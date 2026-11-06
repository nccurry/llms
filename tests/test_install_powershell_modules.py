"""lint/install_powershell_modules.py unpacks a package only when its SHA-256 matches its pin."""

import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "install_powershell_modules", ROOT / "lint/install_powershell_modules.py"
)
assert spec is not None and spec.loader is not None
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def package(manifest="@{ ModuleVersion = '1.0.0' }"):
    """Return the bytes of a small zip that looks like a PowerShell Gallery package."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Demo.psd1", manifest)
        archive.writestr("en-US/about_Demo.help.txt", "help")
    return buffer.getvalue()


class InstallPowerShellModulesTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.modules = self.directory / "modules"
        # Any real download would reach urlopen, so this makes the tests fail rather than go online.
        offline = patch.object(
            installer.urllib.request, "urlopen", side_effect=AssertionError("network used")
        )
        offline.start()
        self.addCleanup(offline.stop)

    def serve(self, content):
        """Make every download return `content`, and remember the URLs asked for."""
        self.urls = []

        def download(url):
            self.urls.append(url)
            return content

        patcher = patch.object(installer, "download", side_effect=download)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_matching_checksum_unpacks_the_package_into_name_and_version(self):
        content = package()
        self.serve(content)
        with contextlib.redirect_stdout(io.StringIO()):
            installer.install_module(
                "Demo", "1.0.0", hashlib.sha256(content).hexdigest(), self.modules
            )
        folder = self.modules / "Demo" / "1.0.0"
        self.assertEqual((folder / "Demo.psd1").read_text(), "@{ ModuleVersion = '1.0.0' }")
        self.assertTrue((folder / "en-US/about_Demo.help.txt").is_file())
        self.assertEqual(self.urls, ["https://www.powershellgallery.com/api/v2/package/Demo/1.0.0"])

    def test_a_checksum_mismatch_raises_and_leaves_nothing_unpacked(self):
        self.serve(package())
        wrong = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            installer.install_module("Demo", "1.0.0", wrong, self.modules)
        self.assertFalse((self.modules / "Demo" / "1.0.0").exists())

    def test_a_mismatch_keeps_an_earlier_good_install(self):
        good = package()
        self.serve(good)
        with contextlib.redirect_stdout(io.StringIO()):
            installer.install_module(
                "Demo", "1.0.0", hashlib.sha256(good).hexdigest(), self.modules
            )
        self.serve(package("tampered"))
        with self.assertRaises(ValueError):
            installer.install_module(
                "Demo", "1.0.0", hashlib.sha256(good).hexdigest(), self.modules
            )
        self.assertEqual(
            (self.modules / "Demo" / "1.0.0" / "Demo.psd1").read_text(),
            "@{ ModuleVersion = '1.0.0' }",
        )

    def test_main_reports_a_mismatch_with_exit_code_1_and_removes_other_versions(self):
        content = package()
        self.serve(content)
        stale = self.modules / "Demo" / "0.9.0"
        stale.mkdir(parents=True)
        pins = self.directory / "pins.json"
        pins.write_text(
            json.dumps({"modules": {"Demo": {"version": "1.0.0", "sha256": "0" * 64}}}),
            encoding="utf-8",
        )
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            code = installer.main([str(pins), str(self.modules)])
        self.assertEqual(code, 1)
        self.assertIn("SHA-256 mismatch", errors.getvalue())
        self.assertFalse((self.modules / "Demo" / "1.0.0").exists())
        self.assertFalse(stale.exists())

    def test_download_refuses_a_URL_that_is_not_https(self):
        with self.assertRaisesRegex(ValueError, "non-https"):
            installer.download("http://example.invalid/package")

    def test_the_pinned_modules_file_names_both_modules_with_sha256_values(self):
        pins = json.loads((ROOT / "lint/powershell-modules.json").read_text(encoding="utf-8"))
        self.assertEqual(set(pins["modules"]), {"Pester", "PSScriptAnalyzer"})
        for pin in pins["modules"].values():
            self.assertRegex(pin["sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
