"""External refresh must keep immutable sources and leave failed plans untouched."""

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "install_skills", Path(__file__).resolve().parents[1] / "scripts/install_skills.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ExternalRefreshTests(unittest.TestCase):
    def manifest(self):
        old = "a" * 40
        return {
            "external_skills": [
                {
                    "name": name,
                    "repository": "example/skills",
                    "commit": old,
                    "url": f"https://raw.githubusercontent.com/example/skills/{old}/skills/{name}/SKILL.md",
                    "sha256": "0" * 64,
                    "license": "MIT",
                    "license_url": f"https://raw.githubusercontent.com/example/skills/{old}/LICENSE",
                    "license_sha256": "0" * 64,
                }
                for name in ("one", "two")
            ]
        }

    def test_refresh_uses_one_revision_for_the_repository_and_hashes_payloads(self):
        original = self.manifest()
        with patch.object(
            installer.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="b" * 40 + "\tHEAD\n"),
        ) as remote:
            with patch.object(
                installer.urllib.request,
                "urlopen",
                side_effect=lambda *a, **k: io.BytesIO(b"upstream"),
            ):
                result = installer.refresh_external_specs(original)
        self.assertEqual(remote.call_count, 1)
        for item in result["external_skills"]:
            self.assertEqual(item["commit"], "b" * 40)
            self.assertIn("/" + "b" * 40 + "/", item["url"])
            self.assertEqual(
                item["sha256"], installer.hashlib.sha256(b"upstream").hexdigest()
            )
        self.assertEqual(original, self.manifest())

    def test_failed_download_keeps_the_original_pins(self):
        original = self.manifest()
        with patch.object(
            installer.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="b" * 40 + "\tHEAD\n"),
        ):
            with patch.object(
                installer.urllib.request, "urlopen", side_effect=OSError("offline")
            ):
                with self.assertRaisesRegex(OSError, "offline"):
                    installer.refresh_external_specs(original)
        self.assertEqual(original, self.manifest())

    def test_invalid_revision_stops_before_downloading(self):
        with patch.object(
            installer.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="invalid\tHEAD\n"),
        ):
            with patch.object(installer.urllib.request, "urlopen") as download:
                with self.assertRaisesRegex(ValueError, "resolve upstream HEAD"):
                    installer.refresh_external_specs(self.manifest())
                download.assert_not_called()

    def test_folded_description_preserves_following_upstream_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "SKILL.md"
            file.write_text(
                '---\nname: example\ndescription: >\n  First line\n  second line\nargument-hint: "[full|off]"\nlicense: MIT\n---\nBody\n'
            )
            fields, errors = installer.parse_frontmatter(file)
        self.assertEqual(errors, [])
        self.assertEqual(fields["description"], "First line second line")
        self.assertEqual(fields["argument-hint"], "[full|off]")
        self.assertEqual(fields["license"], "MIT")

    def test_locked_install_does_not_query_upstream_or_rewrite_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest_file = root / "agent-dependencies.json"
            manifest_file.write_text("original pins")
            with (
                patch.object(installer, "repo_root", return_value=root),
                patch.object(
                    installer, "dependency_manifest", return_value=self.manifest()
                ),
                patch.object(installer, "refresh_external_specs") as refresh,
                patch.object(installer, "prepare_external_skills"),
                patch.object(
                    installer, "validate_source", return_value={"valid": True}
                ),
                patch.object(installer, "install_skills", return_value={}),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(installer.main(["--locked", "--output", "json"]), 0)
                refresh.assert_not_called()
            self.assertEqual(manifest_file.read_text(), "original pins")

    def test_dry_run_refreshes_without_rewriting_pins_or_installing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest_file = root / "agent-dependencies.json"
            manifest_file.write_text("original pins")
            manifest = self.manifest()
            with (
                patch.object(installer, "repo_root", return_value=root),
                patch.object(installer, "dependency_manifest", return_value=manifest),
                patch.object(
                    installer, "refresh_external_specs", return_value=manifest
                ) as refresh,
                patch.object(installer, "prepare_external_skills"),
                patch.object(
                    installer, "validate_source", return_value={"valid": True}
                ),
                patch.object(installer, "install_skills", return_value={}) as install,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(installer.main(["--dry-run", "--output", "json"]), 0)
                refresh.assert_called_once_with(manifest)
                self.assertTrue(install.call_args.args[2])
            self.assertEqual(manifest_file.read_text(), "original pins")


if __name__ == "__main__":
    unittest.main()
