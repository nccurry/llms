from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "install_skills.py"
SPEC = importlib.util.spec_from_file_location("install_skills", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT_PATH}")
install_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_skills)


class InstallSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source"
        self.codex_dir = self.root / "codex" / "skills"
        self.claude_dir = self.root / "claude" / "skills"
        self.pi_dir = self.root / "pi" / "agent" / "skills"
        self.skill_name = "sample-skill"
        self.managed_patch = mock.patch.object(
            install_skills,
            "MANAGED_SKILLS",
            [self.skill_name],
        )
        self.managed_patch.start()
        self.write_skill("version one")

    def tearDown(self) -> None:
        self.managed_patch.stop()
        self.temporary_directory.cleanup()

    def write_skill(self, body: str, skill_name: str | None = None) -> None:
        skill_name = skill_name or self.skill_name
        skill_dir = self.source / skill_name
        agents_dir = skill_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            f"name: {skill_name}\n"
            "description: Audit sample code for a focused test.\n"
            "---\n\n"
            f"# Sample Skill\n\n{body}\n",
            encoding="utf-8",
        )
        (agents_dir / "openai.yaml").write_text(
            "interface:\n"
            '  display_name: "Sample Skill"\n'
            '  short_description: "Audit sample code with clear evidence"\n'
            f'  default_prompt: "Use ${skill_name} to audit this sample."\n',
            encoding="utf-8",
        )

    def install_codex(self) -> dict:
        return install_skills.install_skills(
            self.source,
            {"codex": self.codex_dir},
            dry_run=False,
        )

    def test_validation_accepts_valid_skill_and_rejects_bad_interface(self) -> None:
        result = install_skills.validate_source(self.source)
        self.assertTrue(result["valid"], result["errors"])

        openai_yaml = self.source / self.skill_name / "agents" / "openai.yaml"
        openai_yaml.write_text(
            "interface:\n"
            "  display_name: Sample Skill\n"
            '  short_description: "Too short"\n'
            '  default_prompt: "Use $sample-skill-extra for this audit."\n',
            encoding="utf-8",
        )
        result = install_skills.validate_source(self.source)
        self.assertFalse(result["valid"])
        self.assertTrue(any("quoted" in error for error in result["errors"]))
        self.assertTrue(any("25 to 64" in error for error in result["errors"]))
        self.assertTrue(any("exact skill token" in error for error in result["errors"]))

    def test_validation_rejects_duplicate_keys_and_malformed_yaml(self) -> None:
        skill_md = self.source / self.skill_name / "SKILL.md"
        skill_md.write_text(
            "---\n"
            f"name: {self.skill_name}\n"
            f"name: {self.skill_name}\n"
            "description: Audit sample code for a focused test.\n"
            "---\n",
            encoding="utf-8",
        )
        result = install_skills.validate_source(self.source)
        self.assertFalse(result["valid"])
        self.assertTrue(any("duplicate frontmatter key" in error for error in result["errors"]))

        skill_md.write_text(
            "---\n"
            f"name: {self.skill_name}\n"
            'description: "Bad " quote"\n'
            "---\n",
            encoding="utf-8",
        )
        result = install_skills.validate_source(self.source)
        self.assertFalse(result["valid"])
        self.assertTrue(any("valid quoted string" in error for error in result["errors"]))

        skill_md.write_text(
            "---\n"
            f"name: {self.skill_name}\n"
            "description: Audit: invalid YAML\n"
            "---\n",
            encoding="utf-8",
        )
        result = install_skills.validate_source(self.source)
        self.assertFalse(result["valid"])
        self.assertTrue(any("valid plain string" in error for error in result["errors"]))

        self.write_skill("version one")
        openai_yaml = self.source / self.skill_name / "agents" / "openai.yaml"
        openai_yaml.write_text(
            "interface:\n"
            '  display_name: "Sample Skill" trailing\n'
            '  short_description: "Audit sample code with clear evidence"\n'
            '  short_description: "Duplicate interface description"\n'
            f'  default_prompt: "Use ${self.skill_name} to audit this sample."\n',
            encoding="utf-8",
        )
        result = install_skills.validate_source(self.source)
        self.assertFalse(result["valid"])
        self.assertTrue(any("valid quoted string" in error for error in result["errors"]))
        self.assertTrue(any("duplicate short_description" in error for error in result["errors"]))

    def test_create_then_skip_verifies_installed_digest(self) -> None:
        created = self.install_codex()["targets"]["codex"]["skills"][0]
        self.assertEqual("created", created["action"])
        self.assertTrue(created["verified"])
        self.assertEqual(created["source_digest"], created["installed_digest"])
        self.assertFalse((self.codex_dir.parent / ".skill-staging").exists())

        skipped = self.install_codex()["targets"]["codex"]["skills"][0]
        self.assertEqual("skipped", skipped["action"])
        self.assertTrue(skipped["verified"])

    def test_dry_run_has_no_writes(self) -> None:
        result = install_skills.install_skills(
            self.source,
            {"codex": self.codex_dir},
            dry_run=True,
        )
        skill = result["targets"]["codex"]["skills"][0]
        self.assertEqual("would_create", skill["action"])
        self.assertIsNone(skill["verified"])
        self.assertFalse(self.codex_dir.exists())
        self.assertFalse((self.codex_dir.parent / "skill-backups").exists())
        self.assertFalse((self.codex_dir.parent / ".skill-staging").exists())

    def test_updates_use_external_backups_and_handle_timestamp_collisions(self) -> None:
        self.install_codex()
        with mock.patch.object(install_skills.time, "strftime", return_value="20260805-010203"):
            self.write_skill("version two")
            first = self.install_codex()["targets"]["codex"]["skills"][0]
            self.write_skill("version three")
            second = self.install_codex()["targets"]["codex"]["skills"][0]

        first_backup = Path(first["backup"])
        second_backup = Path(second["backup"])
        expected_root = self.codex_dir.parent / "skill-backups" / "20260805-010203" / "codex"
        self.assertTrue(first_backup.parent.samefile(expected_root))
        self.assertEqual("sample-skill", first_backup.name)
        self.assertEqual("sample-skill-2", second_backup.name)
        self.assertNotEqual(first_backup, second_backup)
        self.assertTrue(first["verified"])
        self.assertTrue(second["verified"])

    def test_legacy_backup_moves_out_of_discovery_root(self) -> None:
        self.install_codex()
        legacy = self.codex_dir / "sample-skill.backup-20260623-153621"
        legacy.mkdir()
        (legacy / "old.txt").write_text("legacy", encoding="utf-8")
        legacy_digest = install_skills.digest_path(legacy)

        result = self.install_codex()
        archived = result["targets"]["codex"]["legacy_backups"][0]
        destination = Path(archived["destination"])
        self.assertFalse(legacy.exists())
        self.assertTrue(destination.exists())
        self.assertEqual(legacy_digest, install_skills.digest_path(destination))
        self.assertTrue(archived["verified"])

    def test_promotion_failure_restores_previous_skill(self) -> None:
        self.install_codex()
        destination = self.codex_dir / self.skill_name
        original_digest = install_skills.digest_path(destination)
        self.write_skill("version two")

        with mock.patch.object(Path, "rename", side_effect=OSError("promotion failed")):
            with self.assertRaisesRegex(OSError, "promotion failed"):
                self.install_codex()

        self.assertEqual(original_digest, install_skills.digest_path(destination))

    def test_staging_failure_leaves_existing_skill_untouched(self) -> None:
        self.install_codex()
        destination = self.codex_dir / self.skill_name
        original_digest = install_skills.digest_path(destination)
        self.write_skill("version two")

        with mock.patch.object(
            install_skills.shutil,
            "copytree",
            side_effect=OSError("staging failed"),
        ):
            with self.assertRaisesRegex(OSError, "staging failed"):
                self.install_codex()

        self.assertTrue(destination.exists())
        self.assertEqual(original_digest, install_skills.digest_path(destination))

    def test_quarantine_failure_still_restores_previous_skill(self) -> None:
        self.install_codex()
        destination = self.codex_dir / self.skill_name
        original_digest = install_skills.digest_path(destination)
        self.write_skill("version two")
        original_rename = Path.rename
        original_move = install_skills.shutil.move

        def promote_then_fail(path: Path, target: Path) -> Path:
            result = original_rename(path, target)
            raise OSError("promotion reported failure")

        def fail_quarantine(source: str, target: str) -> str:
            if Path(source) == destination and Path(target).name.endswith(".failed"):
                raise OSError("quarantine failed")
            return original_move(source, target)

        with mock.patch.object(Path, "rename", autospec=True, side_effect=promote_then_fail):
            with mock.patch.object(install_skills.shutil, "move", side_effect=fail_quarantine):
                with self.assertRaisesRegex(OSError, "promotion reported failure"):
                    self.install_codex()

        self.assertEqual(original_digest, install_skills.digest_path(destination))

    def test_failure_on_second_skill_rolls_back_first_skill(self) -> None:
        second_skill = "second-skill"
        self.write_skill("version one", second_skill)
        with mock.patch.object(
            install_skills,
            "MANAGED_SKILLS",
            [self.skill_name, second_skill],
        ):
            install_skills.install_skills(
                self.source,
                {"codex": self.codex_dir},
                dry_run=False,
            )
            original_digests = {
                name: install_skills.digest_path(self.codex_dir / name)
                for name in [self.skill_name, second_skill]
            }
            self.write_skill("version two", self.skill_name)
            self.write_skill("version two", second_skill)
            original_rename = Path.rename

            def fail_second_promotion(path: Path, target: Path) -> Path:
                if path.name == second_skill:
                    raise OSError("second promotion failed")
                return original_rename(path, target)

            with mock.patch.object(
                Path,
                "rename",
                autospec=True,
                side_effect=fail_second_promotion,
            ):
                with self.assertRaisesRegex(OSError, "second promotion failed"):
                    install_skills.install_skills(
                        self.source,
                        {"codex": self.codex_dir},
                        dry_run=False,
                    )

        for name, original_digest in original_digests.items():
            self.assertEqual(original_digest, install_skills.digest_path(self.codex_dir / name))

    def test_codex_and_claude_backups_are_isolated(self) -> None:
        targets = {"codex": self.codex_dir, "claude": self.claude_dir}
        install_skills.install_skills(self.source, targets, dry_run=False)
        self.write_skill("version two")

        with mock.patch.object(install_skills.time, "strftime", return_value="20260805-010203"):
            result = install_skills.install_skills(self.source, targets, dry_run=False)

        codex_backup = Path(result["targets"]["codex"]["skills"][0]["backup"])
        claude_backup = Path(result["targets"]["claude"]["skills"][0]["backup"])
        self.assertIn("codex", codex_backup.parts)
        self.assertIn("claude", claude_backup.parts)
        self.assertNotEqual(codex_backup, claude_backup)

    def test_pi_target_installs_and_uses_its_own_backup_directory(self) -> None:
        targets = {"pi": self.pi_dir}
        first = install_skills.install_skills(self.source, targets, dry_run=False)
        self.assertEqual("created", first["targets"]["pi"]["skills"][0]["action"])

        self.write_skill("version two")
        updated = install_skills.install_skills(self.source, targets, dry_run=False)
        backup = Path(updated["targets"]["pi"]["skills"][0]["backup"])
        self.assertIn("pi", backup.parts)
        self.assertTrue(updated["targets"]["pi"]["skills"][0]["verified"])

    def test_pi_target_resolution_honors_flag_and_environment(self) -> None:
        from_flag = self.root / "custom-pi-skills"
        args = install_skills.parse_args(["--target", "pi", "--pi-dir", str(from_flag)])
        self.assertEqual(from_flag, install_skills.resolve_targets(args)["pi"])

        from_environment = self.root / "environment-pi-skills"
        with mock.patch.dict(
            install_skills.os.environ,
            {"PI_SKILLS_DIR": str(from_environment)},
            clear=False,
        ):
            args = install_skills.parse_args(["--target", "pi"])
            self.assertEqual(from_environment, install_skills.resolve_targets(args)["pi"])

    def test_json_output_contains_verification_fields(self) -> None:
        result = self.install_codex()
        output = io.StringIO()
        with redirect_stdout(output):
            install_skills.emit(result, "json")

        parsed = json.loads(output.getvalue())
        skill = parsed["targets"]["codex"]["skills"][0]
        self.assertIn("source_digest", skill)
        self.assertIn("installed_digest", skill)
        self.assertTrue(skill["verified"])


if __name__ == "__main__":
    unittest.main()
