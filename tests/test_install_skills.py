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
assert spec is not None and spec.loader is not None
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
        with (
            patch.object(
                installer.subprocess,
                "run",
                return_value=SimpleNamespace(stdout="b" * 40 + "\tHEAD\n"),
            ) as remote,
            patch.object(
                installer.urllib.request,
                "urlopen",
                side_effect=lambda *a, **k: io.BytesIO(b"upstream"),
            ),
        ):
            result = installer.refresh_external_specs(original)
        self.assertEqual(remote.call_count, 1)
        for item in result["external_skills"]:
            self.assertEqual(item["commit"], "b" * 40)
            self.assertIn("/" + "b" * 40 + "/", item["url"])
            self.assertEqual(item["sha256"], installer.hashlib.sha256(b"upstream").hexdigest())
        self.assertEqual(original, self.manifest())

    def test_failed_download_keeps_the_original_pins(self):
        original = self.manifest()
        with (
            patch.object(
                installer.subprocess,
                "run",
                return_value=SimpleNamespace(stdout="b" * 40 + "\tHEAD\n"),
            ),
            patch.object(installer.urllib.request, "urlopen", side_effect=OSError("offline")),
            self.assertRaisesRegex(OSError, "offline"),
        ):
            installer.refresh_external_specs(original)
        self.assertEqual(original, self.manifest())

    def test_invalid_revision_stops_before_downloading(self):
        with (
            patch.object(
                installer.subprocess,
                "run",
                return_value=SimpleNamespace(stdout="invalid\tHEAD\n"),
            ),
            patch.object(installer.urllib.request, "urlopen") as download,
        ):
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
                patch.object(installer, "dependency_manifest", return_value=self.manifest()),
                patch.object(installer, "refresh_external_specs") as refresh,
                patch.object(installer, "prepare_external_skills"),
                patch.object(installer, "validate_source", return_value={"valid": True}),
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
                patch.object(installer, "refresh_external_specs", return_value=manifest) as refresh,
                patch.object(installer, "prepare_external_skills"),
                patch.object(installer, "validate_source", return_value={"valid": True}),
                patch.object(installer, "install_skills", return_value={}) as install,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(installer.main(["--dry-run", "--output", "json"]), 0)
                refresh.assert_called_once_with(manifest)
                self.assertTrue(install.call_args.args[2])
            self.assertEqual(manifest_file.read_text(), "original pins")


class RetiredSkillTests(unittest.TestCase):
    """Skills that leave the repo move to backups; other installers' skills stay."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source = root / "source"
        (self.source / "kept").mkdir(parents=True)
        (self.source / "kept" / "SKILL.md").write_text("kept\n")
        self.target = root / "agent" / "skills"
        self.target.mkdir(parents=True)
        for name in ("dropped", "start-this-up", "someone-elses"):
            (self.target / name).mkdir()
            (self.target / name / "SKILL.md").write_text(f"{name}\n")

    def tearDown(self):
        self.temp.cleanup()

    def install(self, dry_run=False):
        with (
            patch.object(installer, "MANAGED_SKILLS", ["kept"]),
            patch.object(installer, "validate_source", return_value={"valid": True}),
        ):
            return installer.install_skills(
                self.source,
                {"agent": self.target},
                dry_run,
                manifest={},
                external_source=self.source,
            )

    def record(self, *names):
        installer.install_record(self.target).write_text(
            installer.json.dumps({"skills": list(names)})
        )

    def installed(self):
        return sorted(path.name for path in self.target.iterdir())

    def test_recorded_and_known_retired_skills_move_to_backups(self):
        self.record("kept", "dropped")
        result = self.install()

        self.assertEqual(self.installed(), ["kept", "someone-elses"])
        retired = result["targets"]["agent"]["retired"]
        self.assertEqual([r["skill"] for r in retired], ["dropped", "start-this-up"])
        for item in retired:
            self.assertEqual(item["action"], "retired")
            moved = Path(item["destination"])
            self.assertEqual(moved.parent.parent.parent, installer.backup_root(self.target))
            self.assertEqual((moved / "SKILL.md").read_text(), f"{item['skill']}\n")
        self.assertEqual(installer.recorded_skills(self.target), ["kept"])

    def test_skills_never_recorded_stay_without_a_record(self):
        self.install()
        self.assertEqual(self.installed(), ["dropped", "kept", "someone-elses"])

    def test_dry_run_moves_nothing_and_writes_no_record(self):
        self.record("kept", "dropped")
        result = self.install(dry_run=True)

        self.assertEqual(self.installed(), ["dropped", "someone-elses", "start-this-up"])
        actions = {r["skill"]: r["action"] for r in result["targets"]["agent"]["retired"]}
        self.assertEqual(actions, {"dropped": "would_retire", "start-this-up": "would_retire"})
        self.assertEqual(installer.recorded_skills(self.target), ["kept", "dropped"])

    def test_failed_install_retires_nothing(self):
        self.record("kept", "dropped")
        with (
            patch.object(installer, "install_skill", side_effect=RuntimeError("boom")),
            self.assertRaisesRegex(RuntimeError, "boom"),
        ):
            self.install()

        self.assertEqual(self.installed(), ["dropped", "someone-elses", "start-this-up"])
        self.assertEqual(installer.recorded_skills(self.target), ["kept", "dropped"])


if __name__ == "__main__":
    unittest.main()
