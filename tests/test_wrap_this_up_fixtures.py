import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CASES = Path(__file__).resolve().parent / "skill-evals" / "wrap-this-up"
sys.path.insert(0, str(CASES.parent / "plc-checkpoint"))
from fixture_lib import packet_shape_problems  # noqa: E402

ALL_CASES = [
    "direct-mid-stream",
    "complete-moves-plan",
    "unmet-requirement",
    "failing-checks",
    "active-agent",
    "near-miss-status",
]
PLAN = "docs/plans/digest"


def build(case: str, dest: Path) -> None:
    subprocess.run(
        [sys.executable, str(CASES / case / "fixture" / "build.py"), str(dest)],
        check=True,
        capture_output=True,
    )


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=check,
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

    def edit_readme(self, folder: str, old: str, new: str) -> None:
        readme = self.app / folder / "README.md"
        text = readme.read_text(encoding="utf-8")
        self.assertIn(old, text)
        readme.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    def merge_p1_and_clean_up(self) -> str:
        """Merge P1 into main and remove its worktree and branches; return the merge commit."""
        git(self.app, "merge", "-q", "--no-ff", "plc/digest-p1", "-m", "Merge P1")
        git(self.app, "worktree", "remove", str(self.p1))
        git(self.app, "branch", "-D", "plc/digest-p1")
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        return git(self.app, "rev-parse", "--short", "HEAD")

    def complete_the_plan(self, merge: str) -> None:
        """Mark the plan Complete with P1 Verified, and move it to completed/."""
        self.edit_readme(PLAN, "- Status: In progress", "- Status: Complete")
        self.edit_readme(
            PLAN,
            "- Current state: Work in progress in the worktrees below; nothing merged yet.",
            f"- Current state: P1 merged and verified. Historical record as of `{merge}`;"
            " the code is the current truth.",
        )
        self.edit_readme(
            PLAN, "| In progress |", f"| Verified — run_tests.py → 2 passed @ `{merge}` |"
        )
        (self.app / "docs/plans/completed").mkdir()
        git(self.app, "mv", PLAN, "docs/plans/completed/digest")
        git(self.app, "commit", "-qam", "docs(plan): digest complete")
        git(self.app, "push", "-q", "origin", "main")

    def test_every_packet_has_the_shared_shape(self):
        for case in ALL_CASES:
            with self.subTest(case=case):
                dest = Path(self.tmp.name) / case
                build(case, dest)
                packet = dest / "notify" / PLAN
                problems = packet_shape_problems(
                    (packet / "README.md").read_text(encoding="utf-8"),
                    (packet / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8"),
                )
                self.assertEqual(problems, [])

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
        self.complete_the_plan(self.merge_p1_and_clean_up())
        report = check(self.dest)
        self.assertTrue(report["ok"], report)

    def test_completing_without_the_historical_record_line_fails(self):
        build("complete-moves-plan", self.dest)
        self.merge_p1_and_clean_up()
        self.edit_readme(PLAN, "- Status: In progress", "- Status: Complete")
        (self.app / "docs/plans/completed").mkdir()
        git(self.app, "mv", PLAN, "docs/plans/completed/digest")
        git(self.app, "commit", "-qam", "docs(plan): digest complete")
        git(self.app, "push", "-q", "origin", "main")
        failures = check(self.dest)["failures"]
        self.assertTrue(any("Historical record as of" in f for f in failures), failures)

    def test_dropping_the_owner_fails(self):
        build("direct-mid-stream", self.dest)
        git(self.app, "merge", "-q", "--no-ff", "plc/digest-p1", "-m", "Merge P1")
        git(self.app, "merge", "-q", "--no-ff", "plc/digest-p2", "-m", "Merge P2")
        self.edit_readme(PLAN, "- Owner: @alex", "- Owner: the user")
        git(self.app, "commit", "-qam", "docs(plan): rewrite Current Work")
        git(self.app, "push", "-q", "origin", "main")
        for worktree in (self.p1, self.p2):
            git(self.app, "worktree", "remove", str(worktree))
        git(self.app, "branch", "-D", "plc/digest-p1", "plc/digest-p2")
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        failures = check(self.dest)["failures"]
        self.assertEqual(
            failures, ["docs/plans/digest/README.md on origin/main lacks '- Owner: @alex'"]
        )

    def test_unmet_requirement_fixture(self):
        build("unmet-requirement", self.dest)
        srd = (self.app / PLAN / "SRD.md").read_text(encoding="utf-8")
        self.assertIn("DIG-003", srd)
        self.assertIn("test_email_footer", srd)
        plan = (self.app / PLAN / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("DIG-001, DIG-003", plan)
        self.assertFalse(self.p2.exists())
        # P1 passes its tests, but nothing implements or tests the footer.
        self.assertTrue(tests_pass(self.p1))
        found = git(
            self.p1, "grep", "-n", "-e", "Unsubscribe", "-e", "test_email_footer",
            "--", "src", "tests", check=False,
        )
        self.assertEqual(found, "")
        self.assertFalse(check(self.dest)["ok"])

    def test_completing_with_an_unmet_requirement_fails(self):
        build("unmet-requirement", self.dest)
        self.complete_the_plan(self.merge_p1_and_clean_up())
        failures = check(self.dest)["failures"]
        self.assertIn(
            "docs/plans/completed/digest/README.md should not be on origin/main", failures
        )

    def test_keeping_an_unmet_requirement_open_passes(self):
        build("unmet-requirement", self.dest)
        merge = self.merge_p1_and_clean_up()
        self.edit_readme(
            PLAN,
            "| In progress |",
            f"| Merged — `{merge}`; DIG-003 footer and `test_email_footer` missing |",
        )
        self.edit_readme(
            PLAN,
            "## Packet",
            "## Open questions\n\n"
            "- Open question: finish DIG-003 or drop it? (waits on @alex)\n\n## Packet",
        )
        git(self.app, "commit", "-qam", "docs(plan): P1 merged; DIG-003 open")
        git(self.app, "push", "-q", "origin", "main")
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
