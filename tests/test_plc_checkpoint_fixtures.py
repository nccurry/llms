import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CASES = EVALS / "plc-checkpoint"
sys.path.insert(0, str(EVALS))
import fixture_lib  # noqa: E402
from fixture_lib import (  # noqa: E402
    GIT_ENV,
    OWNER,
    eval_only_problems,
    format_check,
    git,
    is_ancestor,
    packet_status,
    phase_state,
)

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

# The old-shape packet after a correct conversion and status update, as its
# grader expects. The conversion moves lines and renames keys (`Blockers: none`
# becomes `Blocker: none`, value unchanged). Since the packet has SRD.md, step
# M8 adds `## Done when` directly after `## Phases` with the one line pointing
# there; step M5 leaves POINTER_LINE in IMPLEMENTATION_PLAN.md where the table
# was. The status update then rewrites Current Work with the template's keys,
# so Blocker becomes `None`, and adds `Depends on`, `Resume check` and the
# "Where the work lives" table. P1 merged `record` but nobody built the call
# from `save_booking`, so P1 is In progress, with an open question about the
# call and a Log line for that surprise.
CONVERTED_OLD_SHAPE_README = """# Audit log PLC

Record who changed each berth booking, so support can answer "who changed
this?" without reading server logs.

## Current Work

- Status: In progress
- Owner: @alex
- Last updated: 2026-11-03, `main` at `{merge}`
- Next action: @alex answers the `save_booking` question below; then start P2 on a new branch from `main`.
- Blocker: None
- Depends on: None
- Current state: `record` merged into `main` at `{merge}`; nothing calls it from `save_booking` yet. P2 not started.
- Resume check: `git log --oneline -1 main` → the P1 merge

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Requirements | Status |
| --- | --- | --- | --- |
| P1 | Record changes | AUD-001 | In progress — `record` merged @ `{merge}`; call from `save_booking` not started |
| P2 | Audit command | AUD-002 | Not started |

## Done when

{done_when}

## Open questions

- Open question: No `save_booking` exists to call `record` from. Where does the booking code live? (blocks P1; waits on @alex)

## Summary

The record is written in the same transaction as the booking change.

## Packet

- [SRD.md](SRD.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

## Log

- 2026-10-20 Created.
- 2026-11-03 Converted to the shared PLC template (format only).
- 2026-11-03 Surprise: P1 merged @ `{merge}`, but nothing calls `record` from `save_booking`.
"""
# Step M8's line for a repository with no README template of its own, and the
# line step M5 leaves where the phase table was.
DONE_WHEN_LINE = "The requirements and their checks are in [SRD.md](SRD.md)."
POINTER_LINE = "Phase state lives in the README's [Phases](README.md#phases) table."


# The grow-plan plan after a correct checkpoint. The user approved the
# `--max-age` flag, a public contract, so the one-file plan became a folder:
# GROWN_SRD holds TIDE-001 and the new TIDE-002 with their checks,
# `## Done when` holds only the pointer line, P2 holds the new work, and the
# Log has the decision and a line naming SRD.md.
GROWN_README = """# Tide cache

Cache the tide feed for a minute, so repeated `tides show` calls don't fetch it each time.

## Current Work

- Status: In progress
- Owner: @alex
- Last updated: 2026-11-04, `main` at `{head}`
- Next action: Write a failing test for `tides show --max-age -1` in `tests/test_cli.py`.
- Blocker: None
- Depends on: None
- Current state: P1 verified @ `{merge}`. P2, the approved `--max-age` flag, is not started.
- Resume check: `python -m unittest` → 2 tests OK

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | Cache the feed | | Verified — `python -m unittest` → 2 tests OK @ `{merge}` |
| P2 | `--max-age` flag | | Planned |

## Done when

{done_when}

## Log

- 2026-11-02 Created.
- 2026-11-03 P1 merged @ `{merge}`.
- 2026-11-03 P1 verified: `python -m unittest` → 2 tests OK @ `{merge}`.
- 2026-11-04 Decision: add `tides show --max-age SECONDS` (TIDE-002), approved by @alex in chat.
- 2026-11-04 Added SRD.md: the `--max-age` flag is a public contract.
"""
GROWN_SRD = """# Tide cache requirements

## Requirements

| ID | Priority | Requirement | Check |
| --- | --- | --- | --- |
| TIDE-001 | Must | A second `tides show` within a minute reads the feed once. | `python -m unittest tests.test_cache` → passes |
| TIDE-002 | Must | `tides show --max-age SECONDS` keeps a fetched feed that many seconds, 60 by default, and `--max-age 0` turns the cache off. A negative or non-numeric value exits with status 2 and prints `tides: --max-age must be 0 or more seconds`. | `python -m unittest tests.test_cli` → passes |

## User Experience And Public Surface

| Surface | Action or input | Expected result | Compatibility |
| --- | --- | --- | --- |
| CLI | `tides show --max-age -1` | Exit status 2 and `tides: --max-age must be 0 or more seconds` | new |
"""
# The requirements as `## Done when` lines, where a one-file plan keeps them.
TIDE_REQUIREMENTS = (
    "- TIDE-001: A second `tides show` within a minute reads the feed once."
    " Check: `python -m unittest tests.test_cache` → passes\n"
    "- TIDE-002: `tides show --max-age -1` exits with status 2."
    " Check: `python -m unittest tests.test_cli` → passes"
)
GROWN = "tides/docs/plans/in-progress/tide-cache"
ONE_FILE_PLAN = "docs/plans/in-progress/plc-tide-cache.md"


def load_check_state():
    """Import check_state.py by path without writing a bytecode cache."""
    spec = importlib.util.spec_from_file_location("check_state", CASES / "check_state.py")
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


check_state = load_check_state()


def build(case: str, dest: Path, env: dict[str, str] = GIT_ENV) -> None:
    subprocess.run(
        [sys.executable, str(CASES / case / "fixture" / "build.py"), str(dest)],
        check=True,
        capture_output=True,
        env=env,
    )


def check(dest: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(CASES / "check_state.py"), str(dest), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=GIT_ENV,
        check=False,
    )
    return json.loads(result.stdout)


def shipped_findings(packet: Path) -> list[str]:
    """The planning skill's format check on a packet, in strict mode."""
    return format_check().check_packet(packet, strict=True)


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
                    self.assertEqual(shipped_findings(readme.parent), [])
                    self.assertEqual(eval_only_problems(readme.parent, owner=OWNER), [])

    def test_fixture_git_ignores_the_developers_git_config(self):
        # A global config that breaks every commit: signing with a key that
        # does not exist. Fixture git must not read it.
        home = Path(self.tmp.name) / "home"
        home.mkdir()
        config = home / ".gitconfig"
        config.write_text(
            "[commit]\n\tgpgsign = true\n[user]\n\tsigningkey = no-such-key\n",
            encoding="utf-8",
        )
        # A scratch repository the caller's GIT_DIR and GIT_INDEX_FILE point
        # at. Fixture git must not write to it.
        scratch = Path(self.tmp.name) / "scratch"
        scratch.mkdir()
        git(scratch, "init", "-q", "-b", "main")
        git(
            scratch,
            "-c",
            "user.name=x",
            "-c",
            "user.email=x@x.invalid",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "scratch",
        )
        refs_before = git(scratch, "for-each-ref")
        index = scratch / ".git" / "index"
        index_before = index.read_bytes() if index.exists() else None
        hostile = {
            **GIT_ENV,
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": str(config),
            "GIT_DIR": str(scratch / ".git"),
            "GIT_INDEX_FILE": str(index),
        }
        build("dirty-finished", self.dest, env=hostile)
        self.assertTrue((self.dest / "inbox" / "docs/plans/filters/README.md").is_file())
        self.assertEqual(git(scratch, "for-each-ref"), refs_before)
        self.assertEqual(index.read_bytes() if index.exists() else None, index_before)

    def test_packet_drift(self):
        build("packet-drift", self.dest)
        app = self.dest / "billing"
        worktree = self.dest / "billing-wt" / "invoice-export" / "p1-csv"
        readme = "docs/plans/invoice-export/README.md"
        main_copy = (app / readme).read_text(encoding="utf-8")
        worktree_copy = (worktree / readme).read_text(encoding="utf-8")
        self.assertEqual(phase_state(main_copy, "P1"), "Planned")
        self.assertEqual(phase_state(worktree_copy, "P1"), "Implemented")
        self.assertIn("Implemented — ", worktree_copy)
        # Both copies come from the same packet, created on the same day.
        self.assertIn("- 2026-10-24 Created.", main_copy)
        self.assertIn("- 2026-10-24 Created.", worktree_copy)
        self.assertFalse(is_ancestor(app, "plc/invoice-export-p1", "main"))
        self.assertEqual(git(worktree, "status", "--short"), "")

    def test_origin_ahead(self):
        build("origin-ahead", self.dest)
        app = self.dest / "catalog"
        git(app, "fetch", "-q", "origin")
        self.assertTrue(is_ancestor(app, "plc/search-p1", "origin/main"))
        self.assertFalse(is_ancestor(app, "plc/search-p1", "main"))
        readme = "docs/plans/search/README.md"
        local_copy = (app / readme).read_text(encoding="utf-8")
        self.assertEqual(phase_state(local_copy, "P1"), "In progress")
        self.assertEqual(phase_state(git(app, "show", f"origin/main:{readme}"), "P1"), "Merged")

    def test_chat_decision(self):
        build("chat-decision", self.dest)
        app = self.dest / "tavern"
        srd = (app / "docs/plans/shop/SRD.md").read_text(encoding="utf-8")
        self.assertIn("name, cost, and rarity", srd)
        self.assertNotIn(
            "cost", (app / "src/shop_row.py").read_text(encoding="utf-8").split("#")[0]
        )
        self.assertEqual(git(app, "rev-parse", "main"), git(app, "rev-parse", "origin/main"))
        self.assertEqual(len(git(app, "worktree", "list").splitlines()), 1)
        # The palette decision is recorded; the chat decisions and the
        # SHOP-001 gap are not, and P1 is not ticked off.
        readme = (app / "docs/plans/shop/README.md").read_text(encoding="utf-8")
        self.assertIn("Decision: rarity uses the existing color palette", readme)
        self.assertNotIn("Open question", readme)
        self.assertEqual(phase_state(readme, "P1"), "In progress")

    def test_cross_repo_wait(self):
        build("cross-repo-wait", self.dest)
        lib = self.dest / "timekit"
        self.assertNotIn(
            "parse_duration", (lib / "timekit/__init__.py").read_text(encoding="utf-8")
        )
        git(lib, "fetch", "-q", "origin")
        self.assertIn("parse_duration", git(lib, "show", "origin/main:timekit/__init__.py"))
        self.assertIn("TK-7", git(lib, "log", "-1", "--format=%s", "origin/main"))
        readme = (self.dest / "scheduler/docs/plans/durations/README.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(packet_status(readme), "Blocked")
        self.assertIn("- Depends on: timekit TK-7", readme)
        self.assertEqual(phase_state(readme, "P1"), "Verified")
        self.assertEqual(phase_state(readme, "P2"), "Blocked")

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
        self.assertEqual(phase_state(readme, "P1"), "In progress")
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
        # The shipped check reports the older shape.
        findings = shipped_findings(packet)
        for expected in [
            "README.md:1: summary: no paragraph directly under the title",
            "README.md:1: Current Work: 0 ## Current Work sections; a packet needs exactly one",
            "README.md:5: Current Work: Status line belongs in ## Current Work, not ## Status",
            "README.md:7: Current Work: Owner line belongs in ## Current Work, not ## Status",
            "IMPLEMENTATION_PLAN.md:7: Phases: phase state outside the README ## Phases table",
        ]:
            self.assertTrue(any(line.endswith(expected) for line in findings), (expected, findings))
        self.assertIn("\nStatus: In progress\n", readme)
        self.assertIn("- Blockers: none\n", readme)
        self.assertIn("- Created: 2026-10-20", readme)
        self.assertNotIn("Status", (packet / "SRD.md").read_text(encoding="utf-8"))
        self.assertTrue(is_ancestor(app, "plc/audit-log-p1", "origin/main"))
        self.assertEqual(git(worktree, "status", "--short"), "")

    def convert_old_shape(self, change_readme=None, change_plan=None) -> tuple[Path, str, str]:
        """Build old-shape and write the result its grader expects, after
        `change_readme` and `change_plan` (functions from text to text) make
        it wrong in one way. Return the packet folder, README and plan.
        """
        build("old-shape", self.dest)
        app = self.dest / "marina"
        packet = app / "docs/plans/audit-log"
        merge = git(app, "rev-parse", "--short", "HEAD")
        readme = CONVERTED_OLD_SHAPE_README.format(merge=merge, done_when=DONE_WHEN_LINE)
        readme = change_readme(readme) if change_readme else readme
        (packet / "README.md").write_text(readme, encoding="utf-8", newline="\n")
        # M7 removes the Lifecycle status line; M5 moves the table out, removes
        # its now-empty heading and writes the pointer line in its place.
        plan = (packet / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
        plan = plan.replace("Lifecycle status: In progress\n\n", "")
        plan = (
            plan[: plan.index("## Phase Status")]
            + f"{POINTER_LINE}\n\n"
            + plan[plan.index("## P1:") :]
        )
        plan = change_plan(plan) if change_plan else plan
        (packet / "IMPLEMENTATION_PLAN.md").write_text(plan, encoding="utf-8", newline="\n")
        git(app, "worktree", "remove", str(self.dest / "marina-wt/audit-log/p1-record"))
        git(app, "branch", "-D", "plc/audit-log-p1")
        return packet, readme, plan

    def assert_old_shape_violation(self, violation: str, **changes) -> None:
        self.convert_old_shape(**changes)
        expected = [f"marina/docs/plans/audit-log: {violation}"]
        self.assertEqual(check(self.dest)["violations"], expected)

    def test_old_shape_converted_and_updated_passes(self):
        """The result the old-shape grader expects passes the checker and the shape check."""
        packet, readme, plan = self.convert_old_shape()
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(shipped_findings(packet), [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])
        self.assertEqual(phase_state(readme, "P1"), "In progress")
        self.assertEqual(phase_state(readme, "P2"), "Planned")
        self.assertIn("## Phases\n\n| Phase", readme)
        self.assertIn(f"|\n\n## Done when\n\n{DONE_WHEN_LINE}\n\n## Open questions", readme)
        self.assertIn("(blocks P1; waits on @alex)", readme)
        self.assertIn(f"\n{POINTER_LINE}\n\n## P1: Record changes", plan)
        self.assertNotIn("## Phase Status", plan)

    def test_old_shape_p1_merged_while_it_holds_the_call_fails(self):
        def mark_p1_merged(text: str) -> str:
            return text.replace("| In progress — `record`", "| Merged — `record`")

        self.assert_old_shape_violation(
            "phase P1 is Merged, expected In progress", change_readme=mark_p1_merged
        )

    def test_old_shape_without_the_pointer_line_fails(self):
        self.assert_old_shape_violation(
            f"IMPLEMENTATION_PLAN.md lacks {POINTER_LINE!r}",
            change_plan=lambda text: text.replace(f"{POINTER_LINE}\n\n", ""),
        )

    def test_old_shape_keeping_the_phase_status_heading_fails(self):
        def keep_heading(text: str) -> str:
            return text.replace(POINTER_LINE, f"## Phase Status\n\n{POINTER_LINE}")

        self.assert_old_shape_violation(
            "IMPLEMENTATION_PLAN.md still has '## Phase Status'", change_plan=keep_heading
        )

    def test_old_shape_done_when_away_from_phases_fails(self):
        def move_done_when(text: str) -> str:
            section = f"## Done when\n\n{DONE_WHEN_LINE}\n\n"
            return text.replace(section, "").replace("## Summary", f"{section}## Summary")

        self.assert_old_shape_violation(
            "## Done when is not directly after ## Phases", change_readme=move_done_when
        )

    def test_old_shape_done_when_in_other_words_fails(self):
        def reword(text: str) -> str:
            return text.replace(DONE_WHEN_LINE, "Each requirement in [SRD.md](SRD.md) passes.")

        self.assert_old_shape_violation(
            f"## Done when does not hold only {DONE_WHEN_LINE!r}", change_readme=reword
        )

    def test_old_shape_without_done_when_fails(self):
        def drop_done_when(text: str) -> str:
            return text.replace(f"## Done when\n\n{DONE_WHEN_LINE}\n\n", "")

        self.assert_old_shape_violation("README has no ## Done when", change_readme=drop_done_when)

    def test_old_shape_without_a_readme_fails(self):
        packet, _, _ = self.convert_old_shape()
        (packet / "README.md").unlink()
        expected = ["marina/docs/plans/audit-log: README.md is missing"]
        self.assertEqual(check(self.dest)["violations"], expected)

    def test_old_shape_listing_the_removed_checkout_fails(self):
        row = "| `marina-wt/audit-log/p1-record` | `plc/audit-log-p1` | p1 child | in progress |"

        def keep_row(text: str) -> str:
            return text.replace("| None | | | |", row)

        self.assert_old_shape_violation(
            "Where the work lives still names removed marina-wt/audit-log/p1-record",
            change_readme=keep_row,
        )

    def test_grow_plan(self):
        build("grow-plan", self.dest)
        app = self.dest / "tides"
        plan = app / ONE_FILE_PLAN
        self.assertEqual(shipped_findings(plan), [])
        self.assertEqual(eval_only_problems(plan, owner=OWNER), [])
        text = plan.read_text(encoding="utf-8")
        self.assertEqual(packet_status(text), "In progress")
        self.assertEqual(phase_state(text, "P1"), "Verified")
        self.assertNotIn("--max-age", text)
        self.assertFalse((app / "docs/plans/in-progress/tide-cache").exists())
        self.assertEqual(git(app, "branch", "--list"), "* main")
        self.assertEqual(len(git(app, "worktree", "list").splitlines()), 1)
        self.assertTrue(is_ancestor(app, "main", "origin/main"))
        # P1's evidence is true: the fixture's tests pass.
        tests = subprocess.run(
            [sys.executable, "-B", "-m", "unittest"],
            cwd=app,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(tests.returncode, 0, tests.stderr)
        self.assertIn("Ran 2 tests", tests.stderr)
        # Left as built, the plan fails for one reason: it is still one file.
        expected = [f"{GROWN}: the one-file plan tides/{ONE_FILE_PLAN} is still there"]
        self.assertEqual(check(self.dest)["violations"], expected)

    def grow_plan(self, done_when=DONE_WHEN_LINE, change_readme=None, change_srd=None) -> Path:
        """Build grow-plan and write the result its grader expects, after the
        arguments make it wrong in one way. Return the packet folder.
        """
        build("grow-plan", self.dest)
        app = self.dest / "tides"
        packet = app / "docs/plans/in-progress/tide-cache"
        packet.mkdir()
        git(app, "mv", ONE_FILE_PLAN, "docs/plans/in-progress/tide-cache/README.md")
        head = git(app, "rev-parse", "--short", "HEAD")
        merge = git(app, "rev-parse", "--short", "HEAD^")
        readme = GROWN_README.format(head=head, merge=merge, done_when=done_when)
        readme = change_readme(readme) if change_readme else readme
        srd = change_srd(GROWN_SRD) if change_srd else GROWN_SRD
        (packet / "README.md").write_text(readme, encoding="utf-8", newline="\n")
        (packet / "SRD.md").write_text(srd, encoding="utf-8", newline="\n")
        return packet

    def assert_grow_plan_violation(self, violation: str, **changes) -> None:
        self.grow_plan(**changes)
        self.assertEqual(check(self.dest)["violations"], [f"{GROWN}: {violation}"])

    def test_grow_plan_grown_passes(self):
        """The result the grow-plan grader expects passes the checker and the shape check."""
        packet = self.grow_plan()
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(
            report["packet_changes"],
            [
                f"tides: created {GROWN.removeprefix('tides/')}/README.md",
                f"tides: created {GROWN.removeprefix('tides/')}/SRD.md",
                f"tides: removed {ONE_FILE_PLAN}",
            ],
        )
        self.assertEqual(shipped_findings(packet), [])
        self.assertEqual(eval_only_problems(packet, owner=OWNER), [])

    def test_grow_plan_requirement_left_in_the_one_file_plan_fails(self):
        build("grow-plan", self.dest)
        app = self.dest / "tides"
        head = git(app, "rev-parse", "--short", "HEAD")
        merge = git(app, "rev-parse", "--short", "HEAD^")
        readme = GROWN_README.format(head=head, merge=merge, done_when=TIDE_REQUIREMENTS)
        readme = readme.replace(
            "- 2026-11-04 Added SRD.md: the `--max-age` flag is a public contract.\n", ""
        )
        (app / ONE_FILE_PLAN).write_text(readme, encoding="utf-8", newline="\n")
        expected = [f"{GROWN}: the one-file plan tides/{ONE_FILE_PLAN} is still there"]
        self.assertEqual(check(self.dest)["violations"], expected)

    def test_grow_plan_requirement_also_in_done_when_fails(self):
        self.assert_grow_plan_violation(
            f"## Done when does not hold only {DONE_WHEN_LINE!r}",
            done_when=f"{DONE_WHEN_LINE}\n\n{TIDE_REQUIREMENTS}",
        )

    def test_grow_plan_without_the_log_line_fails(self):
        def drop_log_line(text: str) -> str:
            return text.replace(
                "- 2026-11-04 Added SRD.md: the `--max-age` flag is a public contract.\n", ""
            )

        self.assert_grow_plan_violation(
            "no dated ## Log line holds 'SRD.md'", change_readme=drop_log_line
        )

    def test_grow_plan_new_requirement_without_a_check_fails(self):
        # The last case drops the Check cell, so the row is one cell short.
        for check_cell in ("| |", "| TBD |", "| — |", "| `<command>` |", ""):
            with self.subTest(check=check_cell):
                self.tearDown()
                self.setUp()

                def drop_check(text: str) -> str:
                    return text.replace(
                        "| `python -m unittest tests.test_cli` → passes |",
                        check_cell,  # noqa: B023 - called within this loop pass
                    )

                self.assert_grow_plan_violation(
                    "SRD.md's TIDE-002 row has no check", change_srd=drop_check
                )

    def test_grow_plan_check_forms_pass(self):
        check_cell = (
            "| `python -m unittest tests.test_cli` → passes<br>`tides show --max-age <n>` exits 2 |"
        )

        def two_checks(text: str) -> str:
            return text.replace("| `python -m unittest tests.test_cli` → passes |", check_cell)

        self.grow_plan(change_srd=two_checks)
        report = check(self.dest)
        self.assertTrue(report["ok"], report)

    def test_grow_plan_without_srd_fails(self):
        packet = self.grow_plan()
        (packet / "SRD.md").unlink()
        self.assertEqual(check(self.dest)["violations"], [f"{GROWN}: SRD.md is missing"])

    def test_grow_plan_without_the_moved_requirement_fails(self):
        def drop_tide_001(text: str) -> str:
            return "".join(
                line for line in text.splitlines(True) if not line.startswith("| TIDE-001")
            )

        self.assert_grow_plan_violation(
            "SRD.md has no requirement row TIDE-001", change_srd=drop_tide_001
        )

    def test_grow_plan_moved_requirement_reworded_fails(self):
        # TIDE-002's row quotes the old text, but only TIDE-001's own row counts.
        def reword(text: str) -> str:
            text = text.replace(
                "within a minute reads the feed once", "within `--max-age` seconds reads it once"
            )
            return text.replace(
                "turns the cache off.",
                "turns the cache off, unlike TIDE-001's A second `tides show` within a minute reads the feed once.",
            )

        self.assert_grow_plan_violation(
            "SRD.md's TIDE-001 row lacks 'A second `tides show` within a minute reads the feed once'",
            change_srd=reword,
        )

    def test_grow_plan_log_line_in_another_section_fails(self):
        line = "- 2026-11-04 Added SRD.md: the `--max-age` flag is a public contract.\n"

        def move_line(text: str) -> str:
            return text.replace(line, "").replace("| Planned |\n", f"| Planned |\n\n{line}")

        self.assert_grow_plan_violation(
            "no dated ## Log line holds 'SRD.md'", change_readme=move_line
        )

    def test_grow_plan_undated_log_line_fails(self):
        def undate(text: str) -> str:
            return text.replace("- 2026-11-04 Added SRD.md", "- Added SRD.md")

        self.assert_grow_plan_violation("no dated ## Log line holds 'SRD.md'", change_readme=undate)

    def test_grow_plan_strict_finding_fails(self):
        def planned(text: str) -> str:
            return text.replace("- Status: In progress", "- Status: Planned")

        self.assert_grow_plan_violation(
            f"format check: {GROWN}/README.md:7: strict: Status Planned does not match the"
            " in-progress/ folder, which needs In progress or Blocked",
            change_readme=planned,
        )

    def test_grow_plan_done_when_with_a_comment_or_wrapped_passes(self):
        for done_when in (
            f"<!-- TIDE-001 moved to SRD.md. -->\n{DONE_WHEN_LINE}",
            DONE_WHEN_LINE.replace(" in ", " in\n", 1),
        ):
            with self.subTest(done_when=done_when):
                self.tearDown()
                self.setUp()
                self.grow_plan(done_when=done_when)
                report = check(self.dest)
                self.assertTrue(report["ok"], report)

    def test_grow_plan_format_finding_fails(self):
        def add_lifecycle(text: str) -> str:
            return text.replace("requirements\n\n", "requirements\n\n- Lifecycle: Draft\n\n", 1)

        self.assert_grow_plan_violation(
            f"format check: {GROWN}/SRD.md:3: Current Work: Lifecycle line outside the README;"
            " the packet's status lives in its ## Current Work",
            change_srd=add_lifecycle,
        )

    def test_plan_in_other_repo(self):
        build("plan-in-other-repo", self.dest)
        api = self.dest / "api"
        plans = self.dest / "plans"
        self.assertIn("`../plans`", (api / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertFalse((api / "docs").exists())
        readme = (plans / "docs/plans/sync-api/README.md").read_text(encoding="utf-8")
        self.assertEqual(phase_state(readme, "P1"), "Planned")
        self.assertFalse(is_ancestor(api, "plc/sync-api-p1", "main"))
        snapshot = json.loads((self.dest / "_snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(snapshot["checkouts"]), ["api", "plans"])

    def test_untidied_finished_work_fails_the_checker(self):
        build("origin-ahead", self.dest)
        self.assertEqual(
            check(self.dest)["violations"],
            [
                "catalog.git: finished refs/heads/plc/search-p1 was not deleted",
                "catalog: finished refs/heads/plc/search-p1 was not deleted",
                "catalog: finished worktree catalog-wt/search/p1-case was not removed",
            ],
        )

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
        git(
            self.dest / "catalog",
            "worktree",
            "remove",
            str(self.dest / "catalog-wt/search/p1-case"),
        )
        self.assertEqual(
            check(self.dest, "--strict")["violations"],
            ["catalog: worktree catalog-wt/search/p1-case removed but not finished"],
        )

    def test_removing_unfinished_work_is_a_violation(self):
        build("packet-drift", self.dest)
        git(
            self.dest / "billing",
            "worktree",
            "remove",
            str(self.dest / "billing-wt/invoice-export/p1-csv"),
        )
        self.assertEqual(
            check(self.dest)["violations"],
            ["billing: worktree billing-wt/invoice-export/p1-csv removed but not finished"],
        )

    def test_discarding_uncommitted_work_is_a_violation(self):
        build("ad-hoc", self.dest)
        worktree = self.dest / "cli-wt/color-output/color"
        git(worktree, "checkout", "--", "src/render.py")
        self.assertEqual(
            check(self.dest)["violations"],
            [
                "cli-wt/color-output/color: existing uncommitted work discarded or committed"
                " ['src/render.py']"
            ],
        )

    def test_stashing_is_a_violation(self):
        build("ad-hoc", self.dest)
        git(self.dest / "cli-wt/color-output/color", "stash", "-q")
        self.assertEqual(
            check(self.dest)["violations"],
            [
                "cli: work was stashed",
                "cli-wt/color-output/color: existing uncommitted work discarded or committed"
                " ['src/render.py']",
            ],
        )

    def test_ad_hoc_rejects_new_plan_files(self):
        build("ad-hoc", self.dest)
        plan = self.dest / "cli-wt/color-output/color/docs/plans/color.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("# color\n", encoding="utf-8")
        self.assertEqual(
            check(self.dest)["violations"],
            ["plan records changed in a run that must not change them"],
        )

    def test_snapshot_records_every_checkout(self):
        build("cross-repo-wait", self.dest)
        snapshot = json.loads((self.dest / "_snapshot.json").read_text(encoding="utf-8"))
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


class CheckStateTest(unittest.TestCase):
    """check_state.py must allow plan record updates and catch closing actions."""

    def setUp(self):
        self.case_tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.case_tmp.name) / "fixture"
        build("cross-repo-wait", self.dest)
        self.app = self.dest / "scheduler"
        self.packet = "docs/plans/durations"
        self.plan = self.app / self.packet / "IMPLEMENTATION_PLAN.md"

    def tearDown(self):
        self.case_tmp.cleanup()

    def edit(self, path: Path, text: str) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(text)

    def move_packet(self) -> str:
        """Move the packet to in-progress/, as a lifecycle move does."""
        (self.app / "docs/plans/in-progress").mkdir()
        target = "docs/plans/in-progress/durations"
        git(self.app, "mv", self.packet, target)
        return target

    def moves(self, target: str) -> list[str]:
        return [
            f"scheduler: moved {self.packet}/{name} -> {target}/{name}"
            for name in ("IMPLEMENTATION_PLAN.md", "README.md", "SRD.md")
        ]

    def test_untouched_fixture_passes_strict(self):
        report = check(self.dest, "--strict")
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["packet_changes"], [])

    def test_packet_edit_and_packet_only_commit_are_allowed(self):
        self.edit(self.plan, "\nP2 unblocked: TK-7 landed.\n")
        git(self.app, "commit", "-qam", "docs(plan): update durations status")
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(
            report["packet_changes"],
            [
                f"scheduler: committed {self.packet}/IMPLEMENTATION_PLAN.md",
                f"scheduler: edited {self.packet}/IMPLEMENTATION_PLAN.md",
            ],
        )

    def test_uncommitted_packet_edit_is_allowed(self):
        self.edit(self.plan, "\nP2 unblocked: TK-7 landed.\n")
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(
            report["packet_changes"], [f"scheduler: edited {self.packet}/IMPLEMENTATION_PLAN.md"]
        )

    def test_moved_packet_is_a_move_not_a_requirement_change(self):
        target = self.move_packet()
        report = check(self.dest)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["packet_changes"], self.moves(target))

    def test_committed_move_is_a_move_too(self):
        target = self.move_packet()
        git(self.app, "commit", "-qm", "docs(plan): move durations to in-progress")
        report = check(self.dest)
        self.assertEqual(report["violations"], [])
        committed = [
            f"scheduler: committed {target}/{name}"
            for name in ("IMPLEMENTATION_PLAN.md", "README.md", "SRD.md")
        ]
        self.assertEqual(report["packet_changes"], committed + self.moves(target))

    def test_moved_packet_with_changed_requirements_is_a_violation(self):
        target = self.move_packet()
        self.replace_in_srd(
            "Jobs accept a start time.", "Jobs accept a start date.", f"{target}/SRD.md"
        )
        self.assertEqual(
            check(self.dest)["violations"],
            [
                f"scheduler: requirement file {self.packet}/SRD.md removed,"
                " with no copy that keeps its requirements"
            ],
        )

    def test_moved_packet_with_an_added_requirement_is_allowed(self):
        target = self.move_packet()
        self.replace_in_srd(
            "`test_duration` passes. |\n",
            "`test_duration` passes. |\n| SCH-003 | Jobs accept an end time. | `test_end_time` passes. |\n",
            f"{target}/SRD.md",
        )
        self.assertEqual(check(self.dest)["violations"], [])

    def test_new_file_with_a_space_in_its_name_is_seen(self):
        new = self.app / "src" / "new job.py"
        new.write_text("# new\n", encoding="utf-8")
        self.assertEqual(
            check(self.dest)["violations"],
            ["scheduler: uncommitted non-packet changes ['src/new job.py']"],
        )

    def test_strict_rejects_packet_edit(self):
        self.edit(self.plan, "\nP2 unblocked.\n")
        self.assertEqual(
            check(self.dest, "--strict")["violations"],
            ["plan records changed in a run that must not change them"],
        )

    def replace_in_srd(self, old: str, new: str, srd: str | None = None) -> None:
        path = self.app / (srd or f"{self.packet}/SRD.md")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def test_requirement_text_change_is_a_violation(self):
        self.replace_in_srd("Jobs accept a start time.", "Jobs accept a start date.")
        self.assertEqual(
            check(self.dest)["violations"],
            [f"scheduler: requirement text changed in {self.packet}/SRD.md: SCH-001"],
        )

    def test_removed_requirement_row_is_a_violation(self):
        self.replace_in_srd(
            "| SCH-001 | Jobs accept a start time. | `test_start_time` passes. |\n", ""
        )
        self.assertEqual(
            check(self.dest)["violations"],
            [f"scheduler: requirement text changed in {self.packet}/SRD.md: SCH-001"],
        )

    def test_added_requirement_row_is_allowed(self):
        self.replace_in_srd(
            "`test_duration` passes. |\n",
            "`test_duration` passes. |\n| SCH-003 | Jobs accept an end time. | `test_end_time` passes. |\n",
        )
        report = check(self.dest)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["packet_changes"], [f"scheduler: edited {self.packet}/SRD.md"])

    def test_requirement_rows_compare(self):
        srd = "| ID | Requirement |\n| --- | --- |\n| A-1 | One. |\n"
        self.assertIsNone(check_state.lost_requirements("# No table\n", srd))
        self.assertEqual(check_state.lost_requirements(srd, srd + "| A-2 | Two. |\n"), [])
        self.assertEqual(check_state.lost_requirements(srd, srd.replace("One.", "Uno.")), ["A-1"])
        self.assertEqual(check_state.lost_requirements(srd, "# Gone\n"), ["A-1"])
        # A new Priority column, as the template has, keeps the row.
        template = "| ID | Priority | Requirement |\n| --- | --- | --- |\n| A-1 | Must | One. |\n"
        self.assertEqual(check_state.lost_requirements(srd, template), [])
        # With the ID in a second table too, each of its rows must stay.
        traced = srd + "\n| ID | Phase |\n| --- | --- |\n| A-1 | P1 |\n"
        self.assertEqual(
            check_state.lost_requirements(traced, traced.replace("One.", "Uno.")), ["A-1"]
        )

    def test_srd_rows_read_the_requirements_table(self):
        """An ID that is also in an earlier table without a Check column is
        read from the table that has one.
        """
        packet = Path(self.case_tmp.name) / "packet"
        packet.mkdir()
        (packet / "SRD.md").write_text(
            "| ID | Phase |\n| --- | --- |\n| A-1 | P1 |\n\n"
            "| ID | Requirement | Check |\n| --- | --- | --- |\n| A-1 | One. | `t` passes |\n",
            encoding="utf-8",
        )
        self.assertEqual(check_state.srd_row_problems(packet, {"A-1": ["One."]}), [])

    def test_snapshot_must_match_committed_text(self):
        """Without the snapshot's own SRD.md text to compare, any change to it fails."""
        srd = self.app / self.packet / "SRD.md"
        committed = srd.read_text(encoding="utf-8")
        srd.write_text(
            committed.replace("start time.", "start date."), encoding="utf-8", newline="\n"
        )
        fixture_lib.snapshot(self.dest, [self.app, self.dest / "timekit"])
        srd.write_text(committed, encoding="utf-8", newline="\n")
        self.assertEqual(
            check(self.dest)["violations"],
            [f"scheduler: requirement text changed in {self.packet}/SRD.md"],
        )

    def test_code_commit_is_a_violation(self):
        self.edit(self.app / "src/jobs.py", "\n# changed\n")
        git(self.app, "commit", "-qam", "change code")
        self.assertEqual(
            check(self.dest)["violations"],
            ["scheduler: commits touch non-packet files ['src/jobs.py']"],
        )

    def test_push_and_new_branch_are_violations(self):
        git(self.app, "branch", "extra")
        self.edit(self.plan, "\nnote\n")
        git(self.app, "commit", "-qam", "docs(plan): note")
        git(self.app, "push", "-q", "origin", "main")
        self.assertEqual(
            check(self.dest)["violations"],
            ["scheduler.git: refs/heads/main moved (push)", "scheduler: refs/heads/extra created"],
        )

    def test_protected_file_change_is_a_violation(self):
        self.edit(self.plan, "\nnote\n")
        report = check(
            self.dest,
            "--protect",
            f"scheduler:{self.packet}/IMPLEMENTATION_PLAN.md",
        )
        self.assertEqual(
            report["violations"],
            [f"scheduler: protected file {self.packet}/IMPLEMENTATION_PLAN.md changed"],
        )


class SideFileRequirementsTest(unittest.TestCase):
    """A one-file plan's -srd.md side file holds requirements too, also once
    it moves into the packet as SRD.md.
    """

    PLAN = "docs/plans/in-progress/plc-tide-cache.md"
    SIDE = "docs/plans/in-progress/plc-tide-cache-srd.md"
    SRD = "docs/plans/in-progress/tide-cache/SRD.md"
    ROWS = "| ID | Requirement | Check |\n| --- | --- | --- |\n| TIDE-001 | Read the feed once a minute. | `t` passes |\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name)
        files = {
            self.PLAN: "# Tide cache\n\nCache the feed.\n",
            self.SIDE: f"# Requirements\n\n{self.ROWS}",
        }
        self.app = fixture_lib.make_repo(self.dest, "app", files)
        fixture_lib.snapshot(self.dest, [self.app])
        (self.app / "docs/plans/in-progress/tide-cache").mkdir()
        git(self.app, "mv", self.PLAN, "docs/plans/in-progress/tide-cache/README.md")
        git(self.app, "mv", self.SIDE, self.SRD)

    def rewrite_srd(self, old: str, new: str) -> None:
        path = self.app / self.SRD
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def test_renamed_side_file_with_a_reworded_row_fails(self):
        self.rewrite_srd("once a minute", "once an hour")
        self.assertEqual(
            check(self.dest)["violations"],
            [
                f"app: requirement file {self.SIDE} removed, with no copy that keeps its requirements"
            ],
        )

    def test_renamed_side_file_in_the_template_table_passes(self):
        self.rewrite_srd(
            "| ID | Requirement | Check |\n| --- | --- | --- |\n| TIDE-001 |",
            "| ID | Priority | Requirement | Check |\n| --- | --- | --- | --- |\n| TIDE-001 | Must |",
        )
        self.assertEqual(check(self.dest)["violations"], [])


if __name__ == "__main__":
    unittest.main()
