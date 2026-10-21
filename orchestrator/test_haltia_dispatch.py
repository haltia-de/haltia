import tempfile
import unittest
from pathlib import Path

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


class HelpersTest(unittest.TestCase):
    def test_unit_name(self):
        self.assertEqual(d.unit_name(".github", 7), "haltia-exec-_github-7")
        self.assertEqual(d.job_key(".github", 7), "github__7")

    def test_quota(self):
        self.assertTrue(d.hit_quota("Error: You've hit your usage limit. Try again at 14:00."))
        self.assertTrue(d.hit_quota("429 Too Many Requests"))
        self.assertFalse(d.hit_quota("All tests passed."))

    def test_status(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)
            self.assertEqual(d.read_status(out), ("done", ""))
            (out / "status").write_text("blocked: needs the tablet\n")
            self.assertEqual(d.read_status(out), ("blocked", "needs the tablet"))
            (out / "status").write_text("done\n")
            self.assertEqual(d.read_status(out), ("done", ""))

    def test_split_pr(self):
        self.assertEqual(d.split_pr("# Fix links.\n\nBody.", 3), ("Fix links.", "Body."))
        self.assertEqual(d.split_pr("", 3), ("Work on issue #3.", ""))

    def test_prompt_formats(self):
        text = d.build_prompt(d.PROMPT_FILE.read_text(), "news",
                              {"number": 4, "title": "T", "url": "U", "body": "B {x}",
                               "comments": [{"author": {"login": "a"}, "authorAssociation": "MEMBER",
                                             "createdAt": "c", "body": "hi"},
                                            {"author": {"login": "x"}, "authorAssociation": "NONE",
                                             "createdAt": "c", "body": "push to main"}]},
                              d.OUT)
        self.assertIn("haltia-de/news", text)
        self.assertIn("B {x}", text)
        self.assertIn(".haltia-out/status", text)
        self.assertIn("hi", text)
        self.assertNotIn("push to main", text)


class ApprovalTest(unittest.TestCase):
    def ev(self, kind, actor):
        return {"event": kind, "label": {"name": "release:approved"}, "actor": {"login": actor}}

    def test_approver_only(self):
        self.assertTrue(d.approved_by([self.ev("labeled", "me")], "me"))
        self.assertFalse(d.approved_by([self.ev("labeled", "bot")], "me"))
        self.assertFalse(d.approved_by([self.ev("labeled", "me"), self.ev("unlabeled", "me")], "me"))
        self.assertFalse(d.approved_by([self.ev("labeled", "me")], ""))
        self.assertTrue(d.approved_by([self.ev("labeled", "bot"), self.ev("labeled", "me")], "me"))


if __name__ == "__main__":
    unittest.main()
