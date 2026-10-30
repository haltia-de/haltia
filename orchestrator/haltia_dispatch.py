#!/usr/bin/env python3
"""Haltia dispatcher: starts executors for issues labelled agent:ready (ADR 0005, 0006).

Commands:
  tick [--live]              look at the board and start executors; dry run by default
  run REPO NUMBER MODEL      one executor job; started by `tick --live` in its own systemd unit
  release-check REPO NUMBER  check label attribution for bookkeeping, not human approval (ADR 0011)

Executors get scoped rights (ADR 0006): they edit a plain copy of the tree, with no
.git, and never push, tag or call GitHub. This script commits, pushes, opens the PR and moves
the labels after the executor exits.
"""

import argparse
import configparser
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ORG = "haltia-de"
HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE / "prompt.md"

CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "haltia" / "dispatch.ini"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "haltia-dispatch"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "haltia-dispatch"

MODELS = ("claude", "codex", "grok")
OUT = ".haltia-out"

DEFAULTS = {
    "max_running": "2",
    "memory_max": "4G",
    "timeout_minutes": "120",
    "approver": "",
    # No Bash: prefix rules such as Bash(git diff:*) still allow writes (`--output=`).
    # Web search, and fetching only from documentation sites (ADR 0010): WebFetch
    # runs on this PC, so an open one could reach the home network.
    "claude_allowed_tools": "Read Edit Write Glob Grep WebSearch " + " ".join(
        f"WebFetch(domain:{d})" for d in (
            "docs.gtk.org", "developer.gnome.org", "gitlab.gnome.org", "pygobject.gnome.org",
            "lazka.github.io", "docs.python.org", "pypi.org", "docs.flatpak.org",
            "specifications.freedesktop.org", "www.freedesktop.org", "wiki.alpinelinux.org",
            "gitlab.alpinelinux.org", "wiki.postmarketos.org", "man7.org", "mpv.io",
            "github.com", "raw.githubusercontent.com", "www.gnu.org", "spdx.org")),
}



TEST_TIMEOUT = 600  # seconds for one run of a repository's tests

QUOTA_RE = re.compile(
    r"^(?:(?:API )?Error:\s*|[■●]\s*)?"
    r"(?:You(?:['’]ve| have) (?:hit|reached) your "
    r"(?:(?:\d+[ -]hour|weekly|daily|usage) )?limit\b|Usage limit reached\b)",
    re.IGNORECASE | re.MULTILINE,
)
UNAVAILABLE_RE = re.compile(
    r"^(?:(?:API )?Error:\s*)?(?:503\s+)?(?:service|model) "
    r"(?:is |temporarily |currently )*unavailable\b[^\n]*$|"
    r"^(?:(?:API )?Error:\s*)?(?:server|service) (?:is )?overloaded\b[^\n]*$|"
    r"^(?:Error:\s*)?Please run /login\b[^\n]*$|^API Error:\s*401\b[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)


def load_config():
    cp = configparser.ConfigParser()
    cp.read_dict({"dispatch": DEFAULTS})
    cp.read(CONFIG_FILE)
    return cp["dispatch"]


def sh(*cmd, cwd=None, check=True, capture=True, input=None, env=None):
    r = subprocess.run(cmd, cwd=cwd, check=False, text=True, input=input, env=env,
                       stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.PIPE if capture else None)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: exit {r.returncode}: {(r.stderr or '').strip()}")
    return r.stdout if capture else ""


def gh_json(*args):
    return json.loads(sh("gh", *args) or "null")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# --- pure helpers (tested) ---

def unit_name(repo, number):
    return "haltia-exec-" + re.sub(r"[^A-Za-z0-9]", "_", repo) + f"-{number}"


def job_key(repo, number):
    return f"{repo.lstrip('.')}__{number}"


def label_names(issue):
    return {l["name"] for l in issue.get("labels", [])}


def model_of(issue):
    models = [m for m in MODELS if f"model:{m}" in label_names(issue)]
    return models[0] if len(models) == 1 else None


def pick(issues, busy_repos, slots):
    """Choose up to `slots` issues to start, oldest first.

    Returns (chosen, skipped) where skipped is a list of (issue, reason).
    """
    chosen, skipped = [], []
    busy = set(busy_repos)
    for issue in sorted(issues, key=lambda i: i["createdAt"]):
        names = label_names(issue)
        repo = issue["repository"]["name"]
        if {n for n in names if n.startswith("agent:")} != {"agent:ready"}:
            skipped.append((issue, "not exclusively agent:ready"))
        elif "needs:tablet" in names:
            skipped.append((issue, "needs the tablet; for a live session"))
        elif model_of(issue) is None:
            skipped.append((issue, "no single model: label"))
        elif repo in busy:
            skipped.append((issue, "repository already has an executor"))
        elif len(chosen) >= slots:
            skipped.append((issue, "no free slot"))
        else:
            chosen.append(issue)
            busy.add(repo)
    return chosen, skipped


def hit_quota(log_text):
    # Generic HTTP 429 / "too many requests" can be an application service,
    # not the executor's subscription. Match known CLI limit messages only.
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", log_text[-20000:])
    return bool(QUOTA_RE.search(text))


def read_out(out_dir, name, limit=65536):
    """Read one of the executor's output files, or "" if it is missing.

    Never follows a symlink: the text goes into a public commit and PR, and a link
    could point at any file the dispatcher can read."""
    if out_dir.is_symlink() or not out_dir.is_dir():
        return ""
    try:
        fd = os.open(out_dir / name, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return ""
    with os.fdopen(fd, "rb") as f:
        return f.read(limit).decode("utf-8", errors="replace")


def remove_empty_codex_git_marker(work, model):
    """Discard only an empty real root marker after the Codex scope has stopped."""
    marker = work / ".git"
    if model != "codex" or marker.is_symlink():
        return
    try:
        marker.rmdir()  # Atomic and nonrecursive: files and populated directories stay.
    except OSError:
        pass  # The unchanged metadata guard below rejects anything left behind.


def nested_git(work):
    """Paths of any .git file or directory the executor left in its copy."""
    return [str(p.relative_to(work)) for p in work.rglob(".git")]


def delete_requested(work, text):
    """Remove the files the executor listed in its `delete` file, one path per line.

    Executors without a shell cannot delete or rename. Only files and symlinks
    inside the copy go: no directories, no `..`, nothing outside `work`."""
    removed = []
    root = work.resolve()
    for line in text.splitlines():
        rel = line.strip()
        if not rel or rel.startswith("/") or ".." in Path(rel).parts or Path(rel).parts[:1] == (OUT,):
            continue
        target = work / rel
        if not target.parent.resolve().is_relative_to(root):
            continue
        if target.is_symlink() or target.is_file():
            target.unlink()
            removed.append(rel)
    return removed


def apply_replacements(work, out_dir):
    """Copy regular files from `out/replace/` over the same paths in the copy,
    after delete_requested() removed what they replace (such as a symlink)."""
    src = out_dir / "replace"
    if out_dir.is_symlink() or src.is_symlink() or not src.is_dir():
        return []
    placed = []
    for f in sorted(src.rglob("*")):
        rel = f.relative_to(src)
        if f.is_symlink() or not f.is_file() or rel.parts[:1] in ((OUT,), (".git",)):
            continue
        target = work / rel
        if target.is_symlink() or target.exists():
            continue  # only new paths: deletion has to be asked for first
        if any((work / Path(*rel.parts[:i])).is_symlink() for i in range(1, len(rel.parts))):
            continue  # a linked folder could lead outside the copy
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, target)
        placed.append(str(rel))
    return placed


def read_status(out_dir):
    """Return ("done", "") or ("blocked", reason) from the executor's status file."""
    text = read_out(out_dir, "status").strip()
    if text.lower().startswith("blocked"):
        return "blocked", text.split(":", 1)[1].strip() if ":" in text else ""
    return "done", ""


def split_pr(text, number):
    lines = text.strip().splitlines()
    title = lines[0].lstrip("# ").strip() if lines else ""
    body = "\n".join(lines[1:]).strip()
    return title or f"Work on issue #{number}.", body


def approved_by(events, approver):
    """True if release:approved is on and its last `labeled` event came from `approver`."""
    state, actor = False, None
    for e in events:
        if (e.get("label") or {}).get("name") != "release:approved":
            continue
        if e.get("event") == "labeled":
            state, actor = True, (e.get("actor") or {}).get("login")
        elif e.get("event") == "unlabeled":
            state, actor = False, None
    return bool(approver) and state and actor == approver


def build_prompt(template, repo, issue, out):
    comments = "\n\n".join(
        f"--- {c['author']['login']}, {c['createdAt']}:\n{c['body']}" for c in issue.get("comments", [])
    ) or "(none)"
    return template.format(org=ORG, repo=repo, number=issue["number"], title=issue["title"],
                           url=issue["url"], body=issue["body"] or "(empty)", comments=comments, out=out)


HOME = Path.home()
# What each executor may see of the home folder (ADR 0010): its CLI, read-only,
# and its own login token, writable so a refreshed token is kept. Nothing else.
SANDBOX_RO = {"claude": [HOME / ".local/bin/claude", HOME / ".local/share/claude"],
              "codex": [HOME / ".nvm"],
              "grok": [HOME / ".local/bin/grok", HOME / ".grok/downloads"]}
SANDBOX_RW = {"claude": [HOME / ".claude/.credentials.json"],
              "codex": [HOME / ".codex/auth.json"],
              "grok": [HOME / ".grok/auth.json", HOME / ".grok/auth.json.lock"]}


def sandbox(model, cmd, work, state):
    """Wrap an executor command in bwrap: the home folder, /mnt/data (signing keys,
    other clones), /run/user (session bus, keyring, herdr and Claude sockets) and
    /tmp are empty; only the work copy, the CLI and its token are bound in. The
    network stays: the CLIs talk to their services and search the web."""
    # Own PID, IPC, UTS and cgroup namespaces: without them /proc/<pid>/root of a
    # host process would lead back to the real home folder.
    a = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all", "--share-net",
         "--cap-drop", "ALL", "--ro-bind", "/", "/",
         "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
         "--tmpfs", f"/run/user/{os.getuid()}", "--tmpfs", "/mnt/data", "--tmpfs", str(HOME)]
    for p in SANDBOX_RO[model]:
        a += ["--ro-bind", str(p), str(p)]
    for p in SANDBOX_RW[model]:
        if p.exists():
            a += ["--bind", str(p), str(p)]
    if model == "claude":
        # A bare settings file: no hooks, plugins or project history of the user's.
        cj = state / "claude.json"
        cj.write_text(json.dumps({"hasCompletedOnboarding": True}))
        a += ["--bind", str(cj), str(HOME / ".claude.json")]
    return a + ["--bind", str(work), str(work), "--chdir", str(work), "--setenv", "HOME", str(HOME), "--", *cmd]


def executor_cmd(model, prompt, work, cfg):
    if model == "claude":
        return ["claude", "-p", prompt, "--output-format", "text",
                "--allowedTools", *cfg["claude_allowed_tools"].split()]
    if model == "codex":
        # The sandbox of codex keeps shell commands off the network; --search is
        # OpenAI's server-side web search.
        return ["codex", "--search", "exec", "-s", "workspace-write", "--skip-git-repo-check",
                "-C", str(work), prompt]
    if model == "grok":
        # Inside bwrap Grok's own sandbox cannot nest; file tools and web search
        # only: no run_terminal_command, and no web_fetch, which could send its
        # readable token anywhere. Writes outside the copy land in the empty home.
        return ["grok", "-p", prompt, "--cwd", str(work), "--always-approve",
                "--tools", "read_file,search_replace,list_dir,grep,write,web_search",
                "--output-format", "plain"]
    raise ValueError(model)


# --- jobs ---

def job_dir(repo, number):
    return STATE_DIR / "jobs" / job_key(repo, number)


def read_job(path):
    try:
        return json.loads((path / "job.json").read_text())
    except (OSError, ValueError):
        return None


def write_job(path, job):
    path.mkdir(parents=True, exist_ok=True)
    tmp = path / "job.json.tmp"
    tmp.write_text(json.dumps(job, indent=2))
    tmp.replace(path / "job.json")


def unit_active(unit):
    return sh("systemctl", "--user", "is-active", unit, check=False).strip() in ("active", "activating")


def open_jobs():
    root = STATE_DIR / "jobs"
    if not root.is_dir():
        return []
    return [(p, j) for p in sorted(root.iterdir()) if (j := read_job(p)) and not j.get("finished")]


def set_labels(repo, number, add=(), remove=()):
    args = ["issue", "edit", str(number), "-R", f"{ORG}/{repo}"]
    for l in add:
        args += ["--add-label", l]
    for l in remove:
        args += ["--remove-label", l]
    sh("gh", *args)


def comment(repo, number, text):
    sh("gh", "issue", "comment", str(number), "-R", f"{ORG}/{repo}", "--body-file", "-", input=text)


def block(repo, number, reason):
    comment(repo, number, f"Dispatcher: blocked. {reason}")
    set_labels(repo, number, add=["agent:blocked"], remove=["agent:working", "agent:ready"])


def executor_unavailable(repo, number, model, reason):
    """Advance once along the user's model order; never publish partial output."""
    current = gh_json("issue", "view", str(number), "-R", f"{ORG}/{repo}", "--json", "state,labels")
    if (current.get("state", "").upper() != "OPEN" or model_of(current) != model
            or {n for n in label_names(current) if n.startswith("agent:")} != {"agent:working"}):
        # A person changed the issue while the executor ran. Keep that decision.
        return "superseded"
    index = MODELS.index(model)
    if index == len(MODELS) - 1:
        block(repo, number, f"The {model} executor is unavailable ({reason}). "
              "No next model remains in Claude -> Codex -> Grok; waiting for a person.")
        return "unavailable"
    following = MODELS[index + 1]
    comment(repo, number, f"Dispatcher: {model} is unavailable ({reason}); switching to {following} "
            "under the user's fallback policy (ADR 0012). Partial uncommitted output is not transferred. "
            "The next normal tick starts a fresh scoped executor; no release is authorized.")
    set_labels(repo, number, add=["agent:ready", f"model:{following}"],
               remove=["agent:working", f"model:{model}"])
    return "fallback"


# --- tick ---

def tick(live):
    cfg = load_config()
    running, busy = 0, []
    for path, job in open_jobs():
        if unit_active(job["unit"]):
            running += 1
            busy.append(job["repo"])
            continue
        # The unit is gone but the job never finished: the runner crashed or was killed.
        print(f"crashed: {job['repo']}#{job['number']} ({job['unit']})")
        if live:
            block(job["repo"], job["number"],
                  f"The {job['model']} executor stopped without finishing; the log is on the build PC.")
            job["finished"] = now()
            job["result"] = "crashed"
            write_job(path, job)

    issues = gh_json("search", "issues", "--owner", ORG, "--label", "agent:ready", "--state", "open",
                     "--limit", "100", "--json", "repository,number,title,labels,createdAt,url")
    slots = max(0, int(cfg["max_running"]) - running)
    chosen, skipped = pick(issues, busy, slots)

    print(f"running {running}, free slots {slots}, ready {len(issues)}")
    for issue, reason in skipped:
        print(f"skip  {issue['repository']['name']}#{issue['number']}: {reason}")
    for issue in chosen:
        repo, number, model = issue["repository"]["name"], issue["number"], model_of(issue)
        print(f"start {repo}#{number} with {model}" + ("" if live else " (dry run)"))
        if live:
            start(repo, number, model, cfg)


def start(repo, number, model, cfg):
    unit = unit_name(repo, number)
    path = job_dir(repo, number)
    if path.exists():
        shutil.rmtree(path)
    write_job(path, {"repo": repo, "number": number, "model": model, "unit": unit, "started": now()})
    set_labels(repo, number, add=["agent:working"], remove=["agent:ready"])
    comment(repo, number, f"Dispatcher: taken by {model}, branch `agent/{number}`.")
    sh("systemd-run", "--user", "--collect", f"--unit={unit}",
       f"--property=MemoryMax={cfg['memory_max']}",
       f"--property=RuntimeMaxSec={int(cfg['timeout_minutes']) * 60}",
       f"--setenv=PATH={os.environ.get('PATH', '')}",
       sys.executable, str(Path(__file__).resolve()), "run", repo, str(number), model)


# --- run ---

def git(repo_dir, *args, input=None, check=True):
    """git in a repository only the dispatcher writes, with no hooks or fsmonitor."""
    return sh("git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
              "-C", str(repo_dir), *args, input=input, check=check,
              env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1"))


def prepare(repo, number):
    """Check out the issue's branch in the dispatcher's clone and give the executor
    a plain copy of the tree, with no .git: it never sees or writes git metadata."""
    clone = CACHE_DIR / "clones" / repo
    if not clone.exists():
        clone.parent.mkdir(parents=True, exist_ok=True)
        sh("gh", "repo", "clone", f"{ORG}/{repo}", str(clone), "--", "--no-checkout")
    git(clone, "fetch", "--prune", "origin")
    default = git(clone, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    branch = f"agent/{number}"
    remote_branch = git(clone, "ls-remote", "--heads", "origin", branch).strip()
    base = f"origin/{branch}" if remote_branch else default
    git(clone, "checkout", "-q", "-f", "-B", branch, base)
    git(clone, "clean", "-q", "-ffdx")

    work = CACHE_DIR / "work" / job_key(repo, number)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    sh("rsync", "-a", "--exclude=.git", f"{clone}/", f"{work}/")
    return clone, work, branch, base


def test_command(tree):
    """How a repository runs its tests, or None when it has none."""
    if (tree / "tests" / "run.sh").is_file():
        return ["sh", "tests/run.sh"]
    if (tree / "tests").is_dir() and any((tree / "tests").glob("test*.py")):
        # unittest exits 5 when it finds no TestCase: some repositories' tests
        # are plain scripts that assert as they run.
        return ["sh", "-c", 'python3 -m unittest discover -s tests; rc=$?; [ "$rc" -eq 5 ] || exit "$rc"; '
                'for f in tests/test*.py; do python3 "$f" || exit 1; done']
    return None


def test_sandbox(tree, kit, cmd):
    """bwrap for a repository's tests: no network, an empty home, /mnt/data and
    /run/user hidden; only the tree under test (writable) and kit (read-only)."""
    a = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all", "--cap-drop", "ALL",
         "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
         "--tmpfs", f"/run/user/{os.getuid()}", "--tmpfs", "/mnt/data", "--tmpfs", str(HOME),
         "--bind", str(tree), str(tree), "--chdir", str(tree), "--setenv", "HOME", str(HOME)]
    if kit:
        a += ["--ro-bind", str(kit), str(kit), "--setenv", "PYTHONPATH", str(kit)]
    return a + ["--", *cmd]


def kit_copy(out):
    """A plain copy of haltia-de/kit's main in out, for tests that import
    haltia_kit. Jobs run side by side: the shared kit clone is updated under
    a lock, and every job gets its own copy."""
    import fcntl

    clone = CACHE_DIR / "clones" / "kit"
    clone.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_DIR / "kit.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not clone.exists():
            sh("gh", "repo", "clone", "haltia-de/kit", str(clone), "--", "--no-checkout")
        git(clone, "fetch", "--prune", "origin")
        default = git(clone, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
        tar = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(clone), "archive",
                              default], check=True, capture_output=True).stdout
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    subprocess.run(["tar", "-x", "-C", str(out)], input=tar, check=True)
    return out


def run_tests(tree, kit, log):
    """Run a copy of tree's tests in the test sandbox; (passed, output tail)."""
    cmd = test_command(tree)
    if cmd is None:
        return True, ""
    import tempfile

    scratch = Path(tempfile.mkdtemp(prefix="test-run-", dir=CACHE_DIR))
    sh("rsync", "-a", "--exclude=.git", f"--exclude=/{OUT}", f"{tree}/", f"{scratch}/")
    try:
        r = subprocess.run(test_sandbox(scratch, kit, cmd), capture_output=True, text=True,
                           timeout=TEST_TIMEOUT, stdin=subprocess.DEVNULL)
        ok, text = r.returncode == 0, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        ok, text = False, f"the tests ran longer than {TEST_TIMEOUT} s"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    with open(log, "a") as fh:
        fh.write(f"=== {' '.join(cmd)} in {tree.name}: {'passed' if ok else 'FAILED'}\n{text}\n")
    return ok, text[-3000:]


def can_write(repo, login, cache):
    """True if `login` has write access to the repository (its real permission, not
    the issue's author_association)."""
    if login not in cache:
        r = sh("gh", "api", f"repos/{ORG}/{repo}/collaborators/{login}/permission",
               "--jq", ".permission", check=False).strip()
        cache[login] = r in ("admin", "maintain", "write")
    return cache[login]


def run(repo, number, model):
    cfg = load_config()
    path = job_dir(repo, number)
    job = read_job(path) or {"repo": repo, "number": number, "model": model, "unit": unit_name(repo, number)}
    try:
        job["result"] = run_job(repo, number, model, cfg, path)
    except Exception as e:  # report every failure on the issue; never leave it in agent:working
        job["result"] = "error"
        try:
            block(repo, number, f"The dispatcher failed: {e}")
        except Exception:
            pass
        raise
    finally:
        job["finished"] = now()
        write_job(path, job)


def pr_comments(repo, number):
    """Comments and review bodies of the open PR from agent/<number>, as issue
    comments ({author, createdAt, body}); none when there is no such PR."""
    prs = gh_json("pr", "list", "-R", f"{ORG}/{repo}", "--head", f"agent/{number}",
                  "--state", "open", "--json", "number")
    if not prs:
        return []
    pr = gh_json("pr", "view", str(prs[0]["number"]), "-R", f"{ORG}/{repo}",
                 "--json", "comments,reviews")
    reviews = [{"author": r["author"], "createdAt": r["submittedAt"], "body": r["body"]}
               for r in pr.get("reviews", []) if r.get("body")]
    return pr.get("comments", []) + reviews


def run_job(repo, number, model, cfg, path):
    issue = gh_json("issue", "view", str(number), "-R", f"{ORG}/{repo}",
                    "--json", "number,title,body,url,comments,author")
    writers = {}
    if not can_write(repo, issue["author"]["login"], writers):
        block(repo, number, "The issue's author has no write access; a maintainer should restate it.")
        return "untrusted"
    if not shutil.which(model):
        return executor_unavailable(repo, number, model, "CLI is not installed or not on PATH")
    # A rework: the review findings sit on the open PR of the agent branch, not
    # on the issue, so its comments and reviews join the issue's in time order.
    issue["comments"] = issue.get("comments", []) + pr_comments(repo, number)
    issue["comments"] = [c for c in issue["comments"] if can_write(repo, c["author"]["login"], writers)]
    issue["comments"].sort(key=lambda c: c["createdAt"])

    clone, work, branch, base = prepare(repo, number)
    out = work / OUT
    out.mkdir()
    # Executors have no network: give them the shared rules to read locally.
    shutil.copyfile(HERE.parent / "docs" / "conventions.md", out / "conventions.md")
    prompt = build_prompt(PROMPT_FILE.read_text(), repo, issue, OUT)

    # The executor runs in a scope of its own, and everything left in it is killed
    # when it exits: no process of its may change the copy while it is read.
    # A scope leaves the job unit's cgroup, so it gets the same limits and dies with it.
    job_unit = unit_name(repo, number)
    scope = job_unit + "-executor"
    sh("systemctl", "--user", "stop", f"{scope}.scope", check=False)
    log = path / "executor.log"
    with log.open("w") as f:
        rc = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--collect", f"--unit={scope}",
                             f"--property=MemoryMax={cfg['memory_max']}",
                             f"--property=RuntimeMaxSec={int(cfg['timeout_minutes']) * 60}",
                             f"--property=BindsTo={job_unit}.service",
                             f"--property=PartOf={job_unit}.service",
                             *sandbox(model, executor_cmd(model, prompt, work, cfg), work, path)], cwd=work,
                            stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT).returncode
    sh("systemctl", "--user", "kill", "--signal=SIGKILL", f"{scope}.scope", check=False)
    sh("systemctl", "--user", "stop", f"{scope}.scope", check=False)
    log_text = log.read_text(errors="replace")

    status, reason = read_status(out)
    if status == "blocked":
        block(repo, number, reason or "The executor stopped and gave no reason.")
        return "blocked"
    if rc != 0 and hit_quota(log_text):
        return executor_unavailable(repo, number, model, "subscription or service limit reached")
    if rc != 0 and UNAVAILABLE_RE.search(log_text):
        return executor_unavailable(repo, number, model, "service or CLI login is unavailable")
    if rc != 0:
        block(repo, number, f"The {model} executor failed with exit code {rc}; "
              "no confirmed model unavailability, so its model stays and no partial output is committed.")
        return "failed"

    delete_requested(work, read_out(out, "delete"))
    apply_replacements(work, out)
    remove_empty_codex_git_marker(work, model)
    if found := nested_git(work):
        block(repo, number, f"The {model} executor left git metadata in its copy ({', '.join(found[:5])}); "
              "nothing was committed.")
        return "tampered"
    # The repository's tests, on a copy of the executor's result, before anything
    # is committed. A failure blocks only when the same tests pass on the base:
    # tests already broken before the executor do not hold its work back.
    if test_command(work):
        kit = kit_copy(work.parent / f"{work.name}-kit") if repo != "kit" else None
        try:
            passed, tail = run_tests(work, kit, path / "tests.log")
            base_passed = not passed and run_tests(clone, kit, path / "tests.log")[0]
        finally:
            if kit:
                shutil.rmtree(kit, ignore_errors=True)
        if not passed and base_passed:
            block(repo, number, f"The {model} executor's change fails the repository's tests, "
                  "which pass without it; nothing was pushed. The end of the output:\n\n"
                  f"```\n{tail}\n```")
            return "tests-failed"
    # Copy the executor's files back over the clone's tree; symlinks stay links.
    sh("rsync", "-a", "--delete", "--exclude=.git", f"--exclude=/{OUT}", f"{work}/", f"{clone}/")
    git(clone, "add", "-A")
    if git(clone, "diff", "--cached", "--name-only").strip():
        msg = read_out(out, "commit.txt").strip()
        git(clone, "commit", "-q", "-F", "-", input=(msg or f"Work on issue #{number}.") +
            f"\n\nExecutor: {model} (haltia dispatcher)\n")
    if not git(clone, "rev-list", f"{base}..HEAD").strip():
        block(repo, number, f"The {model} executor exited with code {rc} and changed nothing.")
        return "no-changes"

    git(clone, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    prs = gh_json("pr", "list", "-R", f"{ORG}/{repo}", "--head", branch, "--state", "open", "--json", "number")
    if not prs:
        pr_text = read_out(out, "pr.md")
        title, body = split_pr(pr_text, number)
        body = f"{body}\n\nCloses #{number}.\n\nExecutor: {model} (haltia dispatcher). " \
               "Review per ADR 0008.\n"
        sh("gh", "pr", "create", "-R", f"{ORG}/{repo}", "--head", branch, "--title", title, "--body-file", "-",
           input=body)
    set_labels(repo, number, add=["agent:review"], remove=["agent:working"])
    shutil.rmtree(work, ignore_errors=True)
    return "review"


# --- release-check ---

def release_check(repo, number):
    approver = load_config()["approver"]
    if not approver:
        print("approver is not set in " + str(CONFIG_FILE), file=sys.stderr)
        return 2
    events = gh_json("api", "--paginate", "--slurp", f"repos/{ORG}/{repo}/issues/{number}/events")
    events = [e for page in events for e in page]
    ok = approved_by(events, approver)
    print("approved" if ok else "not approved")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick")
    t.add_argument("--live", action="store_true", help="really change labels and start executors")
    r = sub.add_parser("run")
    r.add_argument("repo")
    r.add_argument("number", type=int)
    r.add_argument("model", choices=MODELS)
    c = sub.add_parser("release-check")
    c.add_argument("repo")
    c.add_argument("number", type=int)
    a = p.parse_args(argv)
    if a.cmd == "tick":
        tick(a.live)
    elif a.cmd == "run":
        run(a.repo, a.number, a.model)
    else:
        return release_check(a.repo, a.number)
    return 0


if __name__ == "__main__":
    sys.exit(main())
