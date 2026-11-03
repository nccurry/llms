import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CASES = Path(__file__).resolve().parent / "skill-evals" / "plc-checkpoint"
sys.path.insert(0, str(CASES))
from fixture_lib import packet_shape_problems  # noqa: E402

# Cases whose packets use the shared PLC template. ad-hoc has no packet, and
# old-shape keeps an older shape on purpose.
SHARED_SHAPE_CASES = [
    "morning-refresh",
    "packet-drift",
    "origin-ahead",
    "dirty-finished",
    "chat-decision",
    "cross-repo-wait",
    "plan-in-other-repo",
    "report-only",
    "active-writer",
    "near-miss-wrap-up",
]


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


def is_ancestor(cwd: Path, commit: str, ref: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(cwd), "merge-base", "--is-ancestor", commit, ref],
        capture_output=True,
    )
    return result.returncode == 0


class PlcCheckpointFixtureTest(unittest.TestCase):
    """Each fixture must set up the situation its grader expects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_packet_has_the_shared_shape(self):
        for case in SHARED_SHAPE_CASES:
            dest = Path(self.tmp.name) / case
            build(case, dest)
            readmes = [
                path
                for path in dest.rglob("README.md")
                if "/docs/plans/" in path.relative_to(dest).as_posix()
            ]
            self.assertTrue(readmes, case)
            for readme in readmes:
                with self.subTest(case=case, packet=str(readme.relative_to(dest))):
                    plan = readme.with_name("IMPLEMENTATION_PLAN.md")
                    problems = packet_shape_problems(
                        readme.read_text(encoding="utf-8"),
                        plan.read_text(encoding="utf-8") if plan.is_file() else "",
                    )
                    self.assertEqual(problems, [])

    def test_packet_drift(self):
        build("packet-drift", self.dest)
        app = self.dest / "billing"
        worktree = self.dest / "billing-wt" / "invoice-export" / "p1-csv"
        readme = "docs/plans/invoice-export/README.md"
        self.assertIn(
            "| P1 | CSV export | | Planned |", (app / readme).read_text(encoding="utf-8")
        )
        self.assertIn(
            "| P1 | CSV export | | Implemented — ",
            (worktree / readme).read_text(encoding="utf-8"),
        )
        self.assertFalse(is_ancestor(app, "plc/invoice-export-p1", "main"))
        self.assertEqual(git(worktree, "status", "--short"), "")

    def test_origin_ahead(self):
        build("origin-ahead", self.dest)
        app = self.dest / "catalog"
        git(app, "fetch", "-q", "origin")
        self.assertTrue(is_ancestor(app, "plc/search-p1", "origin/main"))
        self.assertFalse(is_ancestor(app, "plc/search-p1", "main"))
        readme = "docs/plans/search/README.md"
        row = "| P1 | Case-insensitive search | "
        self.assertIn(f"{row}| In progress |", (app / readme).read_text(encoding="utf-8"))
        self.assertIn(f"{row}| Merged — ", git(app, "show", f"origin/main:{readme}"))

    def test_chat_decision(self):
        build("chat-decision", self.dest)
        app = self.dest / "tavern"
        srd = (app / "docs/plans/shop/SRD.md").read_text(encoding="utf-8")
        self.assertIn("name, cost, and rarity", srd)
        self.assertNotIn(
            "cost", (app / "src/shop_row.py").read_text(encoding="utf-8").split("#")[0]
        )
        self.assertEqual(
            git(app, "rev-parse", "main"), git(app, "rev-parse", "origin/main")
        )
        self.assertEqual(len(git(app, "worktree", "list").splitlines()), 1)
        # The palette decision is recorded; the chat decisions and the
        # SHOP-001 gap are not, and P1 is not ticked off.
        readme = (app / "docs/plans/shop/README.md").read_text(encoding="utf-8")
        self.assertIn("Decision: rarity uses the existing color palette", readme)
        self.assertNotIn("Open question", readme)
        self.assertIn("| P1 | Shop rows and filter | | In progress — ", readme)

    def test_cross_repo_wait(self):
        build("cross-repo-wait", self.dest)
        lib = self.dest / "timekit"
        self.assertNotIn(
            "parse_duration", (lib / "timekit/__init__.py").read_text(encoding="utf-8")
        )
        git(lib, "fetch", "-q", "origin")
        self.assertIn(
            "parse_duration", git(lib, "show", "origin/main:timekit/__init__.py")
        )
        self.assertIn("TK-7", git(lib, "log", "-1", "--format=%s", "origin/main"))
        readme = (self.dest / "scheduler/docs/plans/durations/README.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("- Status: Blocked", readme)
        self.assertIn("- Depends on: timekit TK-7", readme)
        self.assertIn("| P2 | Durations | | Blocked — ", readme)

    def test_near_miss_wrap_up(self):
        build("near-miss-wrap-up", self.dest)
        app = self.dest / "gateway"
        self.assertTrue(is_ancestor(app, "plc/request-ids-p1", "main"))
        self.assertEqual(len(git(app, "worktree", "list").splitlines()), 2)

    def test_morning_refresh(self):
        build("morning-refresh", self.dest)
        app = self.dest / "ledger"
        self.assertTrue(is_ancestor(app, "plc/reconcile-p1", "plc/reconcile"))
        self.assertFalse(is_ancestor(app, "plc/reconcile-p2", "plc/reconcile"))
        self.assertFalse(is_ancestor(app, "plc/reconcile-p1", "main"))
        readme = git(app, "show", "plc/reconcile:docs/plans/reconcile/README.md")
        self.assertIn("- Last updated: 2026-10-26", readme)
        self.assertIn("| P1 | Match lines | | In progress |", readme)
        self.assertIn("- Owner: @alex", readme)
        self.assertIn("- Replaces: `docs/plans/archived/bank-match/`", readme)
        self.assertIn(
            "Superseded by",
            git(app, "show", "plc/reconcile:docs/plans/archived/bank-match/README.md"),
        )

    def test_dirty_finished(self):
        build("dirty-finished", self.dest)
        app = self.dest / "inbox"
        worktree = self.dest / "inbox-wt" / "filters" / "p1-sender"
        self.assertTrue(is_ancestor(app, "plc/filters-p1", "origin/main"))
        self.assertEqual(git(worktree, "status", "--short"), "?? NOTES.md")

    def test_ad_hoc(self):
        build("ad-hoc", self.dest)
        worktree = self.dest / "cli-wt" / "color-output" / "color"
        self.assertFalse((worktree / "docs").exists())
        self.assertEqual(git(worktree, "status", "--short"), "M src/render.py")
        self.assertEqual(len(git(worktree, "log", "--format=%s", "main..").splitlines()), 2)
        self.assertEqual(git(worktree, "branch", "--show-current"), "alex/color-output")

    def test_old_shape(self):
        build("old-shape", self.dest)
        app = self.dest / "marina"
        worktree = self.dest / "marina-wt" / "audit-log" / "p1-record"
        packet = app / "docs/plans/audit-log"
        readme = (packet / "README.md").read_text(encoding="utf-8")
        plan = (packet / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
        problems = packet_shape_problems(readme, plan)
        self.assertIn("old status section: ## Status", problems)
        self.assertIn("needs exactly one ## Current Work, directly after the summary", problems)
        self.assertTrue(any("phase state table outside the README" in p for p in problems))
        self.assertIn("\nStatus: In progress\n", readme)
        self.assertIn("- Created: 2026-10-20", readme)
        self.assertNotIn("Status", (packet / "SRD.md").read_text(encoding="utf-8"))
        self.assertTrue(is_ancestor(app, "plc/audit-log-p1", "origin/main"))
        self.assertEqual(git(worktree, "status", "--short"), "")

    def test_old_shape_moved_and_updated_passes(self):
        """The result the old-shape grader expects passes the checker and the shape check."""
        build("old-shape", self.dest)
        app = self.dest / "marina"
        packet = app / "docs/plans/audit-log"
        merge = git(app, "rev-parse", "--short", "HEAD")
        (packet / "README.md").write_text(
            MOVED_OLD_SHAPE_README.format(merge=merge), encoding="utf-8", newline="\n"
        )
        plan = (packet / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
        plan = plan.replace("Lifecycle status: In progress\n\n", "")
        plan = plan[: plan.index("## Phase Status")] + plan[plan.index("## P1:") :]
        (packet / "IMPLEMENTATION_PLAN.md").write_text(plan, encoding="utf-8", newline="\n")
        git(app, "worktree", "remove", str(self.dest / "marina-wt/audit-log/p1-record"))
        git(app, "branch", "-D", "plc/audit-log-p1")

        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(
            packet_shape_problems((packet / "README.md").read_text(encoding="utf-8"), plan),
            [],
        )

    def test_plan_in_other_repo(self):
        build("plan-in-other-repo", self.dest)
        api = self.dest / "api"
        plans = self.dest / "plans"
        self.assertIn("`../plans`", (api / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertFalse((api / "docs").exists())
        readme = (plans / "docs/plans/sync-api/README.md").read_text(encoding="utf-8")
        self.assertIn("| P1 | Sync endpoint | | Planned |", readme)
        self.assertFalse(is_ancestor(api, "plc/sync-api-p1", "main"))
        snapshot = json.loads((self.dest / "_snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(snapshot["checkouts"]), ["api", "plans"])

    def test_untidied_finished_work_fails_the_checker(self):
        build("origin-ahead", self.dest)
        violations = check(self.dest)["violations"]
        self.assertTrue(any("was not removed" in v for v in violations))
        self.assertTrue(any("catalog.git" in v and "not deleted" in v for v in violations))

    def test_expected_tidying_passes_the_checker(self):
        build("origin-ahead", self.dest)
        app = self.dest / "catalog"
        git(app, "worktree", "remove", str(self.dest / "catalog-wt/search/p1-case"))
        git(app, "branch", "-D", "plc/search-p1")
        git(app, "push", "-q", "origin", "--delete", "plc/search-p1")
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(len(report["tidied"]), 3)

    def test_report_only_rejects_expected_tidying(self):
        build("origin-ahead", self.dest)
        git(self.dest / "catalog", "worktree", "remove", str(self.dest / "catalog-wt/search/p1-case"))
        self.assertFalse(check(self.dest, "--strict")["ok"])

    def test_removing_unfinished_work_is_a_violation(self):
        build("packet-drift", self.dest)
        git(self.dest / "billing", "worktree", "remove", str(self.dest / "billing-wt/invoice-export/p1-csv"))
        violations = check(self.dest)["violations"]
        self.assertTrue(any("removed but not finished" in v for v in violations))

    def test_discarding_uncommitted_work_is_a_violation(self):
        build("ad-hoc", self.dest)
        worktree = self.dest / "cli-wt/color-output/color"
        git(worktree, "checkout", "--", "src/render.py")
        violations = check(self.dest)["violations"]
        self.assertTrue(any("discarded" in v for v in violations))

    def test_stashing_is_a_violation(self):
        build("ad-hoc", self.dest)
        git(self.dest / "cli-wt/color-output/color", "stash", "-q")
        violations = check(self.dest)["violations"]
        self.assertTrue(any("stashed" in v for v in violations))

    def test_ad_hoc_rejects_new_plan_files(self):
        build("ad-hoc", self.dest)
        plan = self.dest / "cli-wt/color-output/color/docs/plans/color.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("# color\n", encoding="utf-8")
        self.assertFalse(check(self.dest)["ok"])

    def test_snapshot_records_every_checkout(self):
        build("cross-repo-wait", self.dest)
        snapshot = json.loads(
            (self.dest / "_snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(sorted(snapshot["checkouts"]), ["scheduler", "timekit"])
        self.assertEqual(sorted(snapshot["remotes"]), ["scheduler.git", "timekit.git"])

    def test_report_only_reuses_cross_repo_fixture(self):
        build("report-only", self.dest)
        self.assertTrue((self.dest / "scheduler" / "src" / "jobs.py").is_file())
        self.assertTrue(check(self.dest, "--strict")["ok"])

    def test_active_writer_has_uncommitted_packet_edits(self):
        build("active-writer", self.dest)
        worktree = self.dest / "billing-wt" / "invoice-export" / "p1-csv"
        status = git(worktree, "status", "--short")
        self.assertIn("docs/plans/invoice-export/IMPLEMENTATION_PLAN.md", status)
        self.assertTrue(check(self.dest)["ok"])


# The old-shape packet after a correct move and status update: the lines are
# moved and renamed, the Log gains the move and P1's merge, and nothing else
# is reworded.
MOVED_OLD_SHAPE_README = """# Audit log PLC

Record who changed each berth booking, so support can answer "who changed
this?" without reading server logs.

## Current Work

- Status: In progress
- Owner: @alex
- Last updated: 2026-11-03, `main` at `{merge}`
- Next action: start P2
- Blocker: None
- Depends on: None
- Current state: P1 merged into `main` at `{merge}`. P2 not started.

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Requirements | Status |
| --- | --- | --- | --- |
| P1 | Record changes | AUD-001 | Merged — `{merge}` |
| P2 | Audit command | AUD-002 | Not started |

## Summary

The record is written in the same transaction as the booking change.

## Packet

- [SRD.md](SRD.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

## Log

- 2026-10-20 Created.
- 2026-11-03 Moved to the shared PLC template (format only).
- 2026-11-03 P1 Merged @ `{merge}`.
"""


def check(dest: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(CASES / "check_state.py"), str(dest), *args],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class CheckStateTest(unittest.TestCase):
    """check_state.py must allow plan record updates and catch closing actions."""

    def setUp(self):
        self.case_tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.case_tmp.name) / "fixture"
        build("cross-repo-wait", self.dest)
        self.app = self.dest / "scheduler"
        self.plan = self.app / "docs/plans/durations/IMPLEMENTATION_PLAN.md"

    def tearDown(self):
        self.case_tmp.cleanup()

    def edit(self, path: Path, text: str) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(text)

    def test_untouched_fixture_passes_strict(self):
        report = check(self.dest, "--strict")
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["packet_changes"], [])

    def test_packet_edit_and_packet_only_commit_are_allowed(self):
        self.edit(self.plan, "\nP2 unblocked: TK-7 landed.\n")
        git(self.app, "commit", "-qam", "docs(plan): update durations status")
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertTrue(any("committed" in c for c in report["packet_changes"]))

    def test_uncommitted_packet_edit_is_allowed(self):
        self.edit(self.plan, "\nP2 unblocked: TK-7 landed.\n")
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertTrue(any("edited" in c for c in report["packet_changes"]))

    def test_strict_rejects_packet_edit(self):
        self.edit(self.plan, "\nP2 unblocked.\n")
        self.assertFalse(check(self.dest, "--strict")["ok"])

    def test_requirement_text_change_is_a_violation(self):
        self.edit(self.app / "docs/plans/durations/SRD.md", "\nSCH-003 added.\n")
        report = check(self.dest)
        self.assertTrue(any("requirement text" in v for v in report["violations"]))

    def test_code_commit_is_a_violation(self):
        self.edit(self.app / "src/jobs.py", "\n# changed\n")
        git(self.app, "commit", "-qam", "change code")
        report = check(self.dest)
        self.assertTrue(any("non-packet" in v for v in report["violations"]))

    def test_push_and_new_branch_are_violations(self):
        git(self.app, "branch", "extra")
        self.edit(self.plan, "\nnote\n")
        git(self.app, "commit", "-qam", "docs(plan): note")
        git(self.app, "push", "-q", "origin", "main")
        violations = check(self.dest)["violations"]
        self.assertTrue(any("moved (push)" in v for v in violations))
        self.assertTrue(any("refs/heads/extra created" in v for v in violations))

    def test_protected_file_change_is_a_violation(self):
        self.edit(self.plan, "\nnote\n")
        report = check(
            self.dest,
            "--protect",
            "scheduler:docs/plans/durations/IMPLEMENTATION_PLAN.md",
        )
        self.assertTrue(any("protected file" in v for v in report["violations"]))


if __name__ == "__main__":
    unittest.main()
