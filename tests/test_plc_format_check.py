"""Tests for plc-planning's format check, skills/plc-planning/scripts/format_check.py."""

import importlib.util
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


def edit(old, new, text=VALID):
    assert text.count(old) == 1, old
    return text.replace(old, new)


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

    def check(self, readme=VALID, folder="planned", name="sample", plan=None, people=(), lifecycle=None):
        packet = self.root / folder / name
        packet.mkdir(parents=True, exist_ok=True)
        (packet / "README.md").write_text(readme, encoding="utf-8")
        if plan is not None:
            (packet / "IMPLEMENTATION_PLAN.md").write_text(plan, encoding="utf-8")
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

    def test_last_updated_starts_with_a_date(self):
        late_date = edit("- Last updated: 2026-11-03", "- Last updated: today, 2026-11-03")
        message = "Current Work: Last updated does not start with a YYYY-MM-DD date"
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

    def test_lookup_word(self):
        self.assertEqual(fc.lookup_word(fc.PHASE_WORDS, "**Merged** — !12"), "Merged")
        self.assertEqual(fc.lookup_word(fc.PHASE_WORDS, "not started"), "Planned")
        self.assertEqual(fc.lookup_word(fc.PACKET_WORDS, "In-progress"), "In progress")
        self.assertIsNone(fc.lookup_word(fc.PACKET_WORDS, "Doneness"))

    def test_paths_print_with_forward_slashes(self):
        self.assertEqual(fc.shown(PureWindowsPath("plans\\planned\\sample")), "plans/planned/sample")


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

    def test_default_packet_passes_when_filled(self):
        for source in sorted((SKILL / "assets" / "default-packet").glob("*.md")):
            (self.packet / source.name).write_text(fill(source.read_text(encoding="utf-8")), encoding="utf-8")
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
