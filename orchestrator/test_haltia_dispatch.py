import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import haltia_dispatch as d


def issue(repo, number, labels, created="2026-10-21T08:00:00Z"):
    return {"repository": {"name": repo}, "number": number, "title": "t", "url": "u",
            "createdAt": created, "labels": [{"name": n} for n in labels]}


class PickTest(unittest.TestCase):
    def test_oldest_first_and_slots(self):
        a = issue("news", 1, ["agent:ready", "model:codex"], "2026-10-21T09:00:00Z")
        b = issue("weather", 2, ["agent:ready", "model:codex"], "2026-10-21T08:00:00Z")
        c = issue("text", 3, ["agent:ready", "model:grok"], "2026-10-21T10:00:00Z")
        chosen, skipped = d.pick([a, b, c], [], 2)
        self.assertEqual([i["number"] for i in chosen], [2, 1])
        self.assertEqual(skipped[0][1], "no free slot")

    def test_skips(self):
        issues = [
            issue("news", 1, ["agent:ready"]),
            issue("news", 2, ["agent:ready", "model:codex", "model:grok"]),
            issue("shell", 3, ["agent:ready", "model:claude", "needs:tablet"]),
            issue("text", 4, ["agent:ready", "model:grok", "agent:blocked"]),
            issue("music", 5, ["agent:ready", "model:claude"]),
        ]
        chosen, skipped = d.pick(issues, ["music"], 2)
        self.assertEqual(chosen, [])
        self.assertEqual(len(skipped), 5)

    def test_one_executor_per_repository(self):
        a = issue("news", 1, ["agent:ready", "model:codex"], "2026-10-21T08:00:00Z")
        b = issue("news", 2, ["agent:ready", "model:grok"], "2026-10-21T09:00:00Z")
        chosen, _ = d.pick([a, b], [], 2)
        self.assertEqual([i["number"] for i in chosen], [1])

    def test_conflicting_or_missing_ready_state_is_never_dispatched(self):
        issues = [issue("news", 1, ["agent:ready", "agent:deferred", "model:codex"]),
                  issue("paint", 2, ["agent:ready", "agent:planned", "model:codex"]),
                  issue("weather", 3, ["model:claude"])]
        chosen, skipped = d.pick(issues, [], 4)
        self.assertEqual(chosen, [])
        self.assertEqual(len(skipped), 3)


class HelpersTest(unittest.TestCase):
    def test_unit_name(self):
        self.assertEqual(d.unit_name(".github", 7), "haltia-exec-_github-7")
        self.assertEqual(d.job_key(".github", 7), "github__7")

    def test_quota(self):
        self.assertTrue(d.hit_quota("Error: You've hit your usage limit. Try again at 14:00."))
        self.assertTrue(d.hit_quota("You’ve hit your usage limit. Upgrade to Pro or try again later."))
        self.assertFalse(d.hit_quota("429 Too Many Requests"))
        self.assertFalse(d.hit_quota("All tests passed."))

    def test_status(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)
            self.assertEqual(d.read_status(out), ("done", ""))
            (out / "status").write_text("blocked: needs the tablet\n")
            self.assertEqual(d.read_status(out), ("blocked", "needs the tablet"))
            (out / "status").write_text("done\n")
            self.assertEqual(d.read_status(out), ("done", ""))

    def test_out_files_never_follow_links(self):
        with tempfile.TemporaryDirectory() as t:
            secret = Path(t) / "secret"
            secret.write_text("token")
            out = Path(t) / "out"
            out.mkdir()
            (out / "pr.md").symlink_to(secret)
            self.assertEqual(d.read_out(out, "pr.md"), "")
            (out / "commit.txt").write_text("x" * 100)
            self.assertEqual(d.read_out(out, "commit.txt", limit=10), "x" * 10)
            link = Path(t) / "linked-out"
            link.symlink_to(out)
            self.assertEqual(d.read_out(link, "commit.txt"), "")

    def test_nested_git(self):
        with tempfile.TemporaryDirectory() as t:
            work = Path(t)
            (work / "a" / "b").mkdir(parents=True)
            self.assertEqual(d.nested_git(work), [])
            (work / "a" / "b" / ".git").write_text("gitdir: /elsewhere")
            self.assertEqual(d.nested_git(work), ["a/b/.git"])

    def test_delete_and_replace(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            work = root / "work"
            work.mkdir()
            (work / "AGENTS.md").write_text("agents")
            (work / "CLAUDE.md").symlink_to("AGENTS.md")
            (root / "outside").write_text("keep")
            (work / "sub").mkdir()
            out = work / d.OUT
            (out / "replace").mkdir(parents=True)
            (out / "replace" / "CLAUDE.md").write_text("@AGENTS.md\n")
            (out / "replace" / "AGENTS.md").write_text("not asked for")
            removed = d.delete_requested(work, "CLAUDE.md\n../outside\n/etc/passwd\nsub\n.haltia-out/status\n")
            self.assertEqual(removed, ["CLAUDE.md"])
            self.assertTrue((root / "outside").exists())
            self.assertTrue((work / "sub").is_dir())
            self.assertEqual(d.apply_replacements(work, out), ["CLAUDE.md"])
            self.assertFalse((work / "CLAUDE.md").is_symlink())
            self.assertEqual((work / "CLAUDE.md").read_text(), "@AGENTS.md\n")
            self.assertEqual((work / "AGENTS.md").read_text(), "agents")

    def test_split_pr(self):
        self.assertEqual(d.split_pr("# Fix links.\n\nBody.", 3), ("Fix links.", "Body."))
        self.assertEqual(d.split_pr("", 3), ("Work on issue #3.", ""))

    def test_prompt_formats(self):
        text = d.build_prompt(d.PROMPT_FILE.read_text(), "news",
                              {"number": 4, "title": "T", "url": "U", "body": "B {x}",
                               "comments": [{"author": {"login": "a"}, "authorAssociation": "MEMBER",
                                             "createdAt": "c", "body": "hi"}]},
                              d.OUT)
        self.assertIn("haltia-de/news", text)
        self.assertIn("B {x}", text)
        self.assertIn(".haltia-out/status", text)
        self.assertIn("hi", text)


class SandboxTest(unittest.TestCase):
    def test_hides_home_and_keys(self):
        with tempfile.TemporaryDirectory() as t:
            work, state = Path(t) / "work", Path(t)
            work.mkdir()
            args = d.sandbox("codex", ["codex", "exec"], work, state)
            pairs = list(zip(args, args[1:]))
            for hidden in ("/mnt/data", str(d.HOME), f"/run/user/{d.os.getuid()}", "/tmp"):
                self.assertIn(("--tmpfs", hidden), pairs)
            self.assertIn(("--bind", str(work)), pairs)
            self.assertIn("--unshare-all", args)
            self.assertIn("--share-net", args)
            self.assertNotIn(str(d.HOME / ".claude/.credentials.json"), args)
            self.assertEqual(args[args.index("--") + 1:], ["codex", "exec"])
            # The work copy is bound after the home folder is emptied.
            self.assertGreater(args.index(str(work)), args.index(str(d.HOME)))


class TestCommandTest(unittest.TestCase):
    def test_choice(self):
        with tempfile.TemporaryDirectory() as t:
            tree = Path(t)
            self.assertIsNone(d.test_command(tree))
            (tree / "tests").mkdir()
            (tree / "tests" / "test_a.py").write_text("")
            self.assertEqual(d.test_command(tree)[:2], ["sh", "-c"])
            (tree / "tests" / "run.sh").write_text("")
            self.assertEqual(d.test_command(tree), ["sh", "tests/run.sh"])

    def test_sandbox_has_no_network(self):
        args = d.test_sandbox(Path("/x"), Path("/k"), ["true"])
        self.assertIn("--unshare-all", args)
        self.assertNotIn("--share-net", args)
        self.assertIn(("--setenv", "PYTHONPATH"), list(zip(args, args[1:])))


class PermissionTest(unittest.TestCase):
    def test_can_write_uses_real_permission_and_caches(self):
        calls = []

        def fake_sh(*cmd, **kw):
            calls.append(cmd)
            return {"me": "admin\n", "helper": "write\n"}.get(cmd[2].split("/")[-2], "read\n")

        real, d.sh = d.sh, fake_sh
        try:
            cache = {}
            self.assertTrue(d.can_write("news", "me", cache))
            self.assertTrue(d.can_write("news", "helper", cache))
            self.assertFalse(d.can_write("news", "stranger", cache))
            self.assertTrue(d.can_write("news", "me", cache))
            self.assertEqual(len(calls), 3)
        finally:
            d.sh = real


class PrCommentsTest(unittest.TestCase):
    def test_comments_and_review_bodies_of_the_agent_pr(self):
        def fake_gh_json(*args):
            if args[:2] == ("pr", "list"):
                return [{"number": 8}] if "agent/7" in args else []
            return {"comments": [{"author": {"login": "me"}, "createdAt": "2026-10-21T10:00:00Z", "body": "fix"}],
                    "reviews": [{"author": {"login": "me"}, "submittedAt": "2026-10-21T09:00:00Z", "body": "review"},
                                {"author": {"login": "me"}, "submittedAt": "2026-10-21T09:30:00Z", "body": ""}]}

        real, d.gh_json = d.gh_json, fake_gh_json
        try:
            got = d.pr_comments("calendar", 7)
            self.assertEqual(sorted(c["body"] for c in got), ["fix", "review"])
            self.assertEqual(d.pr_comments("calendar", 9), [])
        finally:
            d.gh_json = real


class ApprovalTest(unittest.TestCase):
    def ev(self, kind, actor):
        return {"event": kind, "label": {"name": "release:approved"}, "actor": {"login": actor}}

    def test_approver_only(self):
        self.assertTrue(d.approved_by([self.ev("labeled", "me")], "me"))
        self.assertFalse(d.approved_by([self.ev("labeled", "bot")], "me"))
        self.assertFalse(d.approved_by([self.ev("labeled", "me"), self.ev("unlabeled", "me")], "me"))
        self.assertFalse(d.approved_by([self.ev("labeled", "me")], ""))
        self.assertTrue(d.approved_by([self.ev("labeled", "bot"), self.ev("labeled", "me")], "me"))


class AvailabilityTest(unittest.TestCase):
    """Run the real job path; fake only GitHub and the external executor."""

    def execute(self, model, log, *, missing=False, stopped=False, extra_states=()):
        labels = {"agent:working", f"model:{model}", *extra_states}
        messages = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            clone, work = path / "clone", path / "work"
            clone.mkdir()
            work.mkdir()
            (clone / "original").write_text("unchanged")
            data = {"number": 17, "title": "Fix metadata", "body": "bounded task", "url": "u",
                    "comments": [], "author": {"login": "maintainer"}, "state": "OPEN"}

            def read_github(*args):
                return dict(data, labels=[{"name": x} for x in labels])

            def change_labels(repo, number, add=(), remove=()):
                labels.difference_update(remove)
                labels.update(add)

            def executor(*args, **kwargs):
                kwargs["stdout"].write(log)
                (work / "partial").write_text("not transferable")
                if stopped:
                    (work / d.OUT / "status").write_text("blocked: failing application test")
                return subprocess_result

            subprocess_result = type("Result", (), {"returncode": 1})()
            with patch.object(d, "gh_json", side_effect=read_github), \
                 patch.object(d, "can_write", return_value=True), \
                 patch.object(d, "pr_comments", return_value=[]), \
                 patch.object(d, "prepare", return_value=(clone, work, "agent/17", "origin/main")) as prepare, \
                 patch.object(d, "sandbox", side_effect=lambda model, cmd, *rest: cmd), \
                 patch.object(d.shutil, "which", return_value=None if missing else "/usr/bin/executor"), \
                 patch.object(d.subprocess, "run", side_effect=executor), \
                 patch.object(d, "sh", return_value=""), \
                 patch.object(d, "set_labels", side_effect=change_labels), \
                 patch.object(d, "comment", side_effect=lambda repo, number, text: messages.append(text)), \
                 patch.object(d, "git", side_effect=AssertionError("must not commit partial output")):
                result = d.run_job("packages", 17, model, d.load_config(), path)
            self.assertEqual((clone / "original").read_text(), "unchanged")
            self.assertFalse((clone / "partial").exists())
            return result, labels, messages, prepare.call_count

    def test_subscription_limits_advance_once_without_committing_partial_output(self):
        for model, following in (("claude", "codex"), ("codex", "grok")):
            with self.subTest(model=model):
                result, labels, messages, _ = self.execute(model, "You've hit your usage limit.")
                self.assertEqual(result, "fallback")
                self.assertEqual(labels, {"agent:ready", f"model:{following}"})
                self.assertTrue(any(model in x and following in x for x in messages))

    def test_real_five_hour_limit_advances(self):
        result, labels, _, _ = self.execute("claude", "You've hit your 5-hour limit · resets later")
        self.assertEqual(result, "fallback")
        self.assertEqual(labels, {"agent:ready", "model:codex"})

    def test_service_unavailability_advances(self):
        result, labels, _, _ = self.execute("claude", "503 Service unavailable")
        self.assertEqual(result, "fallback")
        self.assertEqual(labels, {"agent:ready", "model:codex"})

    def test_missing_cli_advances_before_preparing_a_copy(self):
        result, labels, _, prepared = self.execute("claude", "", missing=True)
        self.assertEqual(result, "fallback")
        self.assertEqual(labels, {"agent:ready", "model:codex"})
        self.assertEqual(prepared, 0)

    def test_last_model_blocks_without_wrapping_to_claude(self):
        result, labels, _, _ = self.execute("grok", "You've hit your usage limit.")
        self.assertEqual(result, "unavailable")
        self.assertEqual(labels, {"agent:blocked", "model:grok"})

    def test_application_failure_does_not_change_model(self):
        result, labels, _, _ = self.execute("claude", "AssertionError in application test", stopped=True)
        self.assertEqual(result, "blocked")
        self.assertEqual(labels, {"agent:blocked", "model:claude"})

    def test_auth_error_in_blocked_application_keeps_its_model(self):
        result, labels, _, _ = self.execute("claude", "authentication required", stopped=True)
        self.assertEqual(result, "blocked")
        self.assertEqual(labels, {"agent:blocked", "model:claude"})

    def test_generic_failed_output_is_not_committed_or_reassigned(self):
        for log in ("application: authentication required",
                    "Traceback (most recent call last):\nrequests.exceptions.HTTPError: 429 Too Many Requests"):
            with self.subTest(log=log):
                result, labels, _, _ = self.execute("claude", log)
                self.assertEqual(result, "failed")
                self.assertEqual(labels, {"agent:blocked", "model:claude"})

    def test_human_added_state_prevents_fallback(self):
        for state in ("agent:deferred", "agent:planned"):
            with self.subTest(state=state):
                result, labels, messages, _ = self.execute(
                    "claude", "You've hit your usage limit.", extra_states=(state,))
                self.assertEqual(result, "superseded")
                self.assertEqual(labels, {"agent:working", "model:claude", state})
                self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()
