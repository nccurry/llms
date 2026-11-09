"""Check the new eval fixtures and their scope/provenance checker, not agent behavior."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CASES = Path(__file__).parent / "skill-evals/plc-planning"
spec = importlib.util.spec_from_file_location("check_readable", CASES / "check_readable.py")
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReadablePlanFixtureTest(unittest.TestCase):
    def build(self, case):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        dest = Path(temp.name) / "fixture"
        subprocess.run(
            [sys.executable, str(CASES / "readable_fixture.py"), case, str(dest)],
            check=True,
            capture_output=True,
        )
        return dest

    def test_new_plan_cases_require_a_generated_packet(self):
        for case in ("substantial-phase", "design-comparison"):
            with self.subTest(case=case):
                dest = self.build(case)
                self.assertFalse(checker.check(dest)["ok"])

    def test_evidence_preservation_and_scope(self):
        dest = self.build("growing-evidence")
        self.assertFalse(checker.check(dest)["ok"])
        app = dest / "harbor"
        plan = app / "docs/plans/in-progress/reload/IMPLEMENTATION_PLAN.md"
        plan.write_text(plan.read_text() + "\n" + (app / "receipts.md").read_text())
        self.assertTrue(checker.check(dest)["ok"], checker.check(dest))
        preserved = plan.read_text()
        plan.write_text(preserved.replace("supplied fixture facts", "fixture facts"))
        self.assertIn("missing supplied-result attribution", checker.check(dest)["problems"])
        plan.write_text(preserved)
        readme = app / "docs/plans/in-progress/reload/README.md"
        readme.write_text(
            readme.read_text().replace(
                "| In progress |",
                "| In progress — [parser](IMPLEMENTATION_PLAN.md#parser-checks) |",
            )
        )
        self.assertTrue(checker.check(dest)["ok"], checker.check(dest))
        readme.write_text(readme.read_text().replace("#parser-checks", "#missing-heading"))
        self.assertTrue(
            any("missing plan heading" in item for item in checker.check(dest)["problems"])
        )
        plan.write_text(plan.read_text().replace("abc1234", "other-source"))
        self.assertIn("missing evidence fact: abc1234", checker.check(dest)["problems"])
        (app / "harbor.py").write_text("changed application code\n")
        self.assertIn("changed files outside docs/plans", checker.check(dest)["problems"])


if __name__ == "__main__":
    unittest.main()
