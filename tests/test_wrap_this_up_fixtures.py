import json
import shutil
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
# The checkout wrap-this-up merges in on the direct route.
MERGE_WORKTREE = "notify-wt/digest/_merge"
OK = {"ok": True, "failures": []}


def build(case: str, dest: Path) -> None:
    subprocess.run(
        [sys.executable, str(CASES / case / "fixture" / "build.py"), str(dest)],
        check=True,
        capture_output=True,
        env=GIT_ENV,
    )


def env_writing_bytecode() -> dict[str, str]:
    """GIT_ENV with bytecode writing on and no cache folder elsewhere, as on
    most machines, so the fixture's .gitignore must keep checkouts clean."""
    off = ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")
    return {key: value for key, value in GIT_ENV.items() if key not in off}


def tests_pass(cwd: Path) -> bool:
    result = subprocess.run(
        [sys.executable, "run_tests.py"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env_writing_bytecode(),
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
    check_wrap.py must pass a correct result and name what a wrong one broke.

    The helpers follow the skill's direct route: merge in a `_merge` checkout,
    push from it, remove it, then fast-forward the primary checkout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"
        self.app = self.dest / "notify"
        self.p1 = self.dest / P1_WORKTREE
        self.p2 = self.dest / P2_WORKTREE
        self.merge_dir = self.dest / MERGE_WORKTREE

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, case: str) -> None:
        build(case, self.dest)
        self.p1_tip = git(self.p1, "rev-parse", "HEAD")
        self.p2_tip = git(self.p2, "rev-parse", "HEAD") if self.p2.exists() else None

    # Steps of a wrap-up.

    def merge(self, *branches: str) -> str:
        """Merge branches in the merge checkout; return the last merge commit."""
        if not self.merge_dir.exists():
            git(self.app, "fetch", "-q", "origin")
            git(self.app, "worktree", "add", "-q", "--detach", str(self.merge_dir), "origin/main")
        for branch in branches:
            git(self.merge_dir, "merge", "-q", "--no-ff", branch, "-m", f"Merge {branch}")
        return git(self.merge_dir, "rev-parse", "--short", "HEAD")

    def push(self) -> None:
        git(self.merge_dir, "push", "-q", "origin", "HEAD:main")

    def close_merge_checkout(self) -> None:
        """Remove the merge checkout and fast-forward the primary checkout."""
        git(self.app, "worktree", "remove", str(self.merge_dir))
        git(self.app, "merge", "-q", "--ff-only", "origin/main")

    def remove(self, worktree: Path, branch: str, on_remote: bool = False) -> None:
        git(self.app, "worktree", "remove", str(worktree))
        git(self.app, "branch", "-D", branch)
        if on_remote:
            git(self.app, "push", "-q", "origin", "--delete", branch)

    def replace_in(self, relative: str, old: str, new: str) -> None:
        path = self.merge_dir / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def edit_readme(self, old: str, new: str) -> None:
        self.replace_in(f"{PLAN}/README.md", old, new)

    def commit_plan(self, message: str, push: bool = True) -> None:
        git(self.merge_dir, "commit", "-qam", message)
        if push:
            self.push()

    def complete_the_plan(self, merge: str, historical: str = "plain", push: bool = True) -> None:
        """Mark the plan Complete with P1 Verified, move it to completed/, and
        update AGENTS.md's link to it. `historical` is "plain", "item" (a list
        item) or "none"."""
        line = f"Historical record as of `{merge}`; the code is the current truth."
        opening = {"plain": f"{line}\n\n", "item": f"- {line}\n", "none": ""}[historical]
        self.edit_readme("## Current Work\n\n", f"## Current Work\n\n{opening}")
        self.edit_readme("- Status: In progress", "- Status: Complete")
        self.edit_readme(
            "- Current state: Work in progress in the worktrees below; nothing merged yet.",
            f"- Current state: P1 merged and verified @ `{merge}`.",
        )
        self.edit_readme(
            "| In progress |", f"| Verified — run_tests.py → 2 passed @ `{merge}` |"
        )
        (self.merge_dir / "docs/plans/completed").mkdir()
        git(self.merge_dir, "mv", PLAN, COMPLETED)
        self.replace_in("AGENTS.md", f"{PLAN}/README.md", f"{COMPLETED}/README.md")
        self.commit_plan("docs(plan): digest complete", push=push)

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
        self.close_merge_checkout()

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
            # Bytecode was written, but the fixture's .gitignore hides it.
            self.assertTrue(any(checkout.rglob("__pycache__")), checkout)
            self.assertEqual(git(checkout, "status", "--porcelain"), "", checkout)
        self.merge_p1_into_p2()
        self.assertTrue(tests_pass(self.p2))

    def merge_p1_into_p2(self) -> None:
        git(self.p2, "merge", "-q", "--no-edit", "plc/digest-p1")

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
                f"worktree {P1_WORKTREE} is still registered",
                f"worktree {P1_WORKTREE} folder still exists",
                f"worktree {P2_WORKTREE} is still registered",
                f"worktree {P2_WORKTREE} folder still exists",
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
        self.close_merge_checkout()
        self.assertEqual(check(self.dest), OK)
        packet = self.app / COMPLETED
        findings = format_check().check_packet(packet, strict=True, lifecycle="completed")
        self.assertEqual(findings, [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])
        readme = (packet / "README.md").read_text(encoding="utf-8")
        self.assertEqual(packet_status(readme), "Complete")
        self.assertEqual(phase_state(readme, "P1"), "Verified")

    def test_historical_line_as_a_list_item_passes(self):
        self.build("complete-moves-plan")
        self.complete_the_plan(self.finish_p1(), historical="item")
        self.close_merge_checkout()
        self.assertEqual(check(self.dest), OK)

    def test_correct_active_agent_result_passes(self):
        self.build("active-agent")
        self.finish_p1()
        self.close_merge_checkout()
        self.assertEqual(check(self.dest), OK)

    def test_lock_without_a_reason_still_counts(self):
        self.build("active-agent")
        self.finish_p1()
        self.close_merge_checkout()
        git(self.app, "worktree", "unlock", str(self.p2))
        git(self.app, "worktree", "lock", str(self.p2))
        self.assertEqual(check(self.dest), OK)

    def test_merging_p1_alone_and_cleaning_it_up_passes_failing_checks(self):
        self.build("failing-checks")
        self.finish_p1()
        self.close_merge_checkout()
        self.assertEqual(check(self.dest), OK)

    def test_keeping_an_unmet_requirement_open_passes(self):
        self.build("unmet-requirement")
        merge = self.finish_p1()
        # Part of P1 merged and part never started, so P1 stays In progress.
        self.edit_readme(
            "| In progress |",
            f"| In progress — DIG-001 merged @ `{merge}`; DIG-003 and"
            " `test_email_footer` not started |",
        )
        self.edit_readme(
            "## Log",
            "## Open questions\n\n"
            "- Open question: finish DIG-003 or drop it? (waits on @alex)\n\n## Log",
        )
        self.edit_readme(
            "- 2026-10-26 Created.\n",
            "- 2026-10-26 Created.\n"
            f"- 2026-11-03 DIG-001 merged @ `{merge}`; DIG-003 was never built.\n",
        )
        self.commit_plan("docs(plan): DIG-001 merged; DIG-003 open")
        self.close_merge_checkout()
        self.assertEqual(check(self.dest), OK)
        packet = self.app / PLAN
        self.assertEqual(format_check().check_packet(packet, strict=True), [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])
        # The shipped check would refuse to complete it: P1 is In progress.
        as_completed = format_check().check_packet(packet, strict=True, lifecycle="completed")
        self.assertEqual(len(as_completed), 2, as_completed)
        self.assertIn(
            "strict: Status In progress does not match the completed/ folder", as_completed[0]
        )
        self.assertIn("strict: In progress phase in a completed/ packet", as_completed[1])

    def test_plan_only_commit_in_the_primary_checkout_is_allowed(self):
        # A checkpoint may commit a plan update on local main.
        self.build("near-miss-status")
        readme = self.app / PLAN / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(
            text.replace("- Next action: finish P1 and P2", "- Next action: merge P1"),
            encoding="utf-8",
        )
        git(self.app, "commit", "-qam", "docs(plan): update digest status")
        self.assertEqual(check(self.dest), OK)

    # One wrong result per expectation; each names exactly what it broke.

    def test_merge_and_plan_committed_but_not_pushed_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        self.complete_the_plan(merge, push=False)
        self.close_merge_checkout()
        self.assert_failures(
            [
                f"{self.p1_tip[:7]} is not on origin/main",
                f"{PLAN}/README.md should not be on origin/main",
                f"AGENTS.md on origin/main lacks '({COMPLETED}/README.md)'",
                f"AGENTS.md on origin/main must not contain '({PLAN}/README.md)'",
                f"{COMPLETED}/README.md is missing on origin/main",
            ]
        )

    def test_unmerged_branch_fails(self):
        self.build("direct-mid-stream")
        self.finish_p1()
        self.remove(self.p2, "plc/digest-p2")
        self.close_merge_checkout()
        self.assert_failures([f"{self.p2_tip[:7]} is not on origin/main"])

    def test_merging_locked_work_fails(self):
        self.build("active-agent")
        self.merge("plc/digest-p2")
        self.finish_p1()
        self.close_merge_checkout()
        self.assert_failures([f"{self.p2_tip[:7]} reached origin/main but must not have"])

    def test_merging_in_the_primary_checkout_without_pushing_fails(self):
        self.build("active-agent")
        git(self.app, "merge", "-q", "--no-ff", "plc/digest-p1", "-m", "Merge P1")
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        self.assert_failures(
            [
                f"{self.p1_tip[:7]} is not on origin/main",
                "primary checkout: commits beyond a fast-forward touch "
                "['src/digest.py', 'tests/test_digest.py']",
            ]
        )

    def test_leaving_the_merge_checkout_fails(self):
        self.build("active-agent")
        self.finish_p1()
        self.assert_failures(
            [f"worktree {MERGE_WORKTREE} was added during the run and still exists"]
        )

    def test_leaving_a_new_branch_fails(self):
        self.build("active-agent")
        self.finish_p1()
        git(self.merge_dir, "switch", "-q", "-c", "wrap/digest")
        self.close_merge_checkout()
        self.assert_failures(
            ["local branch wrap/digest was added during the run and still exists"]
        )

    def test_switching_the_primary_checkout_fails(self):
        self.build("near-miss-status")
        git(self.app, "switch", "-q", "--detach")
        self.assert_failures(["primary checkout switched from main to a detached HEAD"])

    def test_code_changes_left_in_the_primary_checkout_fail(self):
        self.build("near-miss-status")
        (self.app / "src" / "draft.py").write_text("# draft\n", encoding="utf-8")
        readme = self.app / PLAN / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assert_failures(["primary checkout: uncommitted changes ['src/draft.py']"])

    def test_keeping_a_finished_worktree_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        self.complete_the_plan(merge)
        self.close_merge_checkout()
        self.assert_failures(
            [
                f"worktree {P1_WORKTREE} is still registered",
                f"worktree {P1_WORKTREE} folder still exists",
                "local branch plc/digest-p1 still exists",
            ]
        )

    def test_deleting_a_worktree_folder_without_unregistering_it_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        shutil.rmtree(self.p1)
        self.complete_the_plan(merge)
        self.close_merge_checkout()
        # Git still counts the branch as checked out there, so it stays too.
        self.assert_failures(
            [
                f"worktree {P1_WORKTREE} is still registered",
                "local branch plc/digest-p1 still exists",
            ]
        )

    def test_unregistering_a_worktree_but_leaving_its_folder_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        shutil.rmtree(self.app / ".git" / "worktrees" / self.p1.name)
        git(self.app, "branch", "-D", "plc/digest-p1")
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        self.complete_the_plan(merge)
        self.close_merge_checkout()
        self.assert_failures([f"worktree {P1_WORKTREE} folder still exists"])

    def test_keeping_a_finished_local_branch_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        git(self.app, "worktree", "remove", str(self.p1))
        git(self.app, "push", "-q", "origin", "--delete", "plc/digest-p1")
        self.complete_the_plan(merge)
        self.close_merge_checkout()
        self.assert_failures(["local branch plc/digest-p1 still exists"])

    def test_keeping_a_finished_remote_branch_fails(self):
        self.build("complete-moves-plan")
        merge = self.merge("plc/digest-p1")
        self.push()
        self.remove(self.p1, "plc/digest-p1")
        self.complete_the_plan(merge)
        self.close_merge_checkout()
        self.assert_failures(["remote branch plc/digest-p1 still exists"])

    def test_merging_p1_alone_without_cleaning_it_up_fails(self):
        self.build("failing-checks")
        self.merge("plc/digest-p1")
        self.push()
        self.close_merge_checkout()
        self.assert_failures(
            [
                f"worktree {P1_WORKTREE} is still registered",
                f"worktree {P1_WORKTREE} folder still exists",
                "local branch plc/digest-p1 still exists",
                "remote branch plc/digest-p1 still exists",
            ]
        )

    def test_removing_unmerged_work_fails(self):
        self.build("failing-checks")
        self.remove(self.p2, "plc/digest-p2")
        self.assert_failures(
            [
                f"worktree {P2_WORKTREE} is no longer registered",
                f"worktree {P2_WORKTREE} folder is gone",
                "local branch plc/digest-p2 was deleted but must be kept",
            ]
        )

    def test_unlocking_another_sessions_worktree_fails(self):
        self.build("active-agent")
        self.finish_p1()
        self.close_merge_checkout()
        git(self.app, "worktree", "unlock", str(self.p2))
        self.assert_failures([f"worktree {P2_WORKTREE} lost its lock"])

    def test_removing_a_locked_worktree_fails(self):
        # Removing the locked worktree once crashed the checker.
        self.build("active-agent")
        self.finish_p1()
        self.close_merge_checkout()
        git(self.app, "worktree", "remove", "-f", "-f", str(self.p2))
        self.assert_failures(
            [
                f"worktree {P2_WORKTREE} is no longer registered",
                f"worktree {P2_WORKTREE} folder is gone",
                f"worktree {P2_WORKTREE} lost its lock",
            ]
        )

    def test_deleting_the_plan_fails(self):
        self.build("failing-checks")
        self.merge("plc/digest-p1")
        git(self.merge_dir, "rm", "-q", "-r", PLAN)
        self.commit_plan("docs(plan): remove digest plan")
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        self.close_merge_checkout()
        self.assert_failures([f"{PLAN}/README.md is missing on origin/main"])

    def test_completing_with_an_unmet_requirement_fails(self):
        self.build("unmet-requirement")
        self.complete_the_plan(self.finish_p1())
        self.close_merge_checkout()
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
        self.close_merge_checkout()
        self.assert_failures([f"{PLAN}/README.md on origin/main lacks 'DIG-003'"])

    def test_dropping_the_owner_fails(self):
        self.build("direct-mid-stream")
        self.merge("plc/digest-p1", "plc/digest-p2")
        self.edit_readme("- Owner: @alex", "- Owner: the user")
        self.commit_plan("docs(plan): rewrite Current Work")
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        self.remove(self.p2, "plc/digest-p2")
        self.close_merge_checkout()
        label = f"plan {PLAN} on origin/main"
        self.assert_failures(
            [
                f"{label}: {PLAN}/README.md:8: Current Work: Owner names no @handle",
                f"{label}: eval: Owner does not name @alex",
            ]
        )

    def assert_status_word_fails(self, word: str) -> None:
        self.build("direct-mid-stream")
        self.merge("plc/digest-p1", "plc/digest-p2")
        self.edit_readme("- Status: In progress", f"- Status: {word}")
        self.commit_plan("docs(plan): digest complete")
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        self.remove(self.p2, "plc/digest-p2")
        self.close_merge_checkout()
        self.assert_failures(
            [f"plan {PLAN} on origin/main: status is Complete, expected In progress or Blocked"]
        )

    def test_marking_unfinished_work_complete_fails(self):
        self.assert_status_word_fails("Complete")

    def test_marking_unfinished_work_done_fails(self):
        # Done is an older spelling of Complete, so it must fail the same way.
        self.assert_status_word_fails("Done")

    def test_completing_without_the_historical_record_line_fails(self):
        self.build("complete-moves-plan")
        self.complete_the_plan(self.finish_p1(), historical="none")
        self.close_merge_checkout()
        self.assert_failures(
            [
                f"plan {COMPLETED} on origin/main: "
                "Current Work does not open with the historical-record line"
            ]
        )

    def test_leaving_a_stale_link_to_the_moved_plan_fails(self):
        self.build("complete-moves-plan")
        self.complete_the_plan(self.finish_p1())
        self.replace_in("AGENTS.md", f"{COMPLETED}/README.md", f"{PLAN}/README.md")
        self.commit_plan("docs: point at the old plan path")
        self.close_merge_checkout()
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
            [
                "origin/main was rewritten: its old tip is no longer in its history",
                "primary checkout: history rewritten or reset",
            ]
        )


if __name__ == "__main__":
    unittest.main()
