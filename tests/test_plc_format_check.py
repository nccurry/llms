"""Tests for plc-planning's format check, run against the sample packets."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "plc-planning"
SCRIPT = SKILL / "scripts" / "format_check.py"
DATA = Path(__file__).resolve().parent / "plc_format_check"
PEOPLE = ["--people", "Alex Kim=alex", "sam=sam"]

GAPS = "packets/planned/gaps/README.md"
BAD = "packets/in-progress/bad/README.md"

DEFAULT_FINDINGS = [
    f"{GAPS}:5: status block: Status, Owner and Last updated must come first, in that order",
    f"{GAPS}:5: status block: no Status line",
    f"{GAPS}:9: owner: sam without @sam",
    f"{GAPS}:5: updated: no date-first Last updated line",
    f"{GAPS}:16: phase state: (empty)",
    f"{GAPS}:17: phases: row has 2 cells, header has 3",
    "packets/planned/plc-harbor-cache.md:1: log: no ## Log section",
    "packets/planned/twohomes/IMPLEMENTATION_PLAN.md:3: phases: phase state outside the README ## Phases table",
    f"{BAD}:1: summary: no paragraph directly under the title",
    f"{BAD}:3: status block: 13 keys (at most 12)",
    f"{BAD}:6: owner: Alex Kim without @alex",
    f"{BAD}:1: log: no ## Log section",
    "packets/in-progress/noreadme: packet folder has no README.md",
]

STRICT_FINDINGS = [
    "packets/planned/blocked/README.md:7: strict: Blocked with no Blocker",
    *DEFAULT_FINDINGS[:7],
    "packets/planned/sup/README.md:7: strict: status Superseded disagrees with folder planned/",
    "packets/planned/sup/README.md:7: strict: Superseded with no reason word",
    *DEFAULT_FINDINGS[7:11],
    f"{BAD}:5: strict: status Planned disagrees with folder in-progress/",
    f"{BAD}:1: log: no ## Log section",
    f"{BAD}:23: strict: Verified with no evidence after ' — '",
    f"{BAD}:24: strict: Dropped with no reason word",
    "packets/in-progress/noreadme: packet folder has no README.md",
]


def run(*args, cwd=DATA, env=None):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
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


class FormatCheckTest(unittest.TestCase):
    def test_good_packet_passes_strict(self):
        self.assertEqual(run("--packet", "packets/planned/good", "--strict", *PEOPLE), (0, [], ""))

    def test_default_mode_reports_structure(self):
        code, out, _ = run("packets", *PEOPLE)
        self.assertEqual(code, 1)
        self.assertEqual(out, DEFAULT_FINDINGS)

    def test_strict_mode_adds_rules_across_fields(self):
        code, out, _ = run("packets", "--strict", *PEOPLE)
        self.assertEqual(code, 1)
        self.assertEqual(out, STRICT_FINDINGS)

    def test_completed_packet_needs_finished_phases(self):
        # P2's note holds an escaped pipe, which stays inside its cell.
        code, out, _ = run("--packet", "packets/completed/finished", "--strict")
        self.assertEqual(code, 1)
        self.assertEqual(out, ["packets/completed/finished/README.md:17: strict: Merged phase in a completed packet"])

    def test_plans_folder_skips_flat_design_files(self):
        _, out, _ = run("packets", "--strict", *PEOPLE)
        self.assertFalse([line for line in out if "-srd.md" in line or "-sadd.md" in line])
        self.assertIn("packets/planned/plc-harbor-cache.md:1: log: no ## Log section", out)

    def test_bad_path_exits_2(self):
        self.assertEqual(run("packets/nope"), (2, [], "no such path: packets/nope\n"))
        self.assertEqual(run("--packet", "packets/planned/nope")[0], 2)

    def test_bad_arguments_exit_2(self):
        code, out, err = run()
        self.assertEqual((code, out), (2, []))
        self.assertIn("give at least one plans folder or --packet", err)
        code, out, err = run("--people", "Alex Kim=alex", "packets")
        self.assertEqual((code, out), (2, []))
        self.assertIn("put plans folders before --people", err)

    def test_folder_rules_hold_for_relative_and_readme_paths(self):
        finding = "strict: status Superseded disagrees with folder planned/"
        _, out, _ = run("--packet", "sup", "--strict", cwd=DATA / "packets" / "planned")
        self.assertIn(f"sup/README.md:7: {finding}", out)
        _, out, _ = run("--packet", "packets/planned/sup/README.md", "--strict")
        self.assertIn(f"packets/planned/sup/README.md:7: {finding}", out)

    def test_title_alone_has_no_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "planned" / "plc-title.md"
            plan.parent.mkdir()
            plan.write_text("# Only a title\n", encoding="utf-8")
            _, out, _ = run("--packet", str(plan))
        self.assertIn(f"{plan}:1: summary: no paragraph directly under the title", out)

    def test_reads_utf8_under_any_locale(self):
        env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
        code, out, err = run("--packet", "packets/completed/finished", "--strict", env=env)
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, ["packets/completed/finished/README.md:17: strict: Merged phase in a completed packet"])


class TemplateTest(unittest.TestCase):
    """A packet made from each template, placeholders filled, passes strict mode."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.packet = Path(self.tmp.name) / "planned" / "sample"
        self.packet.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return run("--packet", str(self.packet), "--strict", *PEOPLE)

    def test_default_packet(self):
        for source in sorted((SKILL / "assets" / "default-packet").glob("*.md")):
            text = fill(source.read_text(encoding="utf-8"))
            (self.packet / source.name).write_text(text, encoding="utf-8")
        self.assertEqual(self.check(), (0, [], ""))

    def test_compact_plan(self):
        text = fill((SKILL / "assets" / "compact-plan.md").read_text(encoding="utf-8"))
        (self.packet / "README.md").write_text(text, encoding="utf-8")
        self.assertEqual(self.check(), (0, [], ""))
        one_file = self.packet.parent / "plc-sample.md"
        shutil.move(self.packet / "README.md", one_file)
        self.assertEqual(run("--packet", str(one_file), "--strict"), (0, [], ""))


if __name__ == "__main__":
    unittest.main()
