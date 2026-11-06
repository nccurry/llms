"""The lint and Pester runners load the pinned modules, even when another copy is installed."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pinned_powershell

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / ".tools/powershell-modules"
DECOY_VERSION = "99.0.0"


class PinnedModuleTests(unittest.TestCase):
    def setUp(self):
        self.pwsh = pinned_powershell.require_pwsh(self)
        if not (MODULES / "PSScriptAnalyzer").is_dir() or not (MODULES / "Pester").is_dir():
            if os.environ.get("LLMS_REQUIRE_PINNED_TOOLS"):
                self.fail("The PowerShell modules are missing; run `task deps:dev-tools`.")
            self.skipTest("The PowerShell modules are not installed; run `task deps:dev-tools`.")
        # A home folder whose user module folder holds a newer decoy of each module.
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        for name in ("PSScriptAnalyzer", "Pester"):
            folder = self.home / ".local/share/powershell/Modules" / name / DECOY_VERSION
            folder.mkdir(parents=True)
            (folder / f"{name}.psm1").write_text("throw 'the decoy module was loaded'\n")
            (folder / f"{name}.psd1").write_text(
                f"@{{ RootModule = '{name}.psm1'; ModuleVersion = '{DECOY_VERSION}';"
                " GUID = '7c1f6a0e-1111-4222-8333-444455556666' }\n"
            )
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PSModulePath": str(MODULES),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
        }

    def powershell(self, *arguments):
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-NonInteractive", *arguments],
            check=False,
            capture_output=True,
            encoding="utf-8",
            env=self.env,
            cwd=ROOT,
            timeout=300,
        )

    def test_the_decoy_shadows_the_pinned_module_for_a_plain_import(self):
        # Without this, the tests below would pass whether or not the runners guard against it.
        result = self.powershell(
            "-Command",
            "(Get-Module -ListAvailable PSScriptAnalyzer | Select-Object -First 1).Version"
            ".ToString()",
        )
        self.assertEqual(result.stdout.strip(), DECOY_VERSION, result.stderr)

    def test_the_analyzer_runner_loads_the_pinned_copy(self):
        result = self.powershell("-File", str(ROOT / "lint/run_psscriptanalyzer.ps1"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"PSScriptAnalyzer 1.25.0 from {MODULES}", result.stdout)
        self.assertNotIn("decoy", result.stdout + result.stderr)

    def test_the_pester_runner_loads_the_pinned_copy(self):
        result = self.powershell("-File", str(ROOT / "lint/run_pester.ps1"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"Pester 6.2.0 from {MODULES}", result.stdout)
        self.assertNotIn("decoy", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
