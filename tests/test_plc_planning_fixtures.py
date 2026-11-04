import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CASES = EVALS / "plc-planning"
sys.path.insert(0, str(EVALS))
from fixture_lib import GIT_ENV, git, packet_shape_problems, write  # noqa: E402

PLAN_PATH = "docs/plans/planned/limit-check/README.md"

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
        env=GIT_ENV,
    )


def check(dest: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(CASES / "check_plan.py"), str(dest)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=GIT_ENV,
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

    def write_good_plan(self, relative: str = PLAN_PATH, owner: str = "@alex") -> None:
        text = GOOD_PLAN.format(head=self.head).replace("- Owner: @alex", f"- Owner: {owner}")
        write(self.app, {relative: text})

    def run_in_app(self, *args: str) -> subprocess.CompletedProcess:
        # Bytecode writing stays on, as on most machines; the fixture's
        # .gitignore must keep the checkout clean anyway.
        env = {key: value for key, value in GIT_ENV.items() if key != "PYTHONDONTWRITEBYTECODE"}
        return subprocess.run(
            [sys.executable, *args],
            cwd=self.app,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def test_fixture_has_the_bug_and_no_plan(self):
        tests = self.run_in_app("-m", "unittest")
        self.assertEqual(tests.returncode, 0, tests.stderr)
        listed = self.run_in_app("harbor.py", "list", "--limit", "-1")
        self.assertEqual(listed.stdout.split(), ["A1", "A2", "B1", "B2"])
        plans_readme = (self.app / "docs/plans/README.md").read_text(encoding="utf-8")
        self.assertIn("`planned/`", plans_readme)
        self.assertFalse((self.app / "docs/plans/planned").exists())
        self.assertEqual(git(self.app, "status", "--porcelain"), "")
        self.assertEqual(
            check(self.dest),
            {
                "ok": False,
                "plan": None,
                "changed": [],
                "problems": ["expected one new plan in docs/plans/planned/, found none"],
            },
        )

    def test_readme_only_plan_passes(self):
        self.write_good_plan()
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["plan"], PLAN_PATH)

    def test_committed_plan_passes(self):
        self.write_good_plan()
        git(self.app, "add", "--all")
        git(self.app, "commit", "-qm", "docs(plan): add limit check plan")
        self.assertTrue(check(self.dest)["ok"])

    def test_one_file_plan_passes(self):
        self.write_good_plan("docs/plans/planned/plc-limit-check.md")
        self.assertTrue(check(self.dest)["ok"])

    def test_one_file_plan_without_the_plc_prefix_fails(self):
        self.write_good_plan("docs/plans/planned/limit-check.md")
        self.assertEqual(
            check(self.dest)["problems"],
            [
                "changed beyond the one plan file: ['docs/plans/planned/limit-check.md']",
                "expected one new plan in docs/plans/planned/, found none",
            ],
        )

    def test_two_plans_fail(self):
        self.write_good_plan()
        self.write_good_plan("docs/plans/planned/plc-limit-check.md")
        self.assertEqual(
            check(self.dest)["problems"],
            [
                "expected one new plan in docs/plans/planned/, found "
                f"['docs/plans/planned/limit-check/README.md', "
                f"'docs/plans/planned/plc-limit-check.md']"
            ],
        )

    def test_full_packet_fails(self):
        self.write_good_plan()
        write(self.app, {"docs/plans/planned/limit-check/SRD.md": "# Requirements\n"})
        self.assertEqual(
            check(self.dest)["problems"],
            ["changed beyond the one plan file: ['docs/plans/planned/limit-check/SRD.md']"],
        )

    def test_code_change_fails(self):
        self.write_good_plan()
        write(self.app, {"harbor.py": "# changed\n"})
        self.assertEqual(
            check(self.dest)["problems"], ["changed beyond the one plan file: ['harbor.py']"]
        )

    def test_plan_outside_planned_fails(self):
        self.write_good_plan("docs/plans/limit-check/README.md")
        self.assertFalse(check(self.dest)["ok"])

    def test_other_owner_fails(self):
        self.write_good_plan(owner="@sam")
        self.assertEqual(check(self.dest)["problems"], ["Owner does not name @alex"])

    def test_owner_with_a_longer_handle_fails(self):
        self.write_good_plan(owner="@alex-b")
        self.assertEqual(check(self.dest)["problems"], ["Owner does not name @alex"])

    def test_rewritten_history_fails(self):
        self.write_good_plan()
        git(self.app, "add", "--all")
        git(self.app, "commit", "-q", "--amend", "-m", "feat: list free berths, with a plan")
        problems = check(self.dest)["problems"]
        self.assertEqual(problems[0], "history rewritten or reset")

    def test_old_compact_shape_fails(self):
        write(self.app, {PLAN_PATH: OLD_COMPACT_PLAN})
        problems = check(self.dest)["problems"]
        self.assertIn("needs a ## Phases section", problems)
        self.assertIn("## Log must be the last section", problems)


class PacketShapeTest(unittest.TestCase):
    """packet_shape_problems must report each break from the shared template."""

    GOOD = GOOD_PLAN.format(head="abc1234")
    ROW_PROBLEM = "phase row needs every cell and a state word"

    def test_good_plan_has_no_problems(self):
        self.assertEqual(packet_shape_problems(self.GOOD), [])

    def test_each_break_is_reported(self):
        thirteen_keys = "".join(f"- Extra key {letter}: x\n" for letter in "ABCDE")
        cases = {
            "no summary directly under the title": (
                "# Limit check\n",
                "# Limit check\n\n## Note\n",
            ),
            "needs exactly one ## Current Work": (
                "## Log\n",
                "## Current Work\n\n- Status: Planned\n\n## Log\n",
            ),
            "old status section: ## Status": (
                "## Log",
                "## Status\n\n- Status: Planned\n\n## Log",
            ),
            "old status section: ## Lifecycle": ("## Log", "## Lifecycle\n\nPlanned.\n\n## Log"),
            "Current Work must start with Status, Owner and Last updated": (
                "- Status: Planned\n- Owner: @alex\n",
                "- Owner: @alex\n- Status: Planned\n",
            ),
            "Current Work has 13 keys (at most 12)": (
                "- Resume check:",
                f"{thirteen_keys}- Resume check:",
            ),
            "Status has no packet status word": ("- Status: Planned", "- Status: Waiting"),
            "Owner names nobody by @handle": ("- Owner: @alex", "- Owner: the user"),
            "Last updated does not start with a date": (
                "- Last updated: 2026-11-03",
                "- Last updated: today",
            ),
            f"{self.ROW_PROBLEM}: | P1 | Reject limits below 1 | Planned |": (
                "| P1 | Reject limits below 1 | | Planned |",
                "| P1 | Reject limits below 1 | Planned |",
            ),
            self.ROW_PROBLEM: ("| Planned |", "| Waiting |"),
            "## Phases needs a table with Phase and State columns": (
                "| Phase | Name | Owner | State |",
                "| Phase | Name | Owner | Notes |",
            ),
            "sections out of template order": (
                "## Done when",
                "## Notes\n\nA repository section.\n\n## Done when",
            ),
            "empty section: ## Open questions": ("## Log", "## Open questions\n\n## Log"),
            "## Log must be the last section": ("## Log\n\n- 2026-11-03 Created.\n", ""),
            "Log line has no date: - Created.": ("- 2026-11-03 Created.", "- Created."),
            "placeholder text": ("- Blocker: None", "- Blocker: TBD"),
        }
        for expected, (old, new) in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(old, self.GOOD)
                problems = packet_shape_problems(self.GOOD.replace(old, new, 1))
                self.assertTrue(any(expected in p for p in problems), problems)

    def test_placeholder_in_code_is_allowed(self):
        text = self.GOOD.replace(
            "Check: `python -m unittest`",
            "Check: `harbor list --limit <n>` and `python -m unittest`",
        )
        self.assertEqual(packet_shape_problems(text), [])
        fenced = self.GOOD.replace(
            "## Log", "```sh\nharbor list --limit <n>\n## Not a heading\n```\n\n## Log"
        )
        self.assertEqual(packet_shape_problems(fenced), [])

    def test_placeholder_outside_code_is_reported(self):
        text = self.GOOD.replace("- Blocker: None", "- Blocker: <what is needed>")
        self.assertEqual(
            packet_shape_problems(text),
            ["placeholder text (N/A, TBD or <...>) left in the README"],
        )

    def test_autolink_is_not_a_placeholder(self):
        text = self.GOOD.replace(
            "- Blocker: None", "- Blocker: None, see <https://example.invalid/x>"
        )
        self.assertEqual(packet_shape_problems(text), [])

    def test_phase_state_table_in_the_plan_is_reported(self):
        plan = "| Phase | Name | Status |\n| --- | --- | --- |\n| P1 | Rows | Merged |\n"
        problems = packet_shape_problems(self.GOOD, plan)
        self.assertEqual(
            problems, ["phase state table outside the README: | Phase | Name | Status |"]
        )

    def test_phase_link_to_a_missing_plan_heading_is_reported(self):
        text = self.GOOD.replace(
            "| P1 | Reject limits below 1 |",
            "| P1 | [Reject limits below 1](IMPLEMENTATION_PLAN.md#p1-reject-limits-below-1) |",
        )
        self.assertEqual(
            packet_shape_problems(text, "### P1: Reject limits below 1\n\n- Check: x\n"), []
        )
        self.assertEqual(
            packet_shape_problems(text, "### P1: Something else\n\n- Check: x\n"),
            ["phase row links to a missing plan heading: #p1-reject-limits-below-1"],
        )


if __name__ == "__main__":
    unittest.main()
