"""Check that the skill evaluation fixtures exercise their stated cases."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CHECKER = EVALS / "plc-checkpoint" / "check_state.py"


class SkillEvalFixtureTests(unittest.TestCase):
    def build(self, name):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        dest = Path(folder.name)
        subprocess.run(
            [sys.executable, str(EVALS / name / "fixture" / "build.py"), str(dest)],
            check=True,
            capture_output=True,
        )
        return dest

    def check_read_only(self, dest):
        return subprocess.run(
            [sys.executable, str(CHECKER), str(dest), "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_stale_discovery_rejects_a_detached_head(self):
        dest = self.build("plc-execution/stale-todo")
        result = self.check_read_only(dest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        subprocess.run(
            ["git", "-C", str(dest / "reload"), "checkout", "--detach"],
            check=True,
            capture_output=True,
        )
        self.assertEqual(self.check_read_only(dest).returncode, 1)

    def test_conflicting_rerun_protects_both_records(self):
        dest = self.build("verify-before-claiming/conflicting-rerun")
        evidence = dest / "reload" / "ci-evidence"
        first = (evidence / "attempt-1.txt").read_text().splitlines()
        second_path = evidence / "attempt-2.txt"
        second = second_path.read_text().splitlines()
        self.assertEqual(first[:4], second[:4])
        self.assertEqual(first[4:], ["Exit: 1", "Active config was replaced."])
        self.assertEqual(second[4:], ["Exit: 0", "Active config was preserved."])
        result = self.check_read_only(dest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        second_path.write_text("changed")
        self.assertEqual(self.check_read_only(dest).returncode, 1)

    def test_bounded_experiment_starts_with_two_loader_calls(self):
        checkout = self.build("performance-experiments/duplicate-load") / "score"
        for mode, stdout in (("benchmark", "loader_calls=2"), ("correctness", "")):
            result = subprocess.run(
                [sys.executable, "check.py", mode],
                cwd=checkout,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), stdout)
