import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CASES = EVALS / "plc-wrapup"
sys.path.insert(0, str(EVALS))
from fixture_lib import (  # noqa: E402
    GIT_ENV,
    OWNER,
    PHASES_HEADER,
    eval_only_problems,
    format_check,
    git,
    packet_status,
    phase_rule,
    phase_rule_problem,
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
# The checkout plc-wrapup merges in on the direct route.
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
    push from it, remove it, then fast-forward the primary checkout.

    The unmet-requirement and direct-mid-stream results rewrite the plan the
    way their graders expect: Current Work, phase notes, open questions and
    Log. Every other result is checker-only: it changes just what
    check_wrap.py reads and leaves the rest of the plan to the graders."""

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

    def rewrite_readme(self, change) -> None:
        """Apply `change`, a function from text to text, to the plan's README."""
        path = self.merge_dir / PLAN / "README.md"
        text = path.read_text(encoding="utf-8")
        new = change(text)
        self.assertNotEqual(new, text)
        path.write_text(new, encoding="utf-8", newline="\n")

    def set_key(self, key: str, value: str) -> None:
        """Replace the value of Current Work's `- <key>:` line."""
        pattern = re.compile(rf"^- {re.escape(key)}: .*$", re.MULTILINE)
        self.rewrite_readme(lambda text: pattern.sub(lambda _: f"- {key}: {value}", text, 1))

    def set_phase(self, phase: str, state: str) -> None:
        """Set the State cell of `phase`'s row, which every fixture starts In progress."""

        def change(text: str) -> str:
            lines = text.split("\n")
            i = next(i for i, line in enumerate(lines) if line.startswith(f"| {phase} |"))
            self.assertTrue(lines[i].endswith("| In progress |"), lines[i])
            lines[i] = lines[i].removesuffix("In progress |") + f"{state} |"
            return "\n".join(lines)

        self.rewrite_readme(change)

    def add_phase_row(self, row: str) -> None:
        """Add a row after the last row of the `## Phases` table."""
        end = "\n\n## Done when"
        self.rewrite_readme(lambda text: text.replace(end, f"\n{row}{end}"))

    def drop_checkout_rows(self, *worktrees: str) -> None:
        """Remove the "Where the work lives" rows naming `worktrees`, leaving
        the template's None row when no row is left. A row already gone is
        skipped, so a later plan rewrite can call this again."""
        path = self.merge_dir / PLAN / "README.md"
        text = path.read_text(encoding="utf-8")
        for worktree in worktrees:
            row = re.compile(rf"^\| `{re.escape(worktree)}` \|[^\n]*\n", re.MULTILINE)
            text = row.sub("", text)
        header = "| Checkout | Branch | Owner | State |\n| --- | --- | --- | --- |\n"
        text = text.replace(f"{header}\n", f"{header}| None | | | |\n\n")
        path.write_text(text, encoding="utf-8", newline="\n")

    def add_open_question(self, question: str) -> None:
        self.edit_readme("## Log", f"## Open questions\n\n- Open question: {question}\n\n## Log")

    def add_log_line(self, line: str) -> None:
        """Add a dated line at the end of `## Log`, the README's last section."""
        self.rewrite_readme(lambda text: f"{text}- {line}\n")

    def complete_the_plan(
        self, merge: str, historical: str = "plain", push: bool = True, drop_row: bool = True
    ) -> None:
        """Mark the plan Complete with P1 Verified, drop P1's checkout row, move
        the plan to completed/, and update AGENTS.md's link to it. Checker-only:
        Last updated and Next action keep their old values. `historical` is
        "plain", "item" (a list item) or "none"."""
        line = f"Historical record as of `{merge}`; the code is the current truth."
        opening = {"plain": f"{line}\n\n", "item": f"- {line}\n", "none": ""}[historical]
        if drop_row:
            self.drop_checkout_rows(P1_WORKTREE)
        self.edit_readme("## Current Work\n\n", f"## Current Work\n\n{opening}")
        self.edit_readme("- Status: In progress", "- Status: Complete")
        self.edit_readme(
            "- Current state: Work in progress in the worktrees below; nothing merged yet.",
            f"- Current state: P1 merged and verified @ `{merge}`.",
        )
        self.edit_readme("| In progress |", f"| Verified — run_tests.py → 2 passed @ `{merge}` |")
        (self.merge_dir / "docs/plans/completed").mkdir()
        git(self.merge_dir, "mv", PLAN, COMPLETED)
        self.replace_in("AGENTS.md", f"{PLAN}/README.md", f"{COMPLETED}/README.md")
        self.commit_plan("docs(plan): digest complete", push=push)

    def finish_p1(self, drop_row: bool = True) -> str:
        """Merge P1, drop its checkout row from the plan, push, and remove its
        worktree and branches; return the merge. Checker-only: the rest of
        the plan is left to the graders."""
        merge = self.merge("plc/digest-p1")
        if drop_row:
            self.drop_checkout_rows(P1_WORKTREE)
            self.commit_plan("docs(plan): P1 merged", push=False)
        self.push()
        self.remove(self.p1, "plc/digest-p1", on_remote=True)
        return merge

    def keep_unmet_requirement_open(
        self,
        p1_state: str = "In progress — DIG-001 merged @ `{merge}`; DIG-003 not started",
        new_rows: tuple[str, ...] = (),
        moved_to: str | None = None,
        drop_row: bool = True,
    ) -> None:
        """The unmet-requirement result its grader expects: P1 merged, the plan
        rewritten with DIG-003 recorded as missing, and everything cleaned up.
        `p1_state` and `new_rows` may name `{merge}`, the merge commit. When
        DIG-003 has moved to the new row `moved_to`, the open question blocks
        that row and P1's changed word gets its own Log line."""
        merge = self.finish_p1(drop_row=drop_row)
        self.set_key("Last updated", f"2026-11-03, `main` at `{merge}`")
        self.set_key(
            "Next action",
            "Build DIG-003, the `Unsubscribe:` footer, and `test_email_footer` on a"
            " new branch from `main`, unless @alex defers or drops it.",
        )
        self.set_key("Current state", f"DIG-001 merged @ `{merge}`; DIG-003 not started.")
        self.set_phase("P1", p1_state.format(merge=merge))
        for row in new_rows:
            self.add_phase_row(row.format(merge=merge))
        self.add_open_question(
            f"Build DIG-003 next, or defer or drop it? (blocks {moved_to or 'P1'}; waits on @alex)"
        )
        self.add_log_line(
            f"2026-11-03 DIG-001 merged @ `{merge}`; surprise: DIG-003 was never built."
        )
        if moved_to:
            word = p1_state.split(" — ", 1)[0]
            self.add_log_line(f"2026-11-03 P1 {word} @ `{merge}`; DIG-003 moved to {moved_to}.")
        self.commit_plan("docs(plan): DIG-001 merged; DIG-003 open")
        self.close_merge_checkout()

    def wrap_mid_stream(
        self,
        p2_state: str = "In progress — Slack text merged @ `{p2}`; channel posting not started",
        new_rows: tuple[str, ...] = (),
        merge_p2: bool = True,
        moved_to: str | None = None,
        drop_rows: tuple[str, ...] = (P1_WORKTREE, P2_WORKTREE),
    ) -> None:
        """The direct-mid-stream result its grader expects: both branches
        merged, the plan rewritten with P2's channel posting still to do, and
        everything cleaned up. `p2_state` and `new_rows` may name `{p2}`, P2's
        merge commit. With `merge_p2` false, P2's branch is left unmerged.
        When channel posting has moved to the new row `moved_to`, P2's changed
        word gets its own Log line. `drop_rows` names the checkouts whose
        "Where the work lives" rows the plan update removes."""
        p1 = self.merge("plc/digest-p1")
        p2 = self.merge("plc/digest-p2") if merge_p2 else p1
        self.set_key("Last updated", f"2026-11-03, `main` at `{p2}`")
        self.set_key(
            "Next action",
            "Build P2's channel posting and `test_slack_channel` on a new branch from `main`.",
        )
        self.set_key(
            "Current state",
            f"P1 merged @ `{p1}`. P2's Slack text merged @ `{p2}`; channel posting not started.",
        )
        self.drop_checkout_rows(*drop_rows)
        self.set_phase("P1", f"Merged — `{p1}`")
        self.set_phase("P2", p2_state.format(p2=p2))
        for row in new_rows:
            self.add_phase_row(row.format(p2=p2))
        self.add_log_line(f"2026-11-03 P1 Merged @ `{p1}`.")
        if moved_to:
            word = p2_state.split(" — ", 1)[0]
            self.add_log_line(
                f"2026-11-03 P2 {word} @ `{p2}`; channel posting moved to {moved_to}."
            )
        self.commit_plan("docs(plan): update digest status")
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
            self.p1,
            "grep",
            "-n",
            "-e",
            "Unsubscribe",
            "-e",
            "test_email_footer",
            "--",
            "src",
            "tests",
            check=False,
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
        self.wrap_mid_stream()
        self.assertEqual(check(self.dest), OK)
        packet = self.app / PLAN
        self.assertEqual(format_check().check_packet(packet, strict=True), [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])

    def check_with_channel_posting_moved(self, p2_state: str, row: str = "P3") -> dict:
        """Wrap up with channel posting in its own row `row` and P2 at `p2_state`."""
        self.build("direct-mid-stream")
        new_row = f"| {row} | Channel posting | | Planned — moved from P2 |"
        self.wrap_mid_stream(p2_state, new_rows=(new_row,), moved_to=row)
        return check(self.dest)

    def test_p2_merged_after_moving_channel_posting_passes(self):
        # Once channel posting has its own row, P2 holds only the merged Slack text.
        state = "Merged — `{p2}`; channel posting moved to P3"
        self.assertEqual(self.check_with_channel_posting_moved(state), OK)

    def test_p2_verified_after_moving_channel_posting_passes(self):
        state = "Verified — run_tests.py → 3 passed @ `{p2}`; channel posting moved to P3"
        self.assertEqual(self.check_with_channel_posting_moved(state), OK)

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
        # P1 still holds DIG-003, which nobody built, so it stays In progress.
        self.keep_unmet_requirement_open()
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

    def check_with_dig_003_moved(self, p1_state: str, row: str = "P2") -> dict:
        """Wrap up with DIG-003 in its own row `row` and P1 at `p1_state`."""
        self.build("unmet-requirement")
        new_row = f"| {row} | Email footer | | Planned — DIG-003, moved from P1 |"
        self.keep_unmet_requirement_open(p1_state, new_rows=(new_row,), moved_to=row)
        return check(self.dest)

    def test_p1_merged_after_moving_dig_003_passes(self):
        # Once DIG-003 has its own row, P1 holds only the merged DIG-001.
        report = self.check_with_dig_003_moved("Merged — `{merge}`; DIG-003 moved to P2")
        self.assertEqual(report, OK)

    def test_p1_verified_after_moving_dig_003_passes(self):
        state = "Verified — run_tests.py → 2 passed @ `{merge}`; DIG-003 moved to P2"
        self.assertEqual(self.check_with_dig_003_moved(state), OK)

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

    def test_p1_merged_while_it_holds_dig_003_fails(self):
        self.build("unmet-requirement")
        self.keep_unmet_requirement_open("Merged — `{merge}`; DIG-003 not started")
        self.assert_failures(
            [f"plan {PLAN} on origin/main: phase P1 is Merged, expected In progress"]
        )

    def test_p1_planned_while_dig_001_merged_fails(self):
        self.build("unmet-requirement")
        state = "Planned — DIG-001 merged @ `{merge}`; DIG-003 not started"
        self.keep_unmet_requirement_open(state)
        self.assert_failures(
            [f"plan {PLAN} on origin/main: phase P1 is Planned, expected In progress"]
        )

    def test_moved_to_a_row_that_does_not_exist_fails(self):
        # The note says DIG-003 moved, but no P2 row holds it, so P1 still does.
        state = "Merged — `{merge}`; DIG-003 moved to P2"
        report = self.check_with_dig_003_moved(state, row="P3")
        expected = f"plan {PLAN} on origin/main: phase P1 is Merged, expected In progress"
        self.assertEqual(report["failures"], [expected])

    def test_p2_merged_while_it_holds_channel_posting_fails(self):
        self.build("direct-mid-stream")
        self.wrap_mid_stream("Merged — `{p2}`; channel posting not started")
        self.assert_failures(
            [f"plan {PLAN} on origin/main: phase P2 is Merged, expected In progress"]
        )

    def test_p2_planned_while_its_slack_text_merged_fails(self):
        self.build("direct-mid-stream")
        self.wrap_mid_stream("Planned — Slack text merged @ `{p2}`; channel posting not started")
        self.assert_failures(
            [f"plan {PLAN} on origin/main: phase P2 is Planned, expected In progress"]
        )

    def test_p1_moved_to_itself_fails(self):
        # A note that points at P1's own row moves nothing out of P1.
        self.build("unmet-requirement")
        self.keep_unmet_requirement_open("Merged — `{merge}`; DIG-003 moved to P1")
        self.assert_failures(
            [f"plan {PLAN} on origin/main: phase P1 is Merged, expected In progress"]
        )

    def test_p2_moved_to_a_row_from_the_start_fails(self):
        # P1 was in the plan from the start, so it is not a new row for channel posting.
        self.build("direct-mid-stream")
        self.wrap_mid_stream("Merged — `{p2}`; channel posting moved to P1")
        self.assert_failures(
            [f"plan {PLAN} on origin/main: phase P2 is Merged, expected In progress"]
        )

    def assert_removed_checkout_listed(self, plan: str = PLAN, worktree: str = P1_WORKTREE) -> None:
        self.assert_failures(
            [f"plan {plan} on origin/main: Where the work lives still names removed {worktree}"]
        )

    def test_listing_p2_removed_checkout_fails_direct_mid_stream(self):
        # Both checkouts are removed; the run drops only P1's row.
        self.build("direct-mid-stream")
        self.wrap_mid_stream(drop_rows=(P1_WORKTREE,))
        self.assert_removed_checkout_listed(worktree=P2_WORKTREE)

    def test_listing_a_removed_checkout_fails_unmet_requirement(self):
        self.build("unmet-requirement")
        self.keep_unmet_requirement_open(drop_row=False)
        self.assert_removed_checkout_listed()

    def test_listing_a_removed_checkout_fails_active_agent(self):
        self.build("active-agent")
        self.finish_p1(drop_row=False)
        self.close_merge_checkout()
        self.assert_removed_checkout_listed()

    def test_listing_a_removed_checkout_fails_failing_checks(self):
        self.build("failing-checks")
        self.finish_p1(drop_row=False)
        self.close_merge_checkout()
        self.assert_removed_checkout_listed()

    def test_listing_a_removed_checkout_fails_complete_moves_plan(self):
        self.build("complete-moves-plan")
        self.complete_the_plan(self.finish_p1(drop_row=False), drop_row=False)
        self.close_merge_checkout()
        self.assert_removed_checkout_listed(COMPLETED)

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
        self.wrap_mid_stream(merge_p2=False)
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
        # The plan on origin/main was never updated, so it still lists P1's
        # removed checkout.
        self.assert_failures(
            [
                f"{self.p1_tip[:7]} is not on origin/main",
                "primary checkout: commits beyond a fast-forward touch "
                "['src/digest.py', 'tests/test_digest.py']",
                f"plan {PLAN} on origin/main: Where the work lives still names removed "
                f"{P1_WORKTREE}",
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
        self.assert_failures(["local branch wrap/digest was added during the run and still exists"])

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
        # Checker-only: the plan never names DIG-003.
        self.build("unmet-requirement")
        merge = self.finish_p1()
        self.set_phase("P1", f"In progress — `{merge}`")
        self.commit_plan("docs(plan): P1 merged")
        self.close_merge_checkout()
        self.assert_failures([f"{PLAN}/README.md on origin/main lacks 'DIG-003'"])

    def test_dropping_the_owner_fails(self):
        self.build("direct-mid-stream")
        self.merge("plc/digest-p1", "plc/digest-p2")
        self.edit_readme("- Owner: @alex", "- Owner: the user")
        self.drop_checkout_rows(P1_WORKTREE, P2_WORKTREE)
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
        self.drop_checkout_rows(P1_WORKTREE, P2_WORKTREE)
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


class PhaseRuleTest(unittest.TestCase):
    """fixture_lib.phase_rule_problem, which both checkers use, on small tables."""

    RULE = phase_rule(["In progress"], ["Merged", "Verified"], ["P1", "P2"])

    def problem(self, *rows: str, rule: dict = RULE) -> str | None:
        table = "".join(f"{row}\n" for row in rows)
        readme = f"# T\n\n## Phases\n\n{PHASES_HEADER}\n| --- | --- | --- | --- |\n{table}"
        return phase_rule_problem(readme, "P2", rule)

    def test_in_progress_passes(self):
        self.assertIsNone(self.problem("| P2 | Slack | | In progress — text merged |"))

    def test_a_missing_row_says_so(self):
        self.assertEqual(self.problem("| P1 | Email | | Merged |"), "phase P2 has no row")

    def test_an_unknown_word_names_the_cell(self):
        self.assertEqual(
            self.problem("| P2 | Slack | | Finished — abc1234 |"),
            "phase P2 has no known state word: Finished — abc1234",
        )

    def test_a_move_to_a_new_row_allows_merged(self):
        rows = ("| P2 | Slack | | Merged — moved to P3 |", "| P3 | Posting | | Planned |")
        self.assertIsNone(self.problem(*rows))

    def test_a_move_to_a_row_that_does_not_exist_does_not_count(self):
        self.assertEqual(
            self.problem("| P2 | Slack | | Merged — moved to P3 |"),
            "phase P2 is Merged, expected In progress",
        )

    def test_a_move_to_itself_or_a_starting_row_does_not_count(self):
        for target in ("P2", "P1"):
            with self.subTest(target=target):
                p2 = f"| P2 | Slack | | Merged — moved to {target} |"
                problem = self.problem(p2, "| P1 | Email | | Merged |")
                self.assertEqual(problem, "phase P2 is Merged, expected In progress")

    def test_a_move_to_itself_does_not_count_with_no_starting_rows(self):
        # With no starting rows listed, only the self check rejects this move.
        rule = phase_rule(["In progress"], ["Merged", "Verified"], [])
        problem = self.problem("| P2 | Slack | | Merged — moved to P2 |", rule=rule)
        self.assertEqual(problem, "phase P2 is Merged, expected In progress")

    def test_in_progress_after_a_move_fails(self):
        # Once the unbuilt part has its own row, P2 holds only merged parts.
        rows = ("| P2 | Slack | | In progress — moved to P3 |", "| P3 | Posting | | Planned |")
        self.assertEqual(
            self.problem(*rows), "phase P2 is In progress, expected Merged or Verified"
        )


MR_CASE = CASES / "mr-for-review"
MR_PLAN = "docs/plans/in-progress/retry-backoff"
MR_WORKTREE = "app-wt/retry-backoff/p1"
MR_ROW = (
    "## Merge requests\n\n| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n"
    "| P1 | !3 | Open | |\n\n## Log"
)


class MrForReviewFixtureTest(unittest.TestCase):
    """The mr-for-review fixture sets up an unopened merge request, and
    check_mr_route.py fails what breaks a rule, while a missing
    `## Merge requests` row or `Plan:` line is only a missed suggestion."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name) / "fixture"
        subprocess.run(
            [sys.executable, str(MR_CASE / "fixture" / "build.py"), str(self.dest)],
            check=True,
            capture_output=True,
            env=GIT_ENV,
        )
        self.app = self.dest / "app"
        self.worktree = self.dest / MR_WORKTREE

    def glab(self, *args: str) -> str:
        env = dict(GIT_ENV, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [str(self.dest / "bin" / "glab"), *args],
            cwd=self.app,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def check(self) -> dict:
        result = subprocess.run(
            [sys.executable, str(CASES / "check_mr_route.py"), str(self.dest)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=GIT_ENV,
        )
        return json.loads(result.stdout)

    def open_mr(self, plan_line: bool) -> None:
        body = "Adds a capped backoff delay between retries. `python run_tests.py` passes."
        if plan_line:
            body += "\n\nPlan: PLC-004 P1"
        self.glab(
            "mr",
            "create",
            "--title",
            "Add a capped backoff delay",
            "--source-branch",
            "retry-backoff",
            "--target-branch",
            "main",
            "--description",
            body,
        )

    def update_plan(self, readme_edits: list[tuple[str, str]]) -> None:
        """Commit the plan update on the branch, push it, and remove the worktree."""
        readme = self.worktree / MR_PLAN / "README.md"
        text = readme.read_text(encoding="utf-8")
        edits = [
            ("| In progress |\n\n## Done", "| Implemented — !3 open for review |\n\n## Done"),
            ("- Next action: open the merge request for P1", "- Next action: review and merge !3"),
            (f"| `{MR_WORKTREE}` | `retry-backoff` | p1 child | in progress |", "| None | | | |"),
            (
                "- 2026-11-04 Created.\n",
                "- 2026-11-04 Created.\n- 2026-11-05 P1 Implemented: !3 open.\n",
            ),
            *readme_edits,
        ]
        for old, new in edits:
            self.assertEqual(text.count(old), 1, old)
            text = text.replace(old, new)
        readme.write_text(text, encoding="utf-8", newline="\n")
        git(self.worktree, "commit", "-q", "-am", "docs(plan): P1 is in review in !3")
        git(self.worktree, "push", "-q", "origin", "retry-backoff")
        git(self.app, "worktree", "remove", str(self.worktree))

    def test_fixture_packet_and_tests(self):
        packet = self.app / MR_PLAN
        self.assertEqual(format_check().check_packet(packet, strict=True), [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])
        self.assertTrue(tests_pass(self.worktree))
        self.assertEqual(json.loads((self.dest / "_host" / "state.json").read_text())["mrs"], [])

    def test_untouched_fixture_fails(self):
        report = self.check()
        self.assertEqual(
            report["failures"],
            [
                "no merge request from retry-backoff to main",
                f"plan {MR_PLAN} on retry-backoff: phase P1 is In progress, expected Implemented",
                f"worktree {MR_WORKTREE} is still registered",
                f"worktree {MR_WORKTREE} folder still exists",
            ],
        )
        self.assertEqual(report["missed_suggestions"], ["merge_requests_row", "plan_line"])

    def test_row_and_plan_line_are_credited(self):
        self.open_mr(plan_line=True)
        self.update_plan([("## Log", MR_ROW)])
        self.assertEqual(
            self.check(),
            {
                "ok": True,
                "failures": [],
                "suggestions": {"merge_requests_row": True, "plan_line": True},
                "missed_suggestions": [],
            },
        )

    def test_missing_row_and_plan_line_are_only_missed_suggestions(self):
        self.open_mr(plan_line=False)
        self.update_plan([])
        report = self.check()
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["missed_suggestions"], ["merge_requests_row", "plan_line"])

    def test_row_for_another_mr_is_not_credited(self):
        self.open_mr(plan_line=True)
        self.update_plan([("## Log", MR_ROW.replace("!3", "!4"))])
        report = self.check()
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["missed_suggestions"], ["merge_requests_row"])

    def test_malformed_row_fails_the_format_check(self):
        self.open_mr(plan_line=True)
        self.update_plan([("## Log", MR_ROW.replace("| Open |", "| open |"))])
        failures = self.check()["failures"]
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(
            "State is not Open, Merged @ <commit> or Closed — <reason>: open", failures[0]
        )

    def test_a_second_open_mr_fails_and_the_open_one_is_credited(self):
        self.open_mr(plan_line=True)
        self.update_plan([("## Log", MR_ROW)])
        self.glab(
            "mr",
            "create",
            "--title",
            "Again",
            "--source-branch",
            "retry-backoff",
            "--target-branch",
            "main",
            "--description",
            "Plan: PLC-004 P1",
        )
        report = self.check()
        self.assertEqual(
            report["failures"],
            ["more than one open merge request from retry-backoff to main: !3, !4"],
        )
        self.assertEqual(report["missed_suggestions"], [])

    def test_row_names_the_open_mr_after_a_closed_one(self):
        """A closed !3 replaced by an open !4: only a row for !4 is credited."""
        self.open_mr(plan_line=False)
        state_file = self.dest / "_host" / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["mrs"][0]["state"] = "closed"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        self.glab(
            "mr",
            "create",
            "--title",
            "Retry",
            "--source-branch",
            "retry-backoff",
            "--target-branch",
            "main",
            "--description",
            "Plan: retry-backoff P1",
        )
        self.update_plan([("## Log", MR_ROW)])
        report = self.check()
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["missed_suggestions"], ["merge_requests_row"])

    def test_merging_fails(self):
        self.open_mr(plan_line=True)
        self.update_plan([("## Log", MR_ROW)])
        self.glab("mr", "merge", "3")
        self.assertIn(
            "merge request !3 was merged or set to merge, but the user asked to leave it for review",
            self.check()["failures"],
        )

    def test_pushing_to_main_fails(self):
        self.open_mr(plan_line=True)
        self.update_plan([("## Log", MR_ROW)])
        git(self.app, "push", "-q", "origin", "origin/retry-backoff:refs/heads/main")
        self.assertIn(
            "main on the remote moved; the work must reach it through the merge request",
            self.check()["failures"],
        )


if __name__ == "__main__":
    unittest.main()
