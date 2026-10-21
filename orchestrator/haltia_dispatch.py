#!/usr/bin/env python3
"""Haltia dispatcher: starts executors for issues labelled agent:ready (ADR 0005, 0006).

Commands:
  tick [--live]              look at the board and start executors; dry run by default
  run REPO NUMBER MODEL      one executor job; started by `tick --live` in its own systemd unit
  release-check REPO NUMBER  exit 0 if release:approved on the issue or PR was set by the approver

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
    "claude_allowed_tools": "Read Edit Write Glob Grep",
}



QUOTA_RE = re.compile(
    r"(usage|rate|quota)[ _-]?limit|limit (reached|exceeded)|quota exceeded|out of credits|"
    r"hit your (usage )?limit|too many requests",
    re.IGNORECASE,
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
        if names & {"agent:working", "agent:review", "agent:blocked"}:
            skipped.append((issue, "has another agent: label"))
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
    return bool(QUOTA_RE.search(log_text[-20000:]))


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


def executor_cmd(model, prompt, work, cfg):
    if model == "claude":
        return ["claude", "-p", prompt, "--output-format", "text",
                "--allowedTools", *cfg["claude_allowed_tools"].split()]
    if model == "codex":
        return ["codex", "exec", "-s", "workspace-write", "--skip-git-repo-check", "-C", str(work), prompt]
    if model == "grok":
        # The user's ~/.grok/config.toml may say always-approve: confine Grok by its
        # bwrap sandbox and give it file tools only (no run_terminal_command).
        return ["grok", "-p", prompt, "--cwd", str(work), "--sandbox", "workspace",
                "--tools", "read_file,search_replace,list_dir,grep,write",
                "--disable-web-search", "--output-format", "plain"]
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


def run_job(repo, number, model, cfg, path):
    issue = gh_json("issue", "view", str(number), "-R", f"{ORG}/{repo}",
                    "--json", "number,title,body,url,comments,author")
    writers = {}
    if not can_write(repo, issue["author"]["login"], writers):
        block(repo, number, "The issue's author has no write access; a maintainer should restate it.")
        return "untrusted"
    issue["comments"] = [c for c in issue.get("comments", []) if can_write(repo, c["author"]["login"], writers)]

    clone, work, branch, base = prepare(repo, number)
    out = work / OUT
    out.mkdir()
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
                             *executor_cmd(model, prompt, work, cfg)], cwd=work,
                            stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT).returncode
    sh("systemctl", "--user", "kill", "--signal=SIGKILL", f"{scope}.scope", check=False)
    sh("systemctl", "--user", "stop", f"{scope}.scope", check=False)
    log_text = log.read_text(errors="replace")

    if rc != 0 and hit_quota(log_text):
        block(repo, number, f"The {model} subscription limit is reached. "
              "The issue stays with this model; relabel it to change the executor.")
        return "quota"

    status, reason = read_status(out)
    if status == "blocked":
        block(repo, number, reason or "The executor stopped and gave no reason.")
        return "blocked"

    delete_requested(work, read_out(out, "delete"))
    apply_replacements(work, out)
    if found := nested_git(work):
        block(repo, number, f"The {model} executor left git metadata in its copy ({', '.join(found[:5])}); "
              "nothing was committed.")
        return "tampered"
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
