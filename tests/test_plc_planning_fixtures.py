import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CASES = Path(__file__).resolve().parent / "skill-evals" / "plc-planning"
sys.path.insert(0, str(CASES.parent / "plc-checkpoint"))
from fixture_lib import packet_shape_problems  # noqa: E402

# A README-only plan in the shared PLC template, as the small-change case
# expects. `{head}` is the fixture's commit.
GOOD_PLAN = """# Limit check

Make `harbor list --limit` reject a limit below 1 with a clear error, instead
of printing nothing or dropping berths.

## Current Work

- Status: Planned
- Owner: @alex
- Last updated: 2026-11-03, `main` at `{head}`
- Next action: Write a failing test for `--limit 0`.
- Blocker: None
- Depends on: None
- Current state: Planned; no code changed.
- Resume check: `python -m unittest` → OK

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | Reject limits below 1 | | Planned |

## Done when

- REQ-001: `harbor list --limit 0` and `--limit -1` exit with an error that
  says the limit must be at least 1, and `--limit 2` still prints two berths.
  Check: `python -m unittest` → OK, with a new test for each case.

## Log

- 2026-11-03 Created.
"""

# The older compact-plan shape: no Phases table, no Log.
OLD_COMPACT_PLAN = """# Limit check Plan

## Current Work

- Status: Planned
- Owner: @alex
- Last updated: 2026-11-03, `main` at `abc1234`
- State: not started

## Outcome And Requirements

| ID | Required behavior | Acceptance criteria |
| --- | --- | --- |
| REQ-001 | Reject a limit below 1 | A test passes |
"""


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


def check(dest: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(CASES / "check_plan.py"), str(dest)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class SmallChangeFixtureTest(unittest.TestCase):
    """The small-change fixture and check_plan.py must match the grader."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"
        build("small-change", self.dest)
        self.app = self.dest / "harbor"
        self.head = git(self.app, "rev-parse", "--short", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, text: str) -> None:
        path = self.app / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def write_good_plan(self, relative: str = "docs/plans/planned/limit-check/README.md"):
        self.write(relative, GOOD_PLAN.format(head=self.head))

    def test_fixture_has_the_bug_and_no_plan(self):
        tests = subprocess.run(
            [sys.executable, "-m", "unittest"], cwd=self.app, capture_output=True, text=True
        )
        self.assertEqual(tests.returncode, 0, tests.stderr)
        listed = subprocess.run(
            [sys.executable, "harbor.py", "list", "--limit", "-1"],
            cwd=self.app,
            capture_output=True,
            text=True,
        )
        self.assertEqual(listed.stdout.split(), ["A1", "A2", "B1", "B2"])
        plans_readme = (self.app / "docs/plans/README.md").read_text(encoding="utf-8")
        self.assertIn("`planned/`", plans_readme)
        self.assertFalse((self.app / "docs/plans/planned").exists())
        self.assertEqual(git(self.app, "status", "--short"), "")

    def test_untouched_fixture_fails(self):
        report = check(self.dest)
        self.assertFalse(report["ok"])
        self.assertIn("found none", " ".join(report["problems"]))

    def test_readme_only_plan_passes(self):
        self.write_good_plan()
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["plan"], "docs/plans/planned/limit-check/README.md")

    def test_committed_plan_passes(self):
        self.write_good_plan()
        git(self.app, "add", "--all")
        git(self.app, "commit", "-qm", "docs(plan): add limit check plan")
        self.assertTrue(check(self.dest)["ok"])

    def test_one_file_plan_passes(self):
        self.write_good_plan("docs/plans/planned/plc-limit-check.md")
        self.assertTrue(check(self.dest)["ok"])

    def test_full_packet_fails(self):
        self.write_good_plan()
        self.write("docs/plans/planned/limit-check/SRD.md", "# Limit check requirements\n")
        report = check(self.dest)
        self.assertFalse(report["ok"])
        self.assertIn("SRD.md", " ".join(report["problems"]))

    def test_code_change_fails(self):
        self.write_good_plan()
        self.write("harbor.py", "# changed\n")
        report = check(self.dest)
        self.assertFalse(report["ok"])
        self.assertIn("harbor.py", " ".join(report["problems"]))

    def test_plan_outside_planned_fails(self):
        self.write_good_plan("docs/plans/limit-check/README.md")
        self.assertFalse(check(self.dest)["ok"])

    def test_old_compact_shape_fails(self):
        self.write("docs/plans/planned/limit-check/README.md", OLD_COMPACT_PLAN)
        problems = check(self.dest)["problems"]
        self.assertIn("## Log must be the last section", problems)
        self.assertIn("## Phases must follow ## Current Work", problems)


class PacketShapeTest(unittest.TestCase):
    """packet_shape_problems must report each break from the shared template."""

    GOOD = GOOD_PLAN.format(head="abc1234")

    def test_good_plan_has_no_problems(self):
        self.assertEqual(packet_shape_problems(self.GOOD), [])

    def test_each_break_is_reported(self):
        cases = {
            "no summary directly under the title": ("# Limit check\n", "# Limit check\n\n## Note\n"),
            "needs exactly one ## Current Work": (
                "## Log\n",
                "## Current Work\n\n- Status: Planned\n\n## Log\n",
            ),
            "old status section: ## Status": (
                "## Done when",
                "## Status\n\n- Status: Planned\n\n## Done when",
            ),
            "Current Work must start with Status, Owner and Last updated": (
                "- Status: Planned\n- Owner: @alex\n",
                "- Owner: @alex\n- Status: Planned\n",
            ),
            "Status has no packet status word": ("- Status: Planned", "- Status: Waiting"),
            "Owner names nobody by @handle": ("- Owner: @alex", "- Owner: the user"),
            "Last updated does not start with a date": (
                "- Last updated: 2026-11-03",
                "- Last updated: today",
            ),
            "phase row needs every cell and a state word": ("| Planned |", "| Waiting |"),
            "## Phases needs a table with Phase and State columns": (
                "| Phase | Name | Owner | State |",
                "| Phase | Name | Owner | Notes |",
            ),
            "empty section: ## Open questions": ("## Log", "## Open questions\n\n## Log"),
            "## Log must be the last section": ("## Log\n\n- 2026-11-03 Created.\n", ""),
            "placeholder text": ("- Blocker: None", "- Blocker: TBD"),
        }
        for expected, (old, new) in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(old, self.GOOD)
                problems = packet_shape_problems(self.GOOD.replace(old, new, 1))
                self.assertTrue(any(expected in p for p in problems), problems)

    def test_phase_state_table_in_the_plan_is_reported(self):
        plan = "| Phase | Name | Status |\n| --- | --- | --- |\n| P1 | Rows | Merged |\n"
        problems = packet_shape_problems(self.GOOD, plan)
        self.assertEqual(
            problems, ["phase state table outside the README: | Phase | Name | Status |"]
        )


if __name__ == "__main__":
    unittest.main()
