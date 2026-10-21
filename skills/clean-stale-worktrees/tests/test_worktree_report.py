import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktree_report.py"
spec = importlib.util.spec_from_file_location("worktree_report", SCRIPT)
worktree_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worktree_report)


def run(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def commit(cwd, name, text, message=None):
    (Path(cwd) / name).write_text(text, encoding="utf-8")
    run(cwd, "add", name)
    run(cwd, "commit", "-q", "-m", message or f"change {name}")


class WorktreeReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.remote = base / "remote.git"
        self.repo = base / "repo"
        self.wt = base / "repo-wt" / "c1"
        run(base, "init", "-q", "--bare", "-b", "main", str(self.remote))
        run(base, "init", "-q", "-b", "main", str(self.repo))
        for key, value in (("user.name", "Test"), ("user.email", "t@example.com")):
            run(self.repo, "config", key, value)
        commit(self.repo, "a.txt", "a\n")
        run(self.repo, "remote", "add", "origin", str(self.remote))
        run(self.repo, "push", "-q", "origin", "main")

        run(self.repo, "worktree", "add", "-q", "-b", "merged", str(self.wt / "merged"), "main")

        run(self.repo, "worktree", "add", "-q", "-b", "squashed", str(self.wt / "squashed"), "main")
        commit(self.wt / "squashed", "b.txt", "b\n")
        commit(self.repo, "b.txt", "b\n", "squash merge of b")
        run(self.repo, "push", "-q", "origin", "main")

        run(self.repo, "worktree", "add", "-q", "-b", "open", str(self.wt / "open"), "main")
        commit(self.wt / "open", "c.txt", "c\n")
        (self.wt / "open" / "new.txt").write_text("draft\n", encoding="utf-8")
        run(self.repo, "worktree", "lock", "--reason", "owner; keep until x", str(self.wt / "open"))

        run(self.repo, "worktree", "add", "-q", "--detach", str(base / "review"), "main")
        run(self.repo, "fetch", "-q", "origin")

    def tearDown(self):
        self.tmp.cleanup()

    def report(self):
        data = worktree_report.build_report(str(self.repo), "origin", None, False, False)
        return {Path(w["path"]).name: w for w in data["worktrees"]}, data

    def test_target_and_primary(self):
        worktrees, data = self.report()
        self.assertEqual(data["target"], "origin/main")
        self.assertTrue(worktrees["repo"]["primary"])

    def test_delivery_states(self):
        worktrees, _ = self.report()
        self.assertEqual(worktrees["merged"]["inTarget"], "ancestor")
        self.assertEqual(worktrees["squashed"]["inTarget"], "content")
        self.assertEqual(worktrees["open"]["inTarget"], "no")
        self.assertEqual(worktrees["open"]["ahead"], 1)

    def test_local_changes_lock_and_campaign(self):
        worktrees, _ = self.report()
        self.assertEqual(worktrees["open"]["changes"]["untracked"], 1)
        self.assertEqual(worktrees["open"]["locked"], "owner; keep until x")
        self.assertEqual(worktrees["open"]["campaign"], "c1")
        self.assertIsNone(worktrees["review"]["campaign"])
        self.assertTrue(worktrees["review"]["detached"])

    def test_missing_target_warns_without_fallback(self):
        data = worktree_report.build_report(str(self.repo), "origin", "nosuch", False, False)
        self.assertIsNone(data["target"])
        self.assertIn("nosuch", data["warning"])
        self.assertNotIn("inTarget", data["worktrees"][0])

    def test_table_renders(self):
        _, data = self.report()
        text = worktree_report.table(data)
        self.assertIn("(detached)", text)
        self.assertIn("owner; keep until x", text)


if __name__ == "__main__":
    unittest.main()
