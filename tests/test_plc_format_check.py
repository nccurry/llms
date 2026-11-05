"""Tests for plc-planning's format check, skills/plc-planning/scripts/format_check.py."""

import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "plc-planning"
SCRIPT = SKILL / "scripts" / "format_check.py"
DATA = Path(__file__).resolve().parent / "plc_format_check"
PEOPLE = ["--people", "Alex Kim=alex", "sam=sam"]


def load_format_check():
    """Import the script by path without writing a bytecode cache beside it."""
    spec = importlib.util.spec_from_file_location("format_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


fc = load_format_check()

GAPS = "packets/planned/gaps/README.md"
BAD = "packets/in-progress/bad/README.md"
FIRST_KEYS = "Current Work: Status, Owner and Last updated must come first, in that order"
OUTSIDE = "Phases: phase state outside the README ## Phases table"
NO_EVIDENCE = "strict: Verified phase has no evidence after ' — '"
NO_BLOCKER = "strict: Status is Blocked, but the Blocker line is missing or None"
NOT_FINISHED = "phase in a completed/ packet, which allows only Verified, Live, Deferred or Dropped"
TWO_HOMES = "packets/planned/two-requirement-homes"
NO_POINTER = "Done when: no line points to SRD.md, which holds the requirements"
NO_DONE_WHEN = "Done when: no ## Done when section; with SRD.md it holds only the line pointing there"
ITEMS = "Done when: {} items; with SRD.md it holds only the line pointing there"
IN_SRD = "Done when: {} is in SRD.md's requirements table; delete it here, since SRD.md holds the requirements"
LIFECYCLE_OUTSIDE = (
    "Current Work: Lifecycle line outside the README; the packet's status lives in its ## Current Work"
)
POINTER = "The requirements and their checks are in [SRD.md](SRD.md)."

DEFAULT_FINDINGS = [
    f"{GAPS}:5: {FIRST_KEYS}",
    f"{GAPS}:5: Current Work: no Status line",
    f"{GAPS}:9: Current Work: Owner names sam without @sam",
    f"{GAPS}:5: Current Work: no Last updated line",
    f"{GAPS}:16: Phases: State does not start with a phase state word: (empty)",
    f"{GAPS}:17: Phases: row has 2 cells, but the header has 3",
    "packets/planned/plc-harbor-alerts-plan.md:1: Log: no ## Log section",
    "packets/planned/plc-harbor-cache.md:1: Log: no ## Log section",
    f"packets/planned/two-phase-tables/IMPLEMENTATION_PLAN.md:3: {OUTSIDE}",
    f"{TWO_HOMES}/README.md:17: {ITEMS.format(2)}",
    f"{TWO_HOMES}/README.md:20: {IN_SRD.format('REQ-002')}",
    f"{TWO_HOMES}/SRD.md:3: {LIFECYCLE_OUTSIDE}",
    f"{TWO_HOMES}/SADD.md:3: {LIFECYCLE_OUTSIDE}",
    f"{BAD}:1: summary: no paragraph directly under the title",
    f"{BAD}:3: Current Work: 13 keys; at most 12 are allowed",
    f"{BAD}:6: Current Work: Owner names no @handle",
    f"{BAD}:6: Current Work: Owner names Alex Kim without @alex",
    f"{BAD}:1: Log: no ## Log section",
    "packets/in-progress/no-readme: packet folder has no README.md",
]

STRICT_FINDINGS = [
    f"packets/planned/blocked/README.md:7: {NO_BLOCKER}",
    f"{GAPS}:5: {FIRST_KEYS}",
    f"{GAPS}:5: Current Work: no Status line",
    f"{GAPS}:9: Current Work: Owner names sam without @sam",
    f"{GAPS}:5: Current Work: no Last updated line",
    f"{GAPS}:16: Phases: State does not start with a phase state word: (empty)",
    f"{GAPS}:17: Phases: row has 2 cells, but the header has 3",
    "packets/planned/plc-harbor-alerts-plan.md:1: Log: no ## Log section",
    "packets/planned/plc-harbor-cache.md:1: Log: no ## Log section",
    "packets/planned/superseded/README.md:7: strict: Status Superseded does not match the planned/ folder,"
    " which needs Planned or Blocked",
    "packets/planned/superseded/README.md:7: strict: Superseded note does not start with a reason word",
    f"packets/planned/two-phase-tables/IMPLEMENTATION_PLAN.md:3: {OUTSIDE}",
    f"{TWO_HOMES}/README.md:17: {ITEMS.format(2)}",
    f"{TWO_HOMES}/README.md:20: {IN_SRD.format('REQ-002')}",
    f"{TWO_HOMES}/SRD.md:3: {LIFECYCLE_OUTSIDE}",
    f"{TWO_HOMES}/SADD.md:3: {LIFECYCLE_OUTSIDE}",
    f"{BAD}:1: summary: no paragraph directly under the title",
    f"{BAD}:3: Current Work: 13 keys; at most 12 are allowed",
    f"{BAD}:6: Current Work: Owner names no @handle",
    f"{BAD}:6: Current Work: Owner names Alex Kim without @alex",
    f"{BAD}:5: strict: Status Planned does not match the in-progress/ folder, which needs In progress or Blocked",
    f"{BAD}:1: Log: no ## Log section",
    f"{BAD}:23: {NO_EVIDENCE}",
    f"{BAD}:24: strict: Dropped note does not start with a reason word",
    "packets/in-progress/no-readme: packet folder has no README.md",
]

FINISHED = [f"packets/completed/finished/README.md:17: strict: Merged {NOT_FINISHED}"]

# A packet with no findings, even in strict mode in planned/. Line 7 is
# Status, 8 Owner, 9 Last updated, 10 Blocker, 12 ## Phases, 14 the table
# header, 16 the P1 row and 18 ## Log.
VALID = """\
# Harbor retry cap

Stop retries after three attempts.

## Current Work

- Status: Planned
- Owner: @alex
- Last updated: 2026-11-03
- Blocker: None

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | Cap retries | | Planned |

## Log

- 2026-11-03 Created.
"""
TABLE = "| Phase | Name | Owner | State |\n| --- | --- | --- | --- |\n| P1 | Cap retries | | Planned |"
R = "planned/sample/README.md"
# An SRD.md with two requirements, one with its ID in bold.
SRD = """\
# Requirements

| ID | Priority | Requirement | Check |
| --- | --- | --- | --- |
| REQ-001 | Must | Stop after three attempts. | `task test` → passes |
| **REQ-002** | Must | Log the third failure. | `task test` → passes |
"""


def edit(old, new, text=VALID):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def with_done_when(body, text=VALID):
    """A README with `## Done when` holding body, just before `## Log`, so the
    section's heading is line 18 and its body starts on line 20."""
    return edit("## Log", f"## Done when\n\n{body}\n\n## Log", text)


# VALID with the pointer line a packet with SRD.md needs.
POINTED = with_done_when(POINTER)


def run(*args, cwd=DATA, env=None):
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        encoding="utf-8",
    )
    return result.returncode, result.stdout.splitlines(), result.stderr


def fill(text):
    """Replace each template placeholder with a neutral value."""
    text = text.replace("<YYYY-MM-DD>", "2026-11-03").replace("@<handle>", "@alex")
    text = text.replace("!<number>", "!12")
    return re.sub(r"<(?!!)[^<>\n]+>", "sample", text)


def without_note(text):
    """A template without the HTML comment before its title."""
    return re.sub(r"\A<!--.*?-->\n\n", "", text, flags=re.DOTALL)


class PacketRulesTest(unittest.TestCase):
    """Each rule, on a small packet written for it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def check(self, readme=VALID, folder="planned", name="sample", plan=None, people=(), lifecycle=None, files=None):
        packet = self.root / folder / name
        packet.mkdir(parents=True, exist_ok=True)
        (packet / "README.md").write_text(readme, encoding="utf-8")
        if plan is not None:
            files = {**(files or {}), "IMPLEMENTATION_PLAN.md": plan}
        for file_name, text in (files or {}).items():
            (packet / file_name).write_text(text, encoding="utf-8")
        prefix = self.root.as_posix() + "/"
        found = fc.check_packet(packet, people, strict=True, lifecycle=lifecycle)
        return [line.removeprefix(prefix) for line in found]

    def test_valid_packet(self):
        self.assertEqual(self.check(), [])

    def test_current_work_count(self):
        message = "Current Work: {} ## Current Work sections; a packet needs exactly one"
        self.assertEqual(self.check(edit("## Current Work", "## Work")), [f"{R}:1: {message.format(0)}"])
        second = edit("## Log", "## Current Work\n\n- Status: Planned\n\n## Log")
        self.assertEqual(self.check(second), [f"{R}:1: {message.format(2)}"])

    def test_status_lines_under_old_headings(self):
        old = "## Status\n\nStatus: In progress\n- **Owner:** Sam\nUpdated: 2026-10-01\nNote: kept\n\n"
        old += "## Lifecycle\n\n- State: Active\n\n## Log"
        self.assertEqual(self.check(edit("## Log", old)), [
            f"{R}:20: Current Work: Status line belongs in ## Current Work, not ## Status",
            f"{R}:21: Current Work: Owner line belongs in ## Current Work, not ## Status",
            f"{R}:22: Current Work: Updated line belongs in ## Current Work, not ## Status",
            f"{R}:27: Current Work: State line belongs in ## Current Work, not ## Lifecycle",
        ])

    def test_old_headings_flag_only_status_values(self):
        not_status = "## Status codes\n\n- Status: 404 when the file is missing\n- Owner: Sam\n\n"
        not_status += "## Lifecycle\n\n- Updated: when the owner signs off\n\n## Log"
        self.assertEqual(self.check(edit("## Log", not_status)), [])
        for heading in ("Status (2026-10)", "Status — 2026-10-01", "Current status"):
            owner = edit("## Log", f"## {heading}\n\n- Owners: Sam\n\n## Log")
            message = f"Current Work: Owners line belongs in ## Current Work, not ## {heading}"
            self.assertEqual(self.check(owner), [f"{R}:20: {message}"])

    def test_status_word(self):
        unknown = edit("- Status: Planned", "- Status: Waiting")
        message = "Current Work: Status does not start with a packet status word: Waiting"
        self.assertEqual(self.check(unknown), [f"{R}:7: {message}"])

    def test_owner(self):
        no_owner = edit("- Owner: @alex\n", "")
        self.assertEqual(self.check(no_owner), [f"{R}:5: {FIRST_KEYS}", f"{R}:5: Current Work: no Owner line"])
        for owner in ("Platform team", "alex@example.com"):
            no_handle = edit("- Owner: @alex", f"- Owner: {owner}")
            self.assertEqual(self.check(no_handle), [f"{R}:8: Current Work: Owner names no @handle"])
        self.assertEqual(self.check(edit("- Owner: @alex", "- Owner: Platform team (@alex, @sam)")), [])

    def test_people_match_whole_handles(self):
        people = [("Al", "al")]
        partial = edit("- Owner: @alex", "- Owner: Al (@alsmith)")
        self.assertEqual(self.check(partial, people=people), [f"{R}:8: Current Work: Owner names Al without @al"])
        self.assertEqual(self.check(edit("- Owner: @alex", "- Owner: Al (@al)"), people=people), [])
        self.assertEqual(self.check(edit("- Owner: @alex", "- Owner: Al (@al)."), people=people), [])
        for longer in ("@al.smith", "@al-b"):
            owner = edit("- Owner: @alex", f"- Owner: Al ({longer})")
            self.assertEqual(self.check(owner, people=people), [f"{R}:8: Current Work: Owner names Al without @al"])
        dotted = edit("- Owner: @alex", "- Owner: Alex (@alex.b)")
        message = "Current Work: Owner names Alex without @alex"
        self.assertEqual(self.check(dotted, people=[("Alex", "alex")]), [f"{R}:8: {message}"])

    def test_people_handles_may_start_with_at(self):
        named = edit("- Owner: @alex", "- Owner: Alex Kim (@alex)")
        self.assertEqual(self.check(named, people=[("Alex Kim", "@alex")]), [])
        unnamed = edit("- Owner: @alex", "- Owner: Alex Kim, @sam")
        message = "Current Work: Owner names Alex Kim without @alex"
        self.assertEqual(self.check(unnamed, people=[("Alex Kim", "@alex")]), [f"{R}:8: {message}"])

    def test_at_most_twelve_keys(self):
        extra = "".join(f"- Note {letter}: x\n" for letter in "abcdefgh")
        self.assertEqual(self.check(edit("- Blocker: None\n", "- Blocker: None\n" + extra)), [])
        thirteen = edit("- Blocker: None\n", "- Blocker: None\n" + extra + "- Note i: x\n")
        self.assertEqual(self.check(thirteen), [f"{R}:5: Current Work: 13 keys; at most 12 are allowed"])

    def test_last_updated_starts_with_a_date(self):
        message = "Current Work: Last updated does not start with a YYYY-MM-DD date"
        for value in ("today, 2026-11-03", "2026-11, later"):
            late_date = edit("- Last updated: 2026-11-03", f"- Last updated: {value}")
            self.assertEqual(self.check(late_date), [f"{R}:9: {message}"])

    def test_bold_keys(self):
        bold = edit("- Status: Planned", "- **Status:** Planned")
        bold = edit("- Owner: @alex", "- **Owner**: @alex", bold)
        self.assertEqual(self.check(bold), [])

    def test_older_words(self):
        older = edit("- Status: Planned", "- Status: Draft")
        self.assertEqual(self.check(edit("| Planned |", "| Not started |", older)), [])
        self.assertEqual(self.check(edit("| Planned |", "| Done |")), [f"{R}:16: {NO_EVIDENCE}"])
        self.assertEqual(self.check(edit("| Planned |", "| Done — task test → passed @ abc1234 |")), [])

    def test_phases_table_needs_a_state_column(self):
        no_state = edit(TABLE, "| Phase | Name | Owner |\n| --- | --- | --- |\n| P1 | Cap retries | |")
        self.assertEqual(self.check(no_state), [f"{R}:14: Phases: the ## Phases table has no State column"])

    def test_note_rows_are_skipped(self):
        for first_cell in ("", "—", "-"):
            note_row = f"| P1 | Cap retries | | Planned |\n| {first_cell} | See the notes below | | |"
            self.assertEqual(self.check(edit("| P1 | Cap retries | | Planned |", note_row)), [])

    def test_phases_section_needs_a_phase_table(self):
        wrong_first = edit(TABLE, "| Step | State |\n| --- | --- |\n| P1 | Planned |")
        message = "Phases: the ## Phases table's first column is not Phase"
        self.assertEqual(self.check(wrong_first), [f"{R}:14: {message}"])
        self.assertEqual(self.check(edit(TABLE + "\n", "")), [f"{R}:12: Phases: ## Phases has no table"])

    def test_phase_tables_outside_phases(self):
        self.assertEqual(self.check(edit("## Phases", "## Plan")), [
            f"{R}:14: {OUTSIDE}",
            f"{R}:14: Phases: phase table is not under ## Phases",
        ])
        extra = "## Notes\n\n| Phase | Goal | Status |\n| --- | --- | --- |\n| P1 | Cap | Planned |\n\n"
        extra += "| Phase | Goal |\n| --- | --- |\n| P1 | Cap |\n\n## Log"
        self.assertEqual(self.check(edit("## Log", extra)), [f"{R}:20: {OUTSIDE}"])

    def test_phase_state_in_the_implementation_plan(self):
        old_shape = "# Plan\n\n| Phase | Requirements | Implementation | Verification | Delivery |\n"
        old_shape += "| --- | --- | --- | --- | --- |\n| P1 | REQ-001 | Merged | Not run | Pending |\n"
        self.assertEqual(self.check(plan=old_shape), [f"planned/sample/IMPLEMENTATION_PLAN.md:3: {OUTSIDE}"])
        details = "# Plan\n\n| Phase | Goal |\n| --- | --- |\n| P1 | Cap retries |\n\n### P1: Cap retries\n"
        self.assertEqual(self.check(plan=details, name="details"), [])

    def test_tables_without_edge_pipes(self):
        bare = "Phase | Name | Owner | State\n--- | --- | --- | ---\nP1 | Cap retries | | Planned"
        self.assertEqual(self.check(edit(TABLE, bare)), [])
        waiting = edit(TABLE, bare.replace("| Planned", "| Waiting"))
        message = "Phases: State does not start with a phase state word: Waiting"
        self.assertEqual(self.check(waiting), [f"{R}:16: {message}"])
        plan = "# Plan\n\nPhase | Goal | Status\n:--- | --- | ---:\nP1 | Cap | Merged\n"
        self.assertEqual(self.check(plan=plan, name="bare"), [f"planned/bare/IMPLEMENTATION_PLAN.md:3: {OUTSIDE}"])

    def test_status_lines_in_other_files(self):
        files = {
            "IMPLEMENTATION_PLAN.md": "# Plan\n\n### P1: Cap\n\n- **Status:** Verified\n",
            "SRD.md": "# Requirements\n\n- Status: 404 when the file is missing\n- State: Proposed\n- Status: Draft\n",
            "SADD.md": "# Design\n\n| Phase | State |\n| --- | --- |\n| P1 | Merged |\n\n```\n- Status: Merged\n```\n",
        }
        message = "line outside the README; status lives in its ## Current Work and ## Phases"
        self.assertEqual(self.check(POINTED, files=files), [
            f"planned/sample/IMPLEMENTATION_PLAN.md:5: Phases: Status {message}",
            f"planned/sample/SRD.md:4: Phases: State {message}",
            f"planned/sample/SRD.md:5: Phases: Status {message}",
            f"planned/sample/SADD.md:3: {OUTSIDE}",
        ])

    def test_lifecycle_lines_in_other_files(self):
        # Only a packet status word makes a Lifecycle line status: Accepted is
        # an older phase word. A line inside an HTML comment does not count.
        files = {
            "SRD.md": "# Requirements\n\n- Lifecycle: Draft\n- Status: Approved; @sam signed off on 2026-11-02.\n",
            "SADD.md": (
                "# Design\n\n- **Lifecycle:** In progress\n- Status: Design record for the retry cap.\n"
                "- Lifecycle: Accepted by @sam\n<!--\n- Lifecycle: Draft\n-->\n"
            ),
            "IMPLEMENTATION_PLAN.md": "# Plan\n\n- Lifecycle: see the README\n\n### P1: Cap\n",
        }
        self.assertEqual(self.check(POINTED, files=files), [
            f"planned/sample/SRD.md:3: {LIFECYCLE_OUTSIDE}",
            f"planned/sample/SADD.md:3: {LIFECYCLE_OUTSIDE}",
        ])

    def test_requirements_live_in_srd(self):
        srd = {"SRD.md": SRD}
        self.assertEqual(self.check(POINTED, name="pointer", files=srd), [])
        listed = with_done_when("- REQ-001: Stop after three attempts.\n- REQ-002: Log the third failure.")
        self.assertEqual(self.check(listed, name="readme-only"), [])
        self.assertEqual(self.check(listed, name="both", files=srd), [
            f"planned/both/README.md:18: {NO_POINTER}",
            f"planned/both/README.md:18: {ITEMS.format(2)}",
            f"planned/both/README.md:20: {IN_SRD.format('REQ-001')}",
            f"planned/both/README.md:21: {IN_SRD.format('REQ-002')}",
        ])
        # One item, wrapped onto a second line; each ID is reported once.
        one_item = with_done_when("REQ-001 and REQ-002 pass; see [SRD.md](SRD.md).\nREQ-001 again.")
        self.assertEqual(self.check(one_item, name="one-item", files=srd), [
            f"planned/one-item/README.md:20: {IN_SRD.format('REQ-001')}",
            f"planned/one-item/README.md:20: {IN_SRD.format('REQ-002')}",
        ])

    def test_done_when_beside_srd_names_srd(self):
        srd = {"SRD.md": SRD}
        for name, body in [
            ("empty", ""),
            ("comment-only", "<!-- moved to SRD.md -->"),
            ("tbd", "TBD"),
            ("requirement-text", "- Retries stop after three attempts."),
        ]:
            with self.subTest(body=body):
                found = self.check(with_done_when(body), name=name, files=srd)
                self.assertEqual(found, [f"planned/{name}/README.md:18: {NO_POINTER}"])
        self.assertEqual(self.check(name="missing", files=srd), [f"planned/missing/README.md:1: {NO_DONE_WHEN}"])
        for name, body in [
            ("own-pointer", "Requirements: see [SRD.md](SRD.md#requirements)."),
            ("lowercase", "The requirements are in the srd.md file."),
            ("thematic-break", f"{POINTER}\n\n---"),
            ("wrapped", "The requirements and their checks are in\n[SRD.md](SRD.md)."),
            ("list-item", "- The requirements are in [SRD.md](SRD.md),\n  with their checks."),
        ]:
            with self.subTest(body=body):
                self.assertEqual(self.check(with_done_when(body), name=name, files=srd), [])

    def test_done_when_beside_srd_ignores_comments_and_other_ids(self):
        srd = {"SRD.md": SRD}
        comment = with_done_when(f"<!-- REQ-001 and REQ-002 moved to SRD.md\n     on 2026-11-03. -->\n{POINTER}")
        self.assertEqual(self.check(comment, name="comment", files=srd), [])
        # Each comment ends at its own -->, so the requirement between two is seen.
        two_comments = with_done_when(f"<!-- a -->\n- REQ-001: Stop.\n<!-- b -->\n{POINTER}")
        self.assertEqual(self.check(two_comments, name="two-comments", files=srd), [
            f"planned/two-comments/README.md:18: {ITEMS.format(2)}",
            f"planned/two-comments/README.md:21: {IN_SRD.format('REQ-001')}",
        ])
        other_ids = with_done_when("Unlike XREQ-001 and REQ-0010, these are in [SRD.md](SRD.md).")
        self.assertEqual(self.check(other_ids, name="other-ids", files=srd), [])
        in_srd = with_done_when("REQ-001 is in [SRD.md](SRD.md).")
        for name, text in [
            ("traceability", "| Requirement | Phase |\n| --- | --- |\n| REQ-001 | P1 |\n"),
            ("fenced", "```\n| ID | Requirement |\n| --- | --- |\n| REQ-001 | Stop. |\n```\n"),
            ("commented", "<!--\n| ID | Requirement |\n| --- | --- |\n| REQ-001 | Stop. |\n-->\n"),
        ]:
            with self.subTest(srd=name):
                self.assertEqual(self.check(in_srd, name=name, files={"SRD.md": f"# Requirements\n\n{text}"}), [])
        notes = "| ID | Requirement |\n| --- | --- |\n| REQ-001 | Stop. |\n| — | REQ-003 was merged into REQ-001. |\n"
        notes += "| – | An en dash note. |\n| Note | A row with no ID. |\n"
        dashes = with_done_when("Note: the requirements — all of them – are in [SRD.md](SRD.md).")
        self.assertEqual(self.check(dashes, name="notes", files={"SRD.md": f"# Requirements\n\n{notes}"}), [])

    def test_requirement_id_forms(self):
        table = (
            "| **ID** | Requirement |\n| --- | --- |\n| [REQ-001](#req-001) | Stop. |\n"
            '| <a id="req-002"></a>**REQ-002**: | Log. |\n'
        )
        both = with_done_when("REQ-001 and REQ-002 are in [SRD.md](SRD.md).")
        self.assertEqual(self.check(both, name="forms", files={"SRD.md": f"# Requirements\n\n{table}"}), [
            f"planned/forms/README.md:20: {IN_SRD.format('REQ-001')}",
            f"planned/forms/README.md:20: {IN_SRD.format('REQ-002')}",
        ])

    def test_html_comments_hide_readme_text(self):
        hidden = edit("## Log", "<!--\n## Done when\n\n- REQ-001: Stop.\n-->\n\n## Log", POINTED)
        self.assertEqual(self.check(hidden, name="hidden", files={"SRD.md": SRD}), [])
        # A comment that starts a line and never closes hides the rest of the file.
        unclosed = with_done_when(f"<!-- note\n{POINTER}")
        self.assertEqual(self.check(unclosed, name="unclosed", files={"SRD.md": SRD}), [
            "planned/unclosed/README.md:1: Log: no ## Log section",
            f"planned/unclosed/README.md:18: {NO_POINTER}",
        ])
        inline = with_done_when(f"{POINTER} <!-- not closed")
        self.assertEqual(self.check(inline, name="inline", files={"SRD.md": SRD}), [])

    def test_comments_follow_markdown(self):
        srd = {"SRD.md": SRD}
        # A `<!--` in a code span opens no comment, so a later comment does not
        # hide the lines between them.
        code_span = edit("- Blocker: None", "- Blocker: None\n- Next action: skip `<!--` notes", POINTED)
        code_span = edit(f"## Done when\n\n{POINTER}", f"## Done when\n\n<!-- a note -->\n{POINTER}", code_span)
        self.assertEqual(self.check(code_span, name="code-span", files=srd), [])
        # A comment opens a block only at the start of the original line.
        second = with_done_when(f"{POINTER}\n\n<!-- a --> <!-- b")
        self.assertEqual(self.check(second, name="second", files=srd), [
            f"planned/second/README.md:18: {ITEMS.format(2)}",
        ])
        # Inside a paragraph, a comment must close before the paragraph ends,
        # at a blank line or a heading.
        blank = with_done_when(f"{POINTER} <!-- a\n\nMore text. -->")
        self.assertEqual(self.check(blank, name="blank", files=srd), [f"planned/blank/README.md:18: {ITEMS.format(2)}"])
        heading = edit(f"## Done when\n\n{POINTER}\n\n## Log\n\n- 2026-11-03 Created.",
                       f"## Done when\n\n{POINTER} <!-- a\n## Log\n- 2026-11-03 Created. -->", POINTED)
        self.assertEqual(self.check(heading, name="heading", files=srd), [])
        # Within a paragraph, each comment ends at its own -->, and a `<!--` in a
        # code span opens none.
        for name, body in [
            ("two-inline", f"Note <!-- a --> {POINTER} <!-- b -->"),
            ("code-span-inline", "Notes use `<!--`; see [SRD.md](SRD.md). <!-- old -->"),
        ]:
            with self.subTest(body=body):
                self.assertEqual(self.check(with_done_when(body), name=name, files=srd), [])
        # A comment block ends at its first -->, and the rest of that line stays.
        for name, body in [("block", f"<!-- moved\nREQ-001 here --> {POINTER}"), ("one-line", f"<!-- REQ-001 --> {POINTER}")]:
            with self.subTest(body=body):
                self.assertEqual(self.check(with_done_when(body), name=name, files=srd), [])

    def test_every_done_when_section_counts(self):
        twice = edit("## Log", "## Done when\n\n- REQ-001: Stop.\n\n## Log", POINTED)
        self.assertEqual(self.check(twice, name="twice", files={"SRD.md": SRD}), [
            f"planned/twice/README.md:18: {ITEMS.format(2)}",
            f"planned/twice/README.md:24: {IN_SRD.format('REQ-001')}",
        ])
        # Lines under two headings are two items, even with no blank line.
        tight = with_done_when(f"{POINTER}\n## Done when\nAll tests pass.")
        self.assertEqual(self.check(tight, name="tight", files={"SRD.md": SRD}), [
            f"planned/tight/README.md:18: {ITEMS.format(2)}",
        ])
        # A heading inside ## Done when starts an item of its own.
        heading = with_done_when(f"{POINTER}\n### More\nAll tests pass.")
        self.assertEqual(self.check(heading, name="heading", files={"SRD.md": SRD}), [
            f"planned/heading/README.md:18: {ITEMS.format(2)}",
        ])

    def test_merge_requests_table(self):
        """Several rows per phase pass; each cell has its own finding."""
        valid = (
            "## Merge requests\n\n| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n"
            "| P1 | !12 | Closed — replaced by !14 | first try |\n"
            "| P1 | !14 | Merged @ abc1234 | |\n"
            "| P1 | #34 | Open | follow-up |\n"
            "| P1 | https://git.example.com/app/-/merge_requests/15 | Merged @ `abc1234def` | |\n"
            "| P1 | [!16](https://git.example.com/app/-/merge_requests/16) | Open | |\n\n## Log"
        )
        self.assertEqual(self.check(edit("## Log", valid)), [])
        bad = (
            "## Merge requests\n\n| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n"
            "| P2 | !12 | Open | |\n"
            "| P1 | 12 | Merged | |\n"
            "| P1 | !13 | Closed | |\n"
            "| P1 | !14 | merged @ abc1234 | |\n"
            "| P1 | !15 | Open |\n\n## Log"
        )
        reference = "Merge requests: Merge request is not !<number>, #<number> or a URL: 12"
        state = "Merge requests: State is not Open, Merged @ <commit> or Closed — <reason>: {}"
        self.assertEqual(self.check(edit("## Log", bad)), [
            f"{R}:22: Merge requests: phase P2 is not in the ## Phases table",
            f"{R}:23: {reference}",
            f"{R}:23: {state.format('Merged')}",
            f"{R}:24: {state.format('Closed')}",
            f"{R}:25: {state.format('merged @ abc1234')}",
            f"{R}:26: Merge requests: row has 3 cells, but the header has 4",
        ])

    def test_merge_requests_section_needs_its_table(self):
        message = "Merge requests: the section needs the table | Phase | Merge request | State | Note |"
        no_table = edit("## Log", "## Merge requests\n\nNone yet.\n\n## Log")
        self.assertEqual(self.check(no_table), [f"{R}:18: {message}"])
        wrong = "## Merge requests\n\n| Phase | MR | State |\n| --- | --- | --- |\n| P1 | !12 | Open |\n\n## Log"
        self.assertEqual(self.check(edit("## Log", wrong)), [f"{R}:20: {message}"])

    def test_merge_requests_forms_the_neighbouring_rules_accept(self):
        """Linked and bold phase IDs, emphasis in State, any header case, and
        links whose target holds parentheses or is an autolink."""
        linked = edit("| P1 | Cap retries | | Planned |", "| [P1](IMPLEMENTATION_PLAN.md#p1-cap) | Cap | | Planned |")
        table = (
            "## Merge requests\n\n| phase | Merge Request | STATE | note |\n| --- | --- | --- | --- |\n"
            "| [P1](IMPLEMENTATION_PLAN.md#p1-cap) | [!12](https://git.example.com/a_(b)/-/merge_requests/12) | **Open** | |\n"
            "| **P1** | <https://git.example.com/app/pull/13> | *Merged @ abc1234* | |\n"
            "| `P1` | #14 | **Closed** — replaced by #13 | |\n\n## Log"
        )
        self.assertEqual(self.check(edit("## Log", table, linked)), [])
        self.assertEqual(self.check(edit("## Log", table)), [])

    def test_merge_requests_second_table_is_a_finding(self):
        two = (
            "## Merge requests\n\n| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n"
            "| P1 | !12 | Open | |\n\n| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n"
            "| P9 | x | y | |\n\n## Log"
        )
        message = "Merge requests: a second table; the section holds one table"
        self.assertEqual(self.check(edit("## Log", two)), [f"{R}:24: {message}"])

    def test_merge_requests_tables_in_comments_and_fences_are_ignored(self):
        hidden = "| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n| P9 | x | y | |"
        fenced = (
            f"## Merge requests\n\n```\n{hidden}\n```\n\n"
            "| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n| P1 | !12 | Open | |\n\n## Log"
        )
        self.assertEqual(self.check(edit("## Log", fenced)), [])
        commented = f"## Merge requests\n\n<!--\n{hidden}\n-->\n\n## Log"
        message = "Merge requests: the section needs the table | Phase | Merge request | State | Note |"
        self.assertEqual(self.check(edit("## Log", commented)), [f"{R}:18: {message}"])
        example = f"## Notes\n\n```\n## Merge requests\n\n{hidden}\n```\n\n## Log"
        self.assertEqual(self.check(edit("## Log", example)), [])

    def test_merge_requests_without_phases(self):
        no_phases = edit("## Phases\n\n" + TABLE + "\n\n", "")
        table = (
            "## Merge requests\n\n| Phase | Merge request | State | Note |\n| --- | --- | --- | --- |\n"
            "| P1 | !12 | Open | |\n\n## Log"
        )
        found = self.check(edit("## Log", table, no_phases))
        self.assertIn(f"{R}:16: Merge requests: phase P1 is not in the ## Phases table", found)
        self.assertNotIn(OUTSIDE, " ".join(found))

    def test_no_merge_requests_section_has_no_finding(self):
        self.assertNotIn("## Merge requests", VALID)
        self.assertEqual(self.check(), [])

    def test_fenced_phase_table_in_the_plan(self):
        plan = "# Plan\n\n```\n| Phase | State |\n| --- | --- |\n| P1 | Planned |\n```\n"
        self.assertEqual(self.check(plan=plan), [])

    def test_completed_packet_phase_words(self):
        finished = edit("- Status: Planned", "- Status: Complete")
        for state, allowed in [
            ("Planned", False),
            ("In progress", False),
            ("Implemented", False),
            ("Merged — !12 @ abc1234", False),
            ("Blocked — waits on @sam", False),
            ("Verified — task test → passed @ abc1234", True),
            ("Live — deployed @ abc1234", True),
            ("Deferred — waits on a library fix", True),
            ("Dropped — obsolete", True),
        ]:
            with self.subTest(state=state):
                found = self.check(edit("| Planned |", f"| {state} |", finished), folder="completed")
                word = fc.lookup_word(fc.PHASE_WORDS, state)
                expected = [] if allowed else [f"completed/sample/README.md:16: strict: {word} {NOT_FINISHED}"]
                self.assertEqual(found, expected)

    def test_packet_folder_named_like_a_lifecycle_folder(self):
        message = "packet folder is named like the completed/ lifecycle folder; put it in a folder of its own"
        self.assertEqual(self.check(folder=".", name="completed"), [f"completed: {message}"])

    def test_folder_must_match_status(self):
        verified = edit("| Planned |", "| Verified — task test → passed @ abc1234 |")
        in_progress = edit("- Status: Planned", "- Status: In progress", verified)
        message = "strict: Status In progress does not match the completed/ folder, which needs Complete"
        self.assertEqual(self.check(in_progress, folder="completed"), [f"completed/sample/README.md:7: {message}"])
        deferred = edit("- Status: Planned", "- Status: Complete")
        deferred = edit("| Planned |", "| Deferred — waits on a library fix |", deferred)
        self.assertEqual(self.check(deferred, folder="completed"), [])
        archived = edit("- Status: Planned", "- Status: Archived")
        message = "strict: Archived note does not start with a reason word"
        self.assertEqual(self.check(archived, folder="archived"), [f"archived/sample/README.md:7: {message}"])
        for status in ("Archived — obsolete: the service was retired", "Superseded — superseded by harbor-v2"):
            with_reason = edit("- Status: Planned", f"- Status: {status}")
            self.assertEqual(self.check(with_reason, folder="archived"), [])

    def test_blocked_needs_a_blocker(self):
        blocked = edit("- Status: Planned", "- Status: Blocked")
        for blocker in ("- Blocker: None\n", "- Blocker: **None**\n", "- Blocker: `None`.\n", ""):
            self.assertEqual(self.check(edit("- Blocker: None\n", blocker, blocked)), [f"{R}:7: {NO_BLOCKER}"])
        self.assertEqual(self.check(edit("- Blocker: None", "- Blocker: Library fix (@sam)", blocked)), [])

    def test_live_needs_evidence(self):
        message = "strict: Live phase has no evidence after ' — '"
        self.assertEqual(self.check(edit("| Planned |", "| Live |")), [f"{R}:16: {message}"])
        self.assertEqual(self.check(edit("| Planned |", "| Live — deployed @ abc1234 |")), [])

    def test_dropped_needs_a_reason_word(self):
        for reason in ("won’t do", "won't do", "*duplicate* of P2"):
            self.assertEqual(self.check(edit("| Planned |", f"| Dropped — {reason} |")), [])
        message = "strict: Dropped note does not start with a reason word"
        self.assertEqual(self.check(edit("| Planned |", "| Dropped — later |")), [f"{R}:16: {message}"])

    def test_lifecycle_option(self):
        finished = edit("- Status: Planned", "- Status: Complete")
        finished = edit("| Planned |", "| Merged — !12 @ abc1234 |", finished)
        moved = self.check(finished, folder="in-progress", lifecycle="completed")
        self.assertEqual(moved, [f"in-progress/sample/README.md:16: strict: Merged {NOT_FINISHED}"])
        message = "strict: Status Complete does not match the in-progress/ folder, which needs In progress or Blocked"
        self.assertEqual(self.check(finished, folder="in-progress"), [f"in-progress/sample/README.md:7: {message}"])

    def test_fenced_code_is_ignored(self):
        fenced = "```markdown\n## Current Work\n- Status: Bogus\n| Phase | State |\n| --- | --- |\n"
        fenced += "| P9 | Unknown |\n## Log\n```\n"
        summary = "Stop retries after three attempts.\n"
        with_fence = edit(summary, summary + "\n" + fenced)
        self.assertEqual(self.check(with_fence), [])
        no_log = edit("## Log\n\n- 2026-11-03 Created.\n", "", with_fence)
        self.assertEqual(self.check(no_log), [f"{R}:1: Log: no ## Log section"])
        code_first = edit(summary, "~~~\ncode\n~~~\n")
        self.assertEqual(self.check(code_first), [f"{R}:1: summary: no paragraph directly under the title"])

    def test_headings_ignore_case(self):
        self.assertEqual(self.check(edit("## Log", "## log", edit("## Phases", "## phases"))), [])

    def test_title_alone_has_no_summary(self):
        self.assertIn(f"{R}:1: summary: no paragraph directly under the title", self.check("# Only a title\n"))

    def test_read_errors(self):
        folder = self.root / "planned" / "folder"
        (folder / "README.md").mkdir(parents=True)
        with self.assertRaisesRegex(fc.ReadError, "not a regular file"):
            fc.check_packet(folder)
        broken = self.root / "planned" / "broken"
        broken.mkdir()
        (broken / "README.md").write_bytes(b"# Broken \xff\n")
        with self.assertRaisesRegex(fc.ReadError, "cannot read"):
            fc.check_packet(broken)
        large = self.root / "planned" / "large"
        large.mkdir()
        (large / "README.md").write_bytes(b"x" * (fc.MAX_BYTES + 1))
        with self.assertRaisesRegex(fc.ReadError, "larger than 4 MiB"):
            fc.check_packet(large)

    def test_byte_order_mark_is_ignored(self):
        self.assertEqual(self.check("﻿" + VALID), [])


class HelpersTest(unittest.TestCase):
    def test_cells_keep_escaped_pipes(self):
        self.assertEqual(fc.cells("| P1 | `a \\| b` | Planned |"), ["P1", "`a \\| b`", "Planned"])
        self.assertEqual(fc.cells("| P1 | Planned"), ["P1", "Planned"])

    def test_requirement_rows_skip_fences_and_comments(self):
        lines = [
            "| ID | Requirement |", "| --- | --- |", "| REQ-001 | Stop. |", "",
            "```", "| ID | Requirement |", "| --- | --- |", "| REQ-009 | Fenced. |", "```", "",
            "<!--", "| ID | Requirement |", "| --- | --- |", "| REQ-010 | Hidden. |", "-->",
        ]
        self.assertEqual(fc.requirement_rows(lines), [(3, ["REQ-001", "Stop."])])

    def test_requirement_id(self):
        for cell, expected in [
            ("REQ-001", "REQ-001"),
            ("**REQ-002**:", "REQ-002"),
            ("[REQ-003](#req-003)", "REQ-003"),
            ('<a id="req-004"></a>REQ-004', "REQ-004"),
            ("_REQ-005_", "REQ-005"),
            ("—", None),
            ("Note", None),
            ("", None),
        ]:
            with self.subTest(cell=cell):
                self.assertEqual(fc.requirement_id([cell, "text"]), expected)

    def test_lookup_word(self):
        self.assertEqual(fc.lookup_word(fc.PHASE_WORDS, "**Merged** — !12"), "Merged")
        self.assertEqual(fc.lookup_word(fc.PHASE_WORDS, "not started"), "Planned")
        self.assertEqual(fc.lookup_word(fc.PACKET_WORDS, "In-progress"), "In progress")
        self.assertIsNone(fc.lookup_word(fc.PACKET_WORDS, "Doneness"))

    def test_paths_print_with_forward_slashes(self):
        self.assertEqual(fc.shown(PureWindowsPath("plans\\planned\\sample")), "plans/planned/sample")

    def test_unfenced_closing_rules(self):
        cases = [
            (["```", "a", "~~~", "b", "```", "c"], 5),  # another fence character does not close
            (["````", "a", "```", "b", "````", "c"], 5),  # a shorter fence does not close
            (["```", "a", "``` x", "b", "```", "c"], 5),  # text after the fence does not close
            (["~~~", "a", "~~~~~", "c"], 3),  # a longer fence closes
            (["   ```", "a", "```", "c"], 3),  # up to three spaces of indent opens a fence
        ]
        for lines, blanked in cases:
            with self.subTest(lines=lines):
                self.assertEqual(fc.unfenced(lines), [""] * blanked + lines[blanked:])
        self.assertEqual(fc.unfenced(["    ```", "a"]), ["    ```", "a"])  # four spaces is code, not a fence

    def test_main_returns_exit_codes(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fc.main(["--people", "Alex Kim"]), 2)
            self.assertEqual(fc.main([]), 2)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fc.main(["--help"]), 0)


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)

    def test_good_packet_passes_strict(self):
        self.assertEqual(run("--packet", "packets/planned/good", "--strict", *PEOPLE), (0, [], ""))

    def test_full_packet_passes_strict(self):
        # SRD.md holds the requirements, and the other files hold Status lines
        # that are not status words.
        self.assertEqual(run("--packet", "packets/planned/full", "--strict", *PEOPLE), (0, [], ""))

    def test_default_mode(self):
        self.assertEqual(run("packets", *PEOPLE), (1, DEFAULT_FINDINGS, ""))

    def test_strict_mode(self):
        self.assertEqual(run("packets", "--strict", *PEOPLE), (1, STRICT_FINDINGS, ""))

    def test_completed_packet_needs_finished_phases(self):
        # P2's note holds an escaped pipe, which stays inside its cell.
        self.assertEqual(run("--packet", "packets/completed/finished", "--strict"), (1, FINISHED, ""))

    def test_plans_folder_skips_flat_design_files(self):
        _, out, _ = run("packets", "--strict", *PEOPLE)
        skipped = ("-srd.md", "-sadd.md", "plc-harbor-retry-plan.md")
        self.assertEqual([line for line in out if line.split(":")[0].endswith(skipped)], [])
        self.assertIn("packets/planned/plc-harbor-alerts-plan.md:1: Log: no ## Log section", out)

    def test_plans_folder_discovery(self):
        no_log = edit("## Log\n\n- 2026-11-03 Created.\n", "")
        self.write("planned/plc-a.md", no_log)
        self.write("planned/plc-a-plan.md", "A side file beside the one-file plan plc-a.md.\n")
        self.write("planned/plc-b-implementation-plan.md", no_log)  # alone, so a one-file plan
        self.write("planned/plc-c-prd.md", "A design file.\n")
        self.write("planned/plc-d-sadd.md", "A design file.\n")
        self.write("planned/plc-d-implementation-plan.md", "A side file beside plc-d-sadd.md.\n")
        self.write("planned/images/diagram.png", b"not markdown")
        code, out, _ = run(".", cwd=self.root)
        self.assertEqual((code, out), (1, [
            "planned/plc-a.md:1: Log: no ## Log section",
            "planned/plc-b-implementation-plan.md:1: Log: no ## Log section",
        ]))

    def test_several_packets(self):
        code, out, _ = run("--packet", "packets/planned/blocked", "--packet", "packets/planned/superseded", "--strict")
        self.assertEqual((code, out), (1, [STRICT_FINDINGS[0], *STRICT_FINDINGS[9:11]]))

    def test_bad_paths_exit_2(self):
        self.assertEqual(run("packets/nope"), (2, [], "no such path: packets/nope\n"))
        self.assertEqual(run("--packet", "packets/planned/nope")[0], 2)
        self.assertEqual(run("packets/planned"), (2, [], "packets/planned: no planned/ or in-progress/ folder\n"))
        (self.root / "planned").mkdir()
        self.assertEqual(run(".", cwd=self.root), (2, [], "nothing to check: no packets found\n"))

    def test_bad_arguments_exit_2(self):
        for args, message in [
            ((), "give at least one plans folder or --packet"),
            (("--people", "Alex Kim=alex", "packets"), "put plans folders before --people"),
            (("packets", "--lifecycle", "completed"), "--lifecycle works only with --packet"),
        ]:
            code, out, err = run(*args)
            self.assertEqual((code, out), (2, []))
            self.assertIn(message, err)

    def test_unreadable_file_is_reported_and_others_still_checked(self):
        self.write("planned/broken/README.md", b"# Broken \xff\n")
        self.write("planned/sample/README.md", edit("## Log\n\n- 2026-11-03 Created.\n", ""))
        code, out, err = run("--packet", "planned/broken", "--packet", "planned/sample", cwd=self.root)
        self.assertEqual((code, out), (2, [f"{R}:1: Log: no ## Log section"]))
        self.assertTrue(err.startswith("planned/broken/README.md: cannot read:"), err)

    def test_folder_rules_hold_for_relative_and_readme_paths(self):
        finding = "strict: Status Superseded does not match the planned/ folder, which needs Planned or Blocked"
        _, out, _ = run("--packet", "superseded", "--strict", cwd=DATA / "packets" / "planned")
        self.assertIn(f"superseded/README.md:7: {finding}", out)
        _, out, _ = run("--packet", "packets/planned/superseded/README.md", "--strict")
        self.assertIn(f"packets/planned/superseded/README.md:7: {finding}", out)

    def test_lifecycle_checks_a_packet_before_it_moves(self):
        finished = edit("- Status: Planned", "- Status: Complete")
        self.write("in-progress/sample/README.md", edit("| Planned |", "| Merged — !12 @ abc1234 |", finished))
        code, out, _ = run("--packet", "in-progress/sample", "--strict", "--lifecycle", "completed", cwd=self.root)
        self.assertEqual((code, out), (1, [f"in-progress/sample/README.md:16: strict: Merged {NOT_FINISHED}"]))

    def test_terminal_escapes_are_printed_escaped(self):
        self.write("planned/sample/README.md", edit("- Status: Planned", "- Status: \x1b[31mWaiting"))
        code, out, _ = run("--packet", "planned/sample", cwd=self.root)
        message = "Current Work: Status does not start with a packet status word: \\x1b[31mWaiting"
        self.assertEqual((code, out), (1, [f"{R}:7: {message}"]))

    def test_utf8_under_an_ascii_locale(self):
        env = {key: value for key, value in os.environ.items() if key != "PYTHONIOENCODING"}
        env.update(LC_ALL="C", LANG="C", PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
        self.assertEqual(run("packets", "--strict", *PEOPLE, env=env), (1, STRICT_FINDINGS, ""))


class TemplateTest(unittest.TestCase):
    """The templates and the skill's word list agree with the check."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.packet = Path(self.tmp.name) / "planned" / "sample"
        self.packet.mkdir(parents=True)

    def check(self, path):
        return run("--packet", str(path), "--strict", *PEOPLE)

    def write_filled_packet(self, sadd=lambda text: text):
        """Fill every default-packet template into the packet, passing the
        SADD template through sadd first."""
        for source in sorted((SKILL / "assets" / "default-packet").glob("*.md")):
            text = source.read_text(encoding="utf-8")
            if source.name == "SADD.md":
                text = sadd(text)
            (self.packet / source.name).write_text(fill(text), encoding="utf-8")
        # With SRD.md, the requirements leave ## Done when for the pointer line.
        readme = self.packet / "README.md"
        text = readme.read_text(encoding="utf-8")
        requirement = re.search(r"^- REQ-001: .*$", text, flags=re.MULTILINE)[0]
        readme.write_text(edit(requirement, POINTER, text), encoding="utf-8")

    def test_default_packet_passes_when_filled(self):
        self.write_filled_packet()
        self.assertEqual(self.check(self.packet), (0, [], ""))

    def test_visual_aids_rule(self):
        """plc-planning states the visual aids rule once, among its rules:
        encouraged, not required, which kind for which information, and where
        each lives."""
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("#### Visual aids\n"), 1)
        rules = text.split("### Rules\n", 1)[1]
        rule = " ".join(rules.split("#### Visual aids\n", 1)[1].split("\n#### ", 1)[0].split())
        for phrase in (
            "encouraged",
            "never required",
            "one-file plan usually needs none",
            "plain-text tree",
            "Mermaid",
            "flowchart",
            "sequence diagram",
            "ER diagram",
            "class diagram",
            "state diagram",
            "deployment diagram",
            "decision logic",
            "mostly SADD.md",
            "SRD.md's Expected Experience",
            "at most one overview diagram",
            "the section it explains",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_sadd_diagram_examples_stay_in_comments(self):
        """The SADD template's Mermaid examples sit in HTML comments, so an
        unfilled diagram is not copied into a plan, and a plan that takes them
        out of their comments still passes the strict check."""
        text = (SKILL / "assets" / "default-packet" / "SADD.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertFalse(any("```mermaid" in line for line in fc.uncommented(lines)))
        examples = {
            section.name: sum(line == "```mermaid" for line in lines[section.start:section.end])
            for section in fc.sections(lines)
        }
        self.assertEqual(
            {name: count for name, count in examples.items() if count},
            {"Context And Boundaries": 1, "Runtime And Data Flow": 2},
        )

        def uncomment(sadd):
            out = re.sub(r"<!--.*?\n\n(```mermaid.*?```)\n-->", r"\1", sadd, flags=re.DOTALL)
            self.assertEqual(out.count("<!--"), 0)
            return out

        self.write_filled_packet(uncomment)
        filled = (self.packet / "SADD.md").read_text(encoding="utf-8")
        self.assertEqual(filled.count("```mermaid"), 3)
        self.assertEqual(self.check(self.packet), (0, [], ""))

    def test_compact_plan_passes_when_filled(self):
        text = fill((SKILL / "assets" / "compact-plan.md").read_text(encoding="utf-8"))
        (self.packet / "README.md").write_text(text, encoding="utf-8")
        self.assertEqual(self.check(self.packet), (0, [], ""))
        one_file = self.packet.parent / "plc-sample.md"
        shutil.move(self.packet / "README.md", one_file)
        self.assertEqual(self.check(one_file), (0, [], ""))

    def test_compact_plan_is_the_default_readme(self):
        compact = (SKILL / "assets" / "compact-plan.md").read_text(encoding="utf-8")
        readme = (SKILL / "assets" / "default-packet" / "README.md").read_text(encoding="utf-8")
        self.assertNotEqual(compact, readme)
        self.assertEqual(without_note(compact), readme)

    def test_fixed_fields_match_the_templates(self):
        """Every template in assets/ is in the skill's Fixed fields list, and
        holds the fields the list gives it, exactly."""
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        rules = text.split("### Rules\n", 1)[1]

        def rule(name):
            return " ".join(rules.split(f"#### {name}\n", 1)[1].split("\n#### ", 1)[0].split())

        assets = SKILL / "assets"
        fields = {}
        for item in re.findall(r"- (`[\w.-]+\.md`.+?)(?= - `[\w.-]+\.md`|$)", rule("Fixed fields")):
            texts = [field for field in re.findall(r"`([^`]+)`", item) if field.startswith(("|", "###"))]
            for name in re.findall(r"`([\w.-]+\.md)`", item):
                path = assets / name if name == "compact-plan.md" else assets / "default-packet" / name
                fields[path] = texts
        self.assertEqual(sorted(fields), sorted(assets.rglob("*.md")))
        self.assertEqual(sorted(path.name for path, texts in fields.items() if not texts), [])

        # The README's sections and keys are the ones the rules name.
        sections = re.findall(r"`(## [^`]+)`", rule("Order and format").split(" - ")[0])
        keys = re.search(r"- (Status), (Owner) and (Last updated) come first.*?Then ([^.]+)\.", rule("Current Work"))
        keys = [*keys.groups()[:3], *re.split(r", | and ", keys[4])]
        self.assertEqual(len(sections), 6)
        self.assertEqual(len(keys), 8)

        for path, texts in fields.items():
            lines = fc.unfenced(path.read_text(encoding="utf-8").splitlines())
            if path.name in ("README.md", "compact-plan.md"):
                texts = [*texts, *sections]
                for key in keys:
                    with self.subTest(template=path.name, key=key):
                        self.assertTrue(any(line.startswith(f"- {key}: ") for line in lines))
            for field in texts:
                pattern = re.escape(field).replace("<n>", r"\d+[a-z]?").replace("<name>", ".+")
                with self.subTest(template=path.name, field=field):
                    self.assertTrue(any(re.fullmatch(pattern, line) for line in lines))

        # The format check finds the SRD template's requirements table.
        srd = (assets / "default-packet" / "SRD.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual([cells[0] for _, cells in fc.requirement_rows(srd)], ["REQ-001"])

    def test_independent_review_has_one_home(self):
        """plc-planning states when a plan gets an independent review; the
        skills that write or grow plans point there instead of restating it."""
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        rule = text.split("#### Independent review\n", 1)[1].split("\n#### ", 1)[0]
        self.assertIn("../review-and-fix-plc/SKILL.md", rule)
        self.assertIn("(#independent-review)", text.split("## Shared template", 1)[0])
        for name in ("plc-checkpoint", "plc-execution"):
            other = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=name):
                self.assertIn("../plc-planning/SKILL.md#independent-review", other)
                self.assertNotIn("../review-and-fix-plc/SKILL.md", other)

    def test_skill_word_list_matches_the_check(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        words = " ".join(text.split("### Words\n", 1)[1].split("\n### ", 1)[0].split())
        packet = re.search(r"\*\*Packet status words:\*\* (.+?)\. - ", words)[1].split(", ")
        ladder = re.search(r"\*\*Phase state words, in order:\*\*(.+?)- \*\*Side states", words)[1]
        phases = re.findall(r"- ([A-Z][a-z]+(?: [a-z]+)?)[;:]", ladder)
        phases += re.search(r"\*\*Side states:\*\* ([^.]+)\.", words)[1].split(", ")
        self.assertEqual(packet, list(fc.PACKET_WORDS))
        self.assertEqual(phases, list(fc.PHASE_WORDS))
        for kind, table in (("packets", fc.PACKET_WORDS), ("phases", fc.PHASE_WORDS)):
            older = {}
            for group in re.search(rf"For {kind}: (.+?)\. - ", words)[1].split("; "):
                spellings, canonical = re.fullmatch(r"(.+) \((.+)\)", group).groups()
                older[canonical] = re.split(r", | and ", spellings)
            self.assertEqual(older, {canonical: spellings for canonical, spellings in table.items() if spellings})


if __name__ == "__main__":
    unittest.main()
