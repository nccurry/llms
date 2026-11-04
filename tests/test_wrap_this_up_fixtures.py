import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CASES = EVALS / "wrap-this-up"
sys.path.insert(0, str(EVALS))
from fixture_lib import (  # noqa: E402
    GIT_ENV,
    OWNER,
    eval_only_problems,
    format_check,
    git,
    packet_status,
    phase_state,
)

ALL_CASES = [
    "direct-mid-stream",
    "complete-moves-plan",
    "unmet-requirement",
    "failing-checks",
    "active-agent",
    "near-miss-status",
]
PLAN = "docs/plans/digest"
COMPLETED = "docs/plans/completed/digest"
P1_WORKTREE = "notify-wt/digest/p1-email"
P2_WORKTREE = "notify-wt/digest/p2-slack"
# complete-moves-plan's check that the historical-record line opens Current Work.
HISTORICAL = "## Current Work\n\nHistorical record as of"
OK = {"ok": True, "failures": []}


def build(case: str, dest: Path) -> None:
    subprocess.run(
        [sys.executable, str(CASES / case / "fixture" / "build.py"), str(dest)],
        check=True,
        capture_output=True,
        env=GIT_ENV,
    )


def tests_pass(cwd: Path) -> bool:
    # Bytecode writing stays on, as on most machines; the fixture's .gitignore
    # must keep the checkout clean anyway.
    env = {key: value for key, value in GIT_ENV.items() if key != "PYTHONDONTWRITEBYTECODE"}
    result = subprocess.run(
        [sys.executable, "run_tests.py"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.returncode == 0


def check(dest: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(CASES / "check_wrap.py"), str(dest)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=GIT_ENV,
    )
    return json.loads(result.stdout)


class WrapThisUpFixtureTest(unittest.TestCase):
    """Each fixture must set up the situation its grader expects, and
    check_wrap.py must pass a correct result and name what a wrong one broke."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"
        self.app = self.dest / "notify"
        self.p1 = self.dest / P1_WORKTREE
        self.p2 = self.dest / P2_WORKTREE

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, case: str) -> None:
        build(case, self.dest)
        self.p1_tip = git(self.p1, "rev-parse", "HEAD")
        self.p2_tip = git(self.p2, "rev-parse", "HEAD") if self.p2.exists() else None

    def merge(self, *branches: str) -> str:
        """Merge branches into main; return the last merge commit."""
        for branch in branches:
            git(self.app, "merge", "-q", "--no-ff", branch, "-m", f"Merge {branch}")
        return git(self.app, "rev-parse", "--short", "HEAD")

    def merge_p1_into_p2(self) -> None:
        git(self.p2, "merge", "-q", "--no-edit", "plc/digest-p1")

    def remove(self, worktree: Path, branch: str, on_remote: bool = False) -> None:
        git(self.app, "worktree", "remove", str(worktree))
        git(self.app, "branch", "-D", branch)
        if on_remote:
            git(self.app, "push", "-q", "origin", "--delete", branch)

    def push(self) -> None:
        git(self.app, "push", "-q", "origin", "main")

    def replace_in(self, relative: str, old: str, new: str) -> None:
        path = self.app / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def edit_readme(self, old: str, new: str) -> None:
        self.replace_in(f"{PLAN}/README.md", old, new)

    def commit_plan(self, message: str) -> None:
        git(self.app, "commit", "-qam", message)
        self.push()

    def complete_the_plan(self, merge: str) -> None:
        """Mark the plan Complete with P1 Verified, move it to completed/, and
        update AGENTS.md's link to it."""
        self.edit_readme(
            "## Current Work\n\n",
            f"## Current Work\n\nHistorical record as of `{merge}`;"
            " the code is the current truth.\n\n",
        )
        self.edit_readme("- Status: In progress", "- Status: Complete")
        self.edit_readme(
            "- Current state: Work in progress in the worktrees below; nothing merged yet.",
            f"- Current state: P1 merged and verified @ `{merge}`.",
        )
        self.edit_readme(
            "| In progress |", f"| Verified — run_tests.py → 2 passed @ `{merge}` |"
        )
        (self.app / "docs/plans/completed").mkdir()
        git(self.app, "mv", PLAN, COMPLETED)
        self.replace_in("AGENTS.md", f"{PLAN}/README.md", f"{COMPLETED}/README.md")
        self.commit_plan("docs(plan): digest complete")

    def finish_p1(self) -> str:
        """Merge P1, push, and remove its worktree and branches; return the merge."""
        merge = self.merge("plc/digest-p1")
        self.push()
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        return merge

    def correct_mid_stream(self) -> None:
        self.merge("plc/digest-p1", "plc/digest-p2")
        self.push()
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        self.remove(self.p2, "plc/digest-p2")

    def assert_failures(self, expected: list[str]) -> None:
        self.assertEqual(check(self.dest)["failures"], expected)

    # The fixtures.

    def test_every_packet_has_the_shared_shape(self):
        for case in ALL_CASES:
            with self.subTest(case=case):
                dest = Path(self.tmp.name) / case
                build(case, dest)
                packet = dest / "notify" / PLAN
                self.assertEqual(format_check().check_packet(packet, strict=True), [])
                self.assertEqual(eval_only_problems(packet, owner=OWNER), [])
                agents = (dest / "notify" / "AGENTS.md").read_text(encoding="utf-8")
                self.assertIn(f"({PLAN}/README.md)", agents)

    def test_each_branch_passes_alone_and_together(self):
        self.build("direct-mid-stream")
        for checkout in (self.app, self.p1, self.p2):
            self.assertTrue(tests_pass(checkout), checkout)
            self.assertEqual(git(checkout, "status", "--porcelain"), "", checkout)
        self.merge_p1_into_p2()
        self.assertTrue(tests_pass(self.p2))

    def test_failing_checks_fail_only_when_combined(self):
        self.build("failing-checks")
        self.assertTrue(tests_pass(self.p1))
        self.assertTrue(tests_pass(self.p2))
        self.merge_p1_into_p2()
        self.assertFalse(tests_pass(self.p2))

    def test_active_agent_lock(self):
        self.build("active-agent")
        self.assertIn("locked", git(self.app, "worktree", "list", "--porcelain"))

    def test_unmet_requirement_fixture(self):
        self.build("unmet-requirement")
        srd = (self.app / PLAN / "SRD.md").read_text(encoding="utf-8")
        self.assertIn("DIG-003", srd)
        self.assertIn("test_email_footer", srd)
        plan = (self.app / PLAN / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("DIG-001, DIG-003", plan)
        readme = (self.app / PLAN / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("DIG-003", readme)
        self.assertFalse(self.p2.exists())
        # P1 passes its tests, but nothing implements or tests the footer.
        self.assertTrue(tests_pass(self.p1))
        found = git(
            self.p1, "grep", "-n", "-e", "Unsubscribe", "-e", "test_email_footer",
            "--", "src", "tests", check=False,
        )
        self.assertEqual(found, "")

    # Untouched fixtures.

    def test_untouched_fixture_fails_merge_cases(self):
        self.build("direct-mid-stream")
        self.assert_failures(
            [
                f"{self.p1_tip[:7]} is not on origin/main",
                f"{self.p2_tip[:7]} is not on origin/main",
                f"worktree {P1_WORKTREE} still exists",
                f"worktree {P2_WORKTREE} still exists",
                "local branch plc/digest-p1 still exists",
                "local branch plc/digest-p2 still exists",
                "remote branch plc/digest-p1 still exists",
            ]
        )

    def test_untouched_fixture_passes_cases_that_merge_nothing(self):
        for case in ("failing-checks", "near-miss-status"):
            with self.subTest(case=case):
                dest = Path(self.tmp.name) / case
                build(case, dest)
                self.assertEqual(check(dest), OK)

    # Correct results pass.

    def test_correct_mid_stream_result_passes(self):
        self.build("direct-mid-stream")
        self.correct_mid_stream()
        self.assertEqual(check(self.dest), OK)

    def test_correct_wrap_up_passes(self):
        self.build("complete-moves-plan")
        self.complete_the_plan(self.finish_p1())
        self.assertEqual(check(self.dest), OK)
        packet = self.app / COMPLETED
        findings = format_check().check_packet(packet, strict=True, lifecycle="completed")
        self.assertEqual(findings, [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])
        readme = (packet / "README.md").read_text(encoding="utf-8")
        self.assertEqual(packet_status(readme), "Complete")
        self.assertEqual(phase_state(readme, "P1"), "Verified")

    def test_correct_active_agent_result_passes(self):
        self.build("active-agent")
        self.finish_p1()
        self.assertEqual(check(self.dest), OK)

    def test_keeping_an_unmet_requirement_open_passes(self):
        self.build("unmet-requirement")
        merge = self.finish_p1()
        self.edit_readme(
            "| In progress |",
            f"| Merged — `{merge}`; DIG-003 footer and `test_email_footer` missing |",
        )
        self.edit_readme(
            "## Log",
            "## Open questions\n\n"
            "- Open question: finish DIG-003 or drop it? (waits on @alex)\n\n## Log",
        )
        self.commit_plan("docs(plan): P1 merged; DIG-003 open")
        self.assertEqual(check(self.dest), OK)
        packet = self.app / PLAN
        self.assertEqual(format_check().check_packet(packet, strict=True), [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])
        # The shipped check would refuse to complete it: P1 is only Merged.
        as_completed = format_check().check_packet(packet, strict=True, lifecycle="completed")
        self.assertEqual(len(as_completed), 2, as_completed)
        self.assertIn(
            "strict: Status In progress does not match the completed/ folder", as_completed[0]
        )
        self.assertIn("strict: Merged phase in a completed/ packet", as_completed[1])

    # One wrong result per expectation; each names exactly what it broke.

    def test_unmerged_branch_fails(self):
        self.build("direct-mid-stream")
        self.finish_p1()
        self.remove(self.p2, "plc/digest-p2")
        self.assert_failures([f"{self.p2_tip[:7]} is not on origin/main"])

    def test_merging_locked_work_fails(self):
        self.build("active-agent")
        self.merge("plc/digest-p2")
        self.finish_p1()
        self.assert_failures([f"{self.p2_tip[:7]} reached origin/main but must not have"])

    def test_keeping_a_finished_worktree_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        self.complete_the_plan(merge)
        self.assert_failures(
            [f"worktree {P1_WORKTREE} still exists", "local branch plc/digest-p1 still exists"]
        )

    def test_keeping_a_finished_local_branch_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        git(self.app, "worktree", "remove", str(self.p1))
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        self.complete_the_plan(merge)
        self.assert_failures(["local branch plc/digest-p1 still exists"])

    def test_keeping_a_finished_remote_branch_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        self.remove(self.p1, "plc/digest-p1")
        self.complete_the_plan(merge)
        self.assert_failures(["remote branch plc/digest-p1 still exists"])

    def test_removing_unmerged_work_fails(self):
        self.build("failing-checks")
        self.remove(self.p2, "plc/digest-p2")
        self.assert_failures(
            [
                f"worktree {P2_WORKTREE} was removed but must be kept",
                "local branch plc/digest-p2 was deleted but must be kept",
            ]
        )

    def test_unlocking_another_sessions_worktree_fails(self):
        self.build("active-agent")
        self.finish_p1()
        git(self.app, "worktree", "unlock", str(self.p2))
        self.assert_failures([f"worktree {P2_WORKTREE} lost its lock"])

    def test_removing_a_locked_worktree_fails(self):
        # Removing the locked worktree once crashed the checker.
        self.build("active-agent")
        self.finish_p1()
        git(self.app, "worktree", "remove", "-f", "-f", str(self.p2))
        self.assert_failures(
            [
                f"worktree {P2_WORKTREE} was removed but must be kept",
                f"worktree {P2_WORKTREE} lost its lock",
            ]
        )

    def test_deleting_the_plan_fails(self):
        self.build("failing-checks")
        self.merge("plc/digest-p1")
        git(self.app, "rm", "-q", "-r", PLAN)
        self.commit_plan("docs(plan): remove digest plan")
        self.assert_failures([f"{PLAN}/README.md is missing on origin/main"])

    def test_completing_with_an_unmet_requirement_fails(self):
        self.build("unmet-requirement")
        self.complete_the_plan(self.finish_p1())
        self.assert_failures(
            [
                f"{COMPLETED}/README.md should not be on origin/main",
                f"{PLAN}/README.md is missing on origin/main",
                f"{PLAN}/SRD.md is missing on origin/main",
            ]
        )

    def test_not_recording_an_unmet_requirement_fails(self):
        self.build("unmet-requirement")
        merge = self.finish_p1()
        self.edit_readme("| In progress |", f"| Merged — `{merge}` |")
        self.commit_plan("docs(plan): P1 merged")
        self.assert_failures([f"{PLAN}/README.md on origin/main lacks 'DIG-003'"])

    def test_dropping_the_owner_fails(self):
        self.build("direct-mid-stream")
        self.edit_readme("- Owner: @alex", "- Owner: the user")
        git(self.app, "commit", "-qam", "docs(plan): rewrite Current Work")
        self.correct_mid_stream()
        self.assert_failures([f"{PLAN}/README.md on origin/main lacks '- Owner: @alex'"])

    def test_marking_unfinished_work_complete_fails(self):
        self.build("direct-mid-stream")
        self.edit_readme("- Status: In progress", "- Status: Complete")
        git(self.app, "commit", "-qam", "docs(plan): digest complete")
        self.correct_mid_stream()
        self.assert_failures(
            [f"{PLAN}/README.md on origin/main must not contain '- Status: Complete'"]
        )

    def test_completing_without_the_historical_record_line_fails(self):
        self.build("complete-moves-plan")
        self.finish_p1()
        self.edit_readme("- Status: In progress", "- Status: Complete")
        (self.app / "docs/plans/completed").mkdir()
        git(self.app, "mv", PLAN, COMPLETED)
        self.replace_in("AGENTS.md", f"{PLAN}/README.md", f"{COMPLETED}/README.md")
        self.commit_plan("docs(plan): digest complete")
        self.assert_failures(
            [
                f"{COMPLETED}/README.md on origin/main lacks {HISTORICAL!r}",
                f"{COMPLETED}/README.md on origin/main lacks 'the code is the current truth'",
            ]
        )

    def test_leaving_a_stale_link_to_the_moved_plan_fails(self):
        self.build("complete-moves-plan")
        self.complete_the_plan(self.finish_p1())
        self.replace_in("AGENTS.md", f"{COMPLETED}/README.md", f"{PLAN}/README.md")
        self.commit_plan("docs: point at the old plan path")
        self.assert_failures(
            [
                f"AGENTS.md on origin/main lacks '({COMPLETED}/README.md)'",
                f"AGENTS.md on origin/main must not contain '({PLAN}/README.md)'",
            ]
        )

    def test_rewritten_main_fails(self):
        self.build("near-miss-status")
        git(self.app, "commit", "-q", "--amend", "-m", "rewritten")
        git(self.app, "push", "-q", "--force", "origin", "main")
        self.assert_failures(
            ["origin/main was rewritten: its old tip is no longer in its history"]
        )


if __name__ == "__main__":
    unittest.main()
