#!/usr/bin/env python3
"""Haltia dispatcher: starts executors for issues labelled agent:ready (ADR 0005, 0006).

Commands:
  tick [--live]              look at the board and start executors; dry run by default
  run REPO NUMBER MODEL      one executor job; started by `tick --live` in its own systemd unit
  release-check REPO NUMBER  exit 0 if release:approved on the issue or PR was set by the approver

Executors get scoped rights (ADR 0006): they edit files in their own worktree and
never push, tag or call GitHub. This script commits, pushes, opens the PR and moves
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
    "claude_allowed_tools": "Read Edit Write Glob Grep Bash(git status:*) Bash(git diff:*) Bash(git log:*) Bash(git show:*) Bash(ls:*)",
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


def sh(*cmd, cwd=None, check=True, capture=True, input=None):
    r = subprocess.run(cmd, cwd=cwd, check=False, text=True, input=input,
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


def read_status(out_dir):
    """Return ("done", "") or ("blocked", reason) from the executor's status file."""
    try:
        text = (out_dir / "status").read_text().strip()
    except OSError:
        return "done", ""
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


def executor_cmd(model, prompt, worktree, cfg):
    if model == "claude":
        return ["claude", "-p", prompt, "--output-format", "text",
                "--allowedTools", *cfg["claude_allowed_tools"].split()]
    if model == "codex":
        return ["codex", "exec", "-s", "workspace-write", "-C", str(worktree), prompt]
    if model == "grok":
        return ["grok", "-p", prompt, "--cwd", str(worktree), "--permission-mode", "acceptEdits",
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

def prepare_worktree(repo, number):
    clone = CACHE_DIR / "clones" / repo
    if not clone.exists():
        clone.parent.mkdir(parents=True, exist_ok=True)
        sh("gh", "repo", "clone", f"{ORG}/{repo}", str(clone))
    sh("git", "-C", str(clone), "fetch", "--prune", "origin")
    exclude = clone / ".git" / "info" / "exclude"
    if OUT not in exclude.read_text():
        with exclude.open("a") as f:
            f.write(f"\n{OUT}/\n")
    default = sh("git", "-C", str(clone), "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    branch = f"agent/{number}"
    remote_branch = sh("git", "-C", str(clone), "ls-remote", "--heads", "origin", branch).strip()
    base = f"origin/{branch}" if remote_branch else default
    worktree = CACHE_DIR / "work" / job_key(repo, number)
    if worktree.exists():
        sh("git", "-C", str(clone), "worktree", "remove", "--force", str(worktree), check=False)
        shutil.rmtree(worktree, ignore_errors=True)
    sh("git", "-C", str(clone), "worktree", "prune")
    sh("git", "-C", str(clone), "worktree", "add", "-B", branch, str(worktree), base)
    return clone, worktree, branch, base


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
    clone, worktree, branch, base = prepare_worktree(repo, number)
    out = worktree / OUT
    out.mkdir(exist_ok=True)
    issue = gh_json("issue", "view", str(number), "-R", f"{ORG}/{repo}",
                    "--json", "number,title,body,url,comments")
    prompt = build_prompt(PROMPT_FILE.read_text(), repo, issue, OUT)

    log = path / "executor.log"
    with log.open("w") as f:
        rc = subprocess.run(executor_cmd(model, prompt, worktree, cfg), cwd=worktree,
                            stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT).returncode
    log_text = log.read_text(errors="replace")

    if rc != 0 and hit_quota(log_text):
        block(repo, number, f"The {model} subscription limit is reached. "
              "The issue stays with this model; relabel it to change the executor.")
        return "quota"

    status, reason = read_status(out)
    if status == "blocked":
        block(repo, number, reason or "The executor stopped and gave no reason.")
        return "blocked"

    sh("git", "add", "-A", cwd=worktree)
    if sh("git", "status", "--porcelain", cwd=worktree).strip():
        msg = (out / "commit.txt").read_text().strip() if (out / "commit.txt").exists() else ""
        sh("git", "commit", "-F", "-", cwd=worktree, input=(msg or f"Work on issue #{number}.") +
           f"\n\nExecutor: {model} (haltia dispatcher)\n")
    if not sh("git", "rev-list", f"{base}..HEAD", cwd=worktree).strip():
        block(repo, number, f"The {model} executor exited with code {rc} and changed nothing.")
        return "no-changes"

    sh("git", "push", "-u", "origin", branch, cwd=worktree)
    prs = gh_json("pr", "list", "-R", f"{ORG}/{repo}", "--head", branch, "--state", "open", "--json", "number")
    if not prs:
        pr_text = (out / "pr.md").read_text() if (out / "pr.md").exists() else ""
        title, body = split_pr(pr_text, number)
        body = f"{body}\n\nCloses #{number}.\n\nExecutor: {model} (haltia dispatcher). " \
               "Review by another model (ADR 0005).\n"
        sh("gh", "pr", "create", "-R", f"{ORG}/{repo}", "--head", branch, "--title", title, "--body-file", "-",
           input=body)
    set_labels(repo, number, add=["agent:review"], remove=["agent:working"])
    sh("git", "-C", str(clone), "worktree", "remove", "--force", str(worktree), check=False)
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
