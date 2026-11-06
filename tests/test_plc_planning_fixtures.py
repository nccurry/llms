import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CASES = EVALS / "plc-planning"
sys.path.insert(0, str(EVALS))
from fixture_lib import (  # noqa: E402 - sys.path is set above
    GIT_ENV,
    OWNER,
    eval_only_problems,
    format_check,
    git,
    packet_shape_problems,
    write,
)

# The one shape the case grades: a one-file plan in planned/.
PLAN_PATH = "docs/plans/planned/plc-limit-check.md"

# A one-file plan in the shared PLC template, as the small-change case
# expects. `{head}` is the fixture's commit.
GOOD_PLAN = """# Limit check

Make `harbor list --limit` reject a limit below 1 with a clear error, instead
of printing nothing or dropping berths.

## Current Work

- Status: Planned
- Owner: @alex
- Last updated: 2026-11-03, `main` at `{head}`
- Next action: Write a failing test for `--limit 0` in `tests/test_harbor.py`.
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
        check=False,
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
        # Bytecode writing stays on, with no cache folder elsewhere, as on
        # most machines; the fixture's .gitignore must keep the checkout clean.
        off = ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")
        env = {key: value for key, value in GIT_ENV.items() if key not in off}
        return subprocess.run(
            [sys.executable, *args],
            cwd=self.app,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )

    def test_fixture_has_the_bug_and_no_plan(self):
        tests = self.run_in_app("-m", "unittest")
        self.assertEqual(tests.returncode, 0, tests.stderr)
        listed = self.run_in_app("harbor.py", "list", "--limit", "-1")
        self.assertEqual(listed.stdout.split(), ["A1", "A2", "B1", "B2"])
        self.assertTrue(any(self.app.rglob("__pycache__")))
        plans_readme = (self.app / "docs/plans/README.md").read_text(encoding="utf-8")
        self.assertIn("`planned/`", plans_readme)
        self.assertIn("`plc-<slug>.md`", plans_readme)
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

    def test_one_file_plan_passes(self):
        self.write_good_plan()
        findings = format_check().check_packet(self.app / PLAN_PATH, strict=True)
        self.assertEqual(findings, [])
        report = check(self.dest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["plan"], PLAN_PATH)

    def test_one_small_diagram_passes(self):
        # The skill encourages diagrams without requiring them. The checker
        # accepts one small, apt diagram; the grader judges padding.
        self.write_good_plan()
        plan = self.app / PLAN_PATH
        tree = "```text\nharbor.py\ntests/\n  test_harbor.py\n```"
        text = plan.read_text(encoding="utf-8")
        row = "| P1 | Reject limits below 1 | | Planned |\n"
        text = text.replace(row, f"{row}\nP1 changes these files:\n\n{tree}\n", 1)
        plan.write_text(text, encoding="utf-8")
        self.assertIn(tree, plan.read_text(encoding="utf-8"))
        self.assertEqual(format_check().check_packet(plan, strict=True), [])
        self.assertTrue(check(self.dest)["ok"])

    def test_committed_plan_passes(self):
        self.write_good_plan()
        git(self.app, "add", "--all")
        git(self.app, "commit", "-qm", "docs(plan): add limit check plan")
        self.assertTrue(check(self.dest)["ok"])

    def test_packet_folder_fails(self):
        # The skill and the repository both say a small plan is one file.
        folder_readme = "docs/plans/planned/limit-check/README.md"
        self.write_good_plan(folder_readme)
        self.assertEqual(
            check(self.dest)["problems"],
            [
                f"changed beyond the one plan file: ['{folder_readme}']",
                "expected one new plan in docs/plans/planned/, found none",
            ],
        )

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
        self.write_good_plan("docs/plans/planned/plc-limit-check-later.md")
        self.assertEqual(
            check(self.dest)["problems"],
            [
                "expected one new plan in docs/plans/planned/, found "
                "['docs/plans/planned/plc-limit-check-later.md', "
                "'docs/plans/planned/plc-limit-check.md']"
            ],
        )

    def test_side_file_beside_the_plan_fails(self):
        self.write_good_plan()
        write(self.app, {"docs/plans/planned/plc-limit-check-srd.md": "# Requirements\n"})
        self.assertEqual(
            check(self.dest)["problems"],
            ["changed beyond the one plan file: ['docs/plans/planned/plc-limit-check-srd.md']"],
        )

    def test_code_change_fails(self):
        self.write_good_plan()
        write(self.app, {"harbor.py": "# changed\n"})
        self.assertEqual(
            check(self.dest)["problems"], ["changed beyond the one plan file: ['harbor.py']"]
        )

    def test_plan_outside_planned_fails(self):
        self.write_good_plan("docs/plans/plc-limit-check.md")
        self.assertEqual(
            check(self.dest)["problems"],
            [
                "changed beyond the one plan file: ['docs/plans/plc-limit-check.md']",
                "expected one new plan in docs/plans/planned/, found none",
            ],
        )

    def test_other_owner_fails(self):
        self.write_good_plan(owner="@sam")
        self.assertEqual(check(self.dest)["problems"], ["eval: Owner does not name @alex"])

    def test_owner_with_a_longer_handle_fails(self):
        self.write_good_plan(owner="@alex-b")
        self.assertEqual(check(self.dest)["problems"], ["eval: Owner does not name @alex"])

    def test_plan_in_planned_must_say_planned(self):
        self.write_good_plan()
        plan = self.app / PLAN_PATH
        text = plan.read_text(encoding="utf-8")
        text = text.replace("- Status: Planned", "- Status: In progress")
        plan.write_text(text, encoding="utf-8")
        self.assertEqual(
            check(self.dest)["problems"],
            [
                f"{PLAN_PATH}:8: strict: Status In progress does not match the planned/ folder,"
                " which needs Planned or Blocked"
            ],
        )

    def test_rewritten_history_fails(self):
        self.write_good_plan()
        git(self.app, "add", "--all")
        git(self.app, "commit", "-q", "--amend", "-m", "feat: list free berths, with a plan")
        self.assertEqual(check(self.dest)["problems"], ["history rewritten or reset"])

    def test_old_compact_shape_fails(self):
        write(self.app, {PLAN_PATH: OLD_COMPACT_PLAN})
        problems = check(self.dest)["problems"]
        self.assertIn("eval: no ## Phases section", problems)
        self.assertIn(f"{PLAN_PATH}:1: Log: no ## Log section", problems)
        self.assertIn("eval: ## Log is not the last section", problems)
        self.assertIn("eval: Current Work has no Resume check line", problems)


class PacketShapeTest(unittest.TestCase):
    """packet_shape_problems must report each break from the shared template,
    from the shipped format check or from the evals' own rules.
    """

    GOOD = GOOD_PLAN.format(head="abc1234")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # A plain folder, not a lifecycle folder, so no folder rule applies.
        self.packet = Path(self.tmp.name) / "plans" / "limit-check"

    def tearDown(self):
        self.tmp.cleanup()

    def problems(self, readme: str, plan: str = "", owner: str | None = None) -> list[str]:
        files = {"README.md": readme}
        if plan:
            files["IMPLEMENTATION_PLAN.md"] = plan
        write(self.packet, files)
        return packet_shape_problems(self.packet, owner=owner)

    def test_good_plan_has_no_problems(self):
        self.assertEqual(self.problems(self.GOOD, owner=OWNER), [])

    def test_each_break_is_reported(self):
        thirteen_keys = "".join(f"- Extra key {letter}: x\n" for letter in "ABCDE")
        row_cells = "Phases: row has 3 cells, but the header has 4"
        cases = {
            "summary: no paragraph directly under the title": (
                "# Limit check\n",
                "# Limit check\n\n## Note\n",
            ),
            "Current Work: 2 ## Current Work sections; a packet needs exactly one": (
                "## Log\n",
                "## Current Work\n\n- Status: Planned\n\n## Log\n",
            ),
            "Current Work: Status line belongs in ## Current Work, not ## Status": (
                "## Log",
                "## Status\n\n- Status: Planned\n\n## Log",
            ),
            "Current Work: Status line belongs in ## Current Work, not ## Lifecycle": (
                "## Log",
                "## Lifecycle\n\n- Status: Planned\n\n## Log",
            ),
            "Current Work: Status, Owner and Last updated must come first, in that order": (
                "- Status: Planned\n- Owner: @alex\n",
                "- Owner: @alex\n- Status: Planned\n",
            ),
            "Current Work: 13 keys; at most 12 are allowed": (
                "- Resume check:",
                f"{thirteen_keys}- Resume check:",
            ),
            "Current Work: Status does not start with a packet status word: Waiting": (
                "- Status: Planned",
                "- Status: Waiting",
            ),
            "Current Work: Owner names no @handle": ("- Owner: @alex", "- Owner: the user"),
            "Current Work: Last updated does not start with a YYYY-MM-DD date": (
                "- Last updated: 2026-11-03",
                "- Last updated: today",
            ),
            row_cells: (
                "| P1 | Reject limits below 1 | | Planned |",
                "| P1 | Reject limits below 1 | Planned |",
            ),
            "Phases: State does not start with a phase state word: Waiting": (
                "| Planned |",
                "| Waiting |",
            ),
            "Phases: the ## Phases table has no State column": (
                "| Phase | Name | Owner | State |",
                "| Phase | Name | Owner | Notes |",
            ),
            "Log: no ## Log section": ("## Log\n\n- 2026-11-03 Created.\n", ""),
            "eval: sections out of template order": (
                "## Done when",
                "## Notes\n\nA repository section.\n\n## Done when",
            ),
            "eval: empty section ## Open questions": ("## Log", "## Open questions\n\n## Log"),
            "eval: ## Log is not the last section": (
                "## Log\n\n- 2026-11-03 Created.\n",
                "## Log\n\n- 2026-11-03 Created.\n\n## Notes\n\nAfter the Log.\n",
            ),
            "eval: Log line has no date: - Created.": ("- 2026-11-03 Created.", "- Created."),
            "eval: placeholder text": ("- Blocker: None", "- Blocker: TBD"),
            "eval: no ## Phases section": (
                "## Phases\n\n| Phase | Name | Owner | State |\n| --- | --- | --- | --- |\n"
                "| P1 | Reject limits below 1 | | Planned |\n\n",
                "",
            ),
        }
        for expected, (old, new) in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(old, self.GOOD)
                problems = self.problems(self.GOOD.replace(old, new, 1))
                self.assertTrue(any(expected in problem for problem in problems), problems)

    def test_placeholder_in_code_is_allowed(self):
        text = self.GOOD.replace(
            "Check: `python -m unittest`",
            "Check: `harbor list --limit <n>` and `python -m unittest`",
        )
        self.assertEqual(self.problems(text), [])
        fenced = self.GOOD.replace(
            "## Log", "```sh\nharbor list --limit <n>\n## Not a heading\n```\n\n## Log"
        )
        self.assertEqual(self.problems(fenced), [])

    def test_placeholder_outside_code_is_reported(self):
        text = self.GOOD.replace("- Blocker: None", "- Blocker: <what is needed>")
        self.assertEqual(
            self.problems(text), ["eval: placeholder text (N/A, TBD or <...>) left in the README"]
        )

    def test_autolink_is_not_a_placeholder(self):
        text = self.GOOD.replace(
            "- Blocker: None", "- Blocker: None, see <https://example.invalid/x>"
        )
        self.assertEqual(self.problems(text), [])

    def test_phase_state_table_in_the_plan_is_reported(self):
        plan = "| Phase | Name | Status |\n| --- | --- | --- |\n| P1 | Rows | Merged |\n"
        problems = self.problems(self.GOOD, plan)
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(
            problems[0].endswith(
                "IMPLEMENTATION_PLAN.md:1: Phases: phase state outside the README ## Phases table"
            ),
            problems,
        )

    def test_phase_link_to_a_missing_plan_heading_is_reported(self):
        text = self.GOOD.replace(
            "| P1 | Reject limits below 1 |",
            "| P1 | [Reject limits below 1](IMPLEMENTATION_PLAN.md#p1-reject-limits-below-1) |",
        )
        self.assertEqual(self.problems(text, "### P1: Reject limits below 1\n\n- Check: x\n"), [])
        self.assertEqual(
            self.problems(text, "### P1: Something else\n\n- Check: x\n"),
            ["eval: phase row links to a missing plan heading: #p1-reject-limits-below-1"],
        )

    def test_n_a_is_a_placeholder(self):
        text = self.GOOD.replace("- Blocker: None", "- Blocker: N/A")
        self.assertEqual(
            self.problems(text), ["eval: placeholder text (N/A, TBD or <...>) left in the README"]
        )

    def test_log_line_with_only_a_month_is_reported(self):
        text = self.GOOD.replace("- 2026-11-03 Created.", "- 2026-11 Created.")
        self.assertEqual(self.problems(text), ["eval: Log line has no date: - 2026-11 Created."])

    def test_log_date_followed_by_punctuation_passes(self):
        text = self.GOOD.replace("- 2026-11-03 Created.", "- 2026-11-03: Created.")
        self.assertEqual(self.problems(text), [])

    def test_every_template_key_and_the_work_table_are_required(self):
        no_resume = self.GOOD.replace("- Resume check: `python -m unittest` → OK\n", "")
        self.assertEqual(self.problems(no_resume), ["eval: Current Work has no Resume check line"])
        no_table = self.GOOD.replace(
            "Where the work lives:\n\n| Checkout | Branch | Owner | State |\n"
            "| --- | --- | --- | --- |\n| None | | | |\n\n",
            "",
        )
        self.assertEqual(
            self.problems(no_table), ['eval: Current Work has no "Where the work lives" table']
        )

    def test_fenced_content_counts_as_content(self):
        text = self.GOOD.replace(
            "## Log", "## Commands\n\n```sh\nharbor list --limit 1\n```\n\n## Log"
        )
        self.assertEqual(self.problems(text), [])
        empty = self.GOOD.replace("## Log", "## Commands\n\n## Log")
        self.assertEqual(self.problems(empty), ["eval: empty section ## Commands"])

    def test_bold_keys_and_escaped_pipes_get_the_same_verdict_from_both_layers(self):
        """The evals' own rules read keys and table cells as the shipped check does."""
        bold = (
            self.GOOD.replace("- Status: Planned", "- **Status:** Planned")
            .replace("- Owner: @alex", "- **Owner:** @alex")
            .replace("- Last updated:", "- **Last updated:**")
        )
        piped = self.GOOD.replace(
            "| P1 | Reject limits below 1 | | Planned |",
            "| P1 | [Limits a \\| b](IMPLEMENTATION_PLAN.md#p1-limits-a--b) | | Planned |",
        )
        plan = "### P1: Limits a | b\n\n- Check: x\n"
        cases = [
            ("bold keys", bold, "", True),
            ("escaped pipe in a phase row", piped, plan, True),
            (
                "bold Owner with no handle",
                bold.replace("**Owner:** @alex", "**Owner:** Sam"),
                "",
                False,
            ),
        ]
        for name, readme, plan_text, good in cases:
            with self.subTest(case=name):
                files = {"README.md": readme}
                if plan_text:
                    files["IMPLEMENTATION_PLAN.md"] = plan_text
                write(self.packet, files)
                shipped = format_check().check_packet(self.packet, strict=True)
                own = eval_only_problems(self.packet, owner=OWNER)
                self.assertEqual((shipped == [], own == []), (good, good), (shipped, own))


if __name__ == "__main__":
    unittest.main()
