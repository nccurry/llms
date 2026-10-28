import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CASES = Path(__file__).resolve().parent / "skill-evals" / "wrap-this-up"


def build(case: str, dest: Path) -> None:
    subprocess.run(
        [sys.executable, str(CASES / case / "fixture" / "build.py"), str(dest)],
        check=True,
        capture_output=True,
    )


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def tests_pass(cwd: Path) -> bool:
    result = subprocess.run(
        [sys.executable, "run_tests.py"], cwd=cwd, capture_output=True, text=True
    )
    return result.returncode == 0


def check(dest: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(CASES / "check_wrap.py"), str(dest)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class WrapThisUpFixtureTest(unittest.TestCase):
    """Each fixture must set up the situation its grader expects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"
        self.app = self.dest / "notify"
        self.p1 = self.dest / "notify-wt" / "digest" / "p1-email"
        self.p2 = self.dest / "notify-wt" / "digest" / "p2-slack"

    def tearDown(self):
        self.tmp.cleanup()

    def merge_into_p2(self) -> None:
        git(self.p2, "-c", "user.name=x", "-c", "user.email=x@x", "merge", "-q",
            "--no-edit", "plc/digest-p1")

    def test_each_branch_passes_alone_and_together(self):
        build("direct-mid-stream", self.dest)
        for checkout in (self.app, self.p1, self.p2):
            self.assertTrue(tests_pass(checkout), checkout)
        self.merge_into_p2()
        self.assertTrue(tests_pass(self.p2))

    def test_failing_checks_fail_only_when_combined(self):
        build("failing-checks", self.dest)
        self.assertTrue(tests_pass(self.p1))
        self.assertTrue(tests_pass(self.p2))
        self.merge_into_p2()
        self.assertFalse(tests_pass(self.p2))

    def test_active_agent_lock(self):
        build("active-agent", self.dest)
        self.assertIn("locked", git(self.app, "worktree", "list", "--porcelain"))

    def test_untouched_fixture_fails_merge_cases(self):
        build("direct-mid-stream", self.dest)
        self.assertFalse(check(self.dest)["ok"])

    def test_untouched_fixture_passes_cases_that_merge_nothing(self):
        for case in ("failing-checks", "near-miss-status"):
            with self.subTest(case=case):
                dest = Path(self.tmp.name) / case
                build(case, dest)
                self.assertTrue(check(dest)["ok"])

    def test_correct_wrap_up_passes(self):
        build("complete-moves-plan", self.dest)
        git(self.app, "merge", "-q", "--no-ff", "plc/digest-p1", "-m", "Merge P1")
        git(self.app, "mv", "docs/plans/digest", "docs/plans/done-tmp")
        (self.app / "docs/plans/done").mkdir()
        git(self.app, "mv", "docs/plans/done-tmp", "docs/plans/done/digest")
        git(self.app, "commit", "-qm", "docs(plan): digest complete")
        git(self.app, "push", "-q", "origin", "main")
        git(self.app, "worktree", "remove", str(self.p1))
        git(self.app, "branch", "-D", "plc/digest-p1")
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        report = check(self.dest)
        self.assertTrue(report["ok"], report)

    def test_rewritten_main_fails_the_checker(self):
        build("near-miss-status", self.dest)
        git(self.app, "commit", "-q", "--amend", "-m", "rewritten")
        git(self.app, "push", "-q", "--force", "origin", "main")
        failures = check(self.dest)["failures"]
        self.assertTrue(any("rewritten" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
