"""The manage-tickets eval fixtures set up their situations, and
check_tickets.py passes a correct result and fails a wrong one.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CASES = EVALS / "manage-tickets"
sys.path.insert(0, str(EVALS))
from fixture_lib import GIT_ENV, git  # noqa: E402 - sys.path is set above
from host_fixture import BRANCH, host_command, host_state  # noqa: E402 - sys.path is set above


class ManageTicketsFixtureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, case: str) -> None:
        subprocess.run(
            [sys.executable, str(CASES / case / "fixture" / "build.py"), str(self.dest)],
            check=True,
            capture_output=True,
            env=GIT_ENV,
        )

    def run_tool(self, *argv: str) -> str:
        """Run a fake CLI from the fixture's bin folder, in the app checkout."""
        env = dict(GIT_ENV, PYTHONDONTWRITEBYTECODE="1")
        env["PATH"] = f"{self.dest / 'bin'}{os.pathsep}{env.get('PATH', '')}"
        result = subprocess.run(
            [*host_command(self.dest, argv[0]), *argv[1:]],
            cwd=self.dest / "app",
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def check(self) -> dict:
        result = subprocess.run(
            [sys.executable, str(CASES / "check_tickets.py"), str(self.dest)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=GIT_ENV,
            check=False,
        )
        return json.loads(result.stdout)

    def assert_common_start(self) -> None:
        app = self.dest / "app"
        self.assertEqual(git(app, "branch", "--show-current"), "main")
        self.assertTrue(git(app, "rev-parse", f"origin/{BRANCH}"))
        self.assertEqual([mr for mr in host_state(self.dest)["mrs"]], [])
        self.assertFalse(self.check()["ok"], "no MR yet must fail the check")

    def test_no_tracker(self):
        self.build("no-tracker")
        self.assert_common_start()
        app = self.dest / "app"
        text = git(app, "log", "--all", "--format=%B") + git(
            app, "grep", "-n", "-I", "-e", "#", "--", ".", check=False
        )
        self.assertNotRegex(text, r"\b[A-Z][A-Z0-9]+-\d+\b|#\d+")
        self.assertNotIn("jira", os.listdir(self.dest / "bin"))

        self.run_tool(
            "glab",
            "mr",
            "create",
            "--source-branch",
            BRANCH,
            "--target-branch",
            "main",
            "--title",
            "Add a backoff delay between retries",
            "--description",
            "Waits longer before each retry, up to two seconds.",
        )
        self.assertEqual(self.check(), {"ok": True, "failures": []})

        self.run_tool("glab", "issue", "create", "--title", "Track backoff", "--description", "x")
        self.assertFalse(self.check()["ok"])

    def test_no_tracker_rejects_an_invented_key(self):
        self.build("no-tracker")
        self.run_tool(
            "glab",
            "mr",
            "create",
            "-s",
            BRANCH,
            "-b",
            "main",
            "-t",
            "APP-1: Add a backoff delay",
            "-d",
            "Waits longer.",
        )
        self.assertFalse(self.check()["ok"])

    def test_jira_key(self):
        self.build("jira-key")
        self.assert_common_start()
        app = self.dest / "app"
        self.assertIn("PROJ-123: ", (app / "CONTRIBUTING.md").read_text(encoding="utf-8"))
        self.assertIn(
            "CI_MERGE_REQUEST_TITLE", (app / ".gitlab-ci.yml").read_text(encoding="utf-8")
        )
        self.assertIn("In Progress", self.run_tool("jira", "issue", "view", "PROJ-481"))

        self.run_tool(
            "glab",
            "mr",
            "create",
            "-s",
            BRANCH,
            "-b",
            "main",
            "-t",
            "PROJ-481: Wait between retries",
            "-d",
            "Adds a capped backoff delay.",
        )
        self.assertEqual(self.check(), {"ok": True, "failures": []})

        self.run_tool("jira", "issue", "move", "PROJ-481", "In Review")
        self.assertFalse(self.check()["ok"], "a Jira write the rules leave to automation")

    def test_jira_key_in_the_wrong_form_fails(self):
        self.build("jira-key")
        self.run_tool(
            "glab",
            "mr",
            "create",
            "-s",
            BRANCH,
            "-b",
            "main",
            "-t",
            "Wait between retries [PROJ-481]",
            "-d",
            "Adds a capped backoff delay.",
        )
        self.assertFalse(self.check()["ok"])

    def test_github_closes(self):
        self.build("github-closes")
        self.assert_common_start()
        app = self.dest / "app"
        self.assertIn(
            "Closes #", (app / ".github/pull_request_template.md").read_text(encoding="utf-8")
        )
        self.assertIn("Closes #11", git(app, "log", "--format=%B"))
        self.assertIn("[open]", self.run_tool("gh", "issue", "view", "42"))

        body = self.dest / "body.md"
        body.write_text(
            "## What and why\n\nWaits between retries.\n\nCloses #42\n", encoding="utf-8"
        )
        self.run_tool(
            "gh",
            "pr",
            "create",
            "--head",
            BRANCH,
            "--base",
            "main",
            "--title",
            "Wait between retries",
            "--body-file",
            str(body),
        )
        self.assertEqual(self.check(), {"ok": True, "failures": []})

        self.run_tool("gh", "issue", "close", "42")
        self.assertFalse(self.check()["ok"], "closing is the merge's job")

    def test_github_partial_reference_fails(self):
        self.build("github-closes")
        self.run_tool(
            "gh",
            "pr",
            "create",
            "--head",
            BRANCH,
            "--base",
            "main",
            "--title",
            "Wait between retries",
            "--body",
            "Refs #42",
        )
        self.assertFalse(self.check()["ok"])


if __name__ == "__main__":
    unittest.main()
