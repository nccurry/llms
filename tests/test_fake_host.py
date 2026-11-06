"""The fake code host behaves like the real tools on the calls agents probe:
`--help` changes nothing, an empty note is refused, and `-q`/`--jq`
returns the selected field."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
sys.path.insert(0, str(EVALS))
from fixture_lib import GIT_ENV  # noqa: E402


class FakeHostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"
        subprocess.run(
            [
                sys.executable,
                str(EVALS / "plc-mr-review" / "ready-no-plan" / "fixture" / "build.py"),
                str(self.dest),
            ],
            check=True,
            capture_output=True,
            env=GIT_ENV,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(GIT_ENV, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [str(self.dest / "bin" / args[0]), *args[1:]],
            cwd=self.dest / "app",
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def notes(self) -> int:
        state = json.loads((self.dest / "_host" / "state.json").read_text(encoding="utf-8"))
        return sum(len(t["notes"]) for mr in state["mrs"] for t in mr["discussions"])

    def test_help_changes_nothing(self):
        before = self.notes()
        result = self.run_tool("glab", "mr", "note", "7", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.notes(), before)

    def test_empty_note_is_refused(self):
        before = self.notes()
        self.assertNotEqual(self.run_tool("glab", "mr", "note", "7").returncode, 0)
        self.assertEqual(self.notes(), before)

    def test_jq_selects_a_field(self):
        result = self.run_tool("glab", "mr", "view", "7", "--output", "json", "--jq", ".title")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(result.stdout.lstrip().startswith("{"))


if __name__ == "__main__":
    unittest.main()
