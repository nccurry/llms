"""Setup tolerates Claude managed-settings failures and preserves other errors."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "manage_agent_tools", ROOT / "scripts/manage_agent_tools.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class AgentSetupTests(unittest.TestCase):
    def configure(self, home, error, failing_tool=None):
        def run(command, **kwargs):
            if (
                "claude-code" in command
                or command[-2:] == ["--target", "claude"]
            ) and (failing_tool is None or Path(command[0]).name == failing_tool):
                raise RuntimeError(error)
            return "installed"

        manifest = {
            "tools": {
                "serena": {"version": "1"},
                "cq": {"version": "1"},
                "gitnexus": {"version": "1", "integration_enabled": False},
            }
        }
        servers = {
            "serena": {"command": "/managed/serena", "args": []},
            "cq": {"command": "/managed/cq", "args": ["serve"]},
        }
        with (
            patch.object(Path, "home", return_value=home),
            patch.object(setup, "TOOLS", home / "tools"),
            patch.object(setup, "manifest", return_value=manifest),
            patch.object(setup, "installed_version", return_value="1"),
            patch.object(
                setup, "selected_hosts", return_value=("claude", "pi", "opencode")
            ),
            patch.object(setup, "serena_configuration", return_value={}),
            patch.object(setup, "configure_claude_environment"),
            patch.object(setup.shutil, "which", return_value="/managed/claude"),
            patch.object(
                setup, "tool_command", side_effect=lambda name: [f"/managed/{name}"]
            ),
            patch.object(setup, "host_servers", return_value=servers),
            patch.object(setup, "run", side_effect=run),
        ):
            return setup.configure("all")

    def test_claude_managed_settings_failure_allows_manual_config_and_other_hosts(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.configure(
                home, "Your organization requires remote managed settings to load"
            )
            self.assertEqual(
                [host["host"] for host in result["hosts"]], ["claude", "pi", "opencode"]
            )
            self.assertEqual(len(result["hosts"][0]["limitations"]), 2)
            config = json.loads((home / ".claude.json").read_text())
            self.assertEqual(
                config["mcpServers"]["serena"]["command"], "/managed/serena"
            )
            self.assertEqual(config["mcpServers"]["cq"]["command"], "/managed/cq")
            self.assertTrue((home / ".config/opencode/opencode.json").is_file())

    def test_unexpected_setup_failures_still_fail(self):
        for tool in ("serena", "cq"):
            with (
                self.subTest(tool=tool),
                tempfile.TemporaryDirectory() as temp,
                self.assertRaisesRegex(RuntimeError, "unexpected failure"),
            ):
                self.configure(Path(temp), "unexpected failure", failing_tool=tool)


class ConfigWriteTests(unittest.TestCase):
    """Writes to agent config keep the owner's other settings and files intact."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        tools = patch.object(setup, "TOOLS", self.root / "tools")
        tools.start()
        self.addCleanup(tools.stop)

    def test_update_through_symlink_keeps_the_link(self):
        target = self.root / "dotfiles/settings.json"
        target.parent.mkdir()
        target.write_text("{}\n")
        link = self.root / "settings.json"
        link.symlink_to(target)

        self.assertEqual(setup.update_file(link, '{"a": 1}\n'), "updated")

        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_text(), '{"a": 1}\n')

    def test_update_drops_group_and_world_write(self):
        path = self.root / "hooks.json"
        path.write_text("{}\n")
        path.chmod(0o664)
        setup.update_file(path, "{}\n")
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        path.chmod(0o666)
        setup.update_file(path, '{"a": 1}\n')
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_backups_keep_only_recent_runs(self):
        path = self.root / "config.toml"
        path.write_text("x = 1\n")
        with patch.object(setup, "BACKUP_RUNS_KEPT", 2):
            for _ in range(4):
                setup.backup_configuration(path)
        self.assertEqual(len(list((self.root / "tools/config-backups").iterdir())), 2)

    def test_stable_paths_drop_relative_missing_and_temporary_entries(self):
        kept = self.root / "bin"
        kept.mkdir()
        codex_tmp = self.root / ".codex/tmp/arg0"
        codex_tmp.mkdir(parents=True)
        system_tmp = self.root / "systmp/uv-run"
        system_tmp.mkdir(parents=True)
        with (
            patch.object(Path, "home", return_value=self.root),
            patch.object(
                setup.tempfile, "gettempdir", return_value=str(self.root / "systmp")
            ),
        ):
            self.assertEqual(
                setup.stable_paths(
                    [
                        str(kept),
                        "bin",
                        str(self.root / "gone"),
                        str(codex_tmp),
                        str(system_tmp),
                        str(kept),
                    ]
                ),
                [str(kept)],
            )

    def test_restore_servers_keeps_edits_made_during_setup(self):
        path = self.root / ".claude.json"
        path.write_text(json.dumps({"mcpServers": {"mine": {"command": "a"}}}))
        snapshot = setup.snapshot_configs({path})
        # An installer replaces the servers while the host saves other state.
        path.write_text(
            json.dumps({"mcpServers": {"gitnexus": {"command": "npx"}}, "projects": {"p": 1}})
        )

        setup.restore_servers(snapshot)

        self.assertEqual(
            json.loads(path.read_text()),
            {"mcpServers": {"mine": {"command": "a"}}, "projects": {"p": 1}},
        )

    def test_restore_servers_on_codex_toml_keeps_comments(self):
        path = self.root / "config.toml"
        path.write_text('# mine\nmodel = "x"\n\n[mcp_servers.mine]\ncommand = "a"\n')
        snapshot = setup.snapshot_configs({path})
        path.write_text(
            '# mine\nmodel = "y"\n\n[mcp_servers.cq]\ncommand = "cq"\n'
        )

        setup.restore_servers(snapshot)

        text = path.read_text()
        self.assertIn("# mine", text)
        self.assertIn('model = "y"', text)
        self.assertIn("[mcp_servers.mine]", text)
        self.assertNotIn("cq", text)

    def test_restore_servers_removes_a_server_only_file_it_created(self):
        created = self.root / "opencode.json"
        kept = self.root / "config.json"
        snapshot = setup.snapshot_configs({created, kept})
        created.write_text(json.dumps({"$schema": "s", "mcp": {"cq": {}}}))
        kept.write_text(json.dumps({"theme": "dark", "mcp": {"cq": {}}}))

        setup.restore_servers(snapshot)

        self.assertFalse(created.exists())
        self.assertEqual(json.loads(kept.read_text()), {"theme": "dark"})

    def test_claude_environment_path_is_rebuilt_not_extended(self):
        home = self.root / "home"
        (home / ".claude").mkdir(parents=True)
        settings = home / ".claude/settings.json"
        settings.write_text(json.dumps({"env": {"PATH": "/stale/dir", "KEEP": "1"}}))
        with (
            patch.object(Path, "home", return_value=home),
            patch.object(setup, "tool_env", return_value={"PATH": "/usr/bin"}),
        ):
            setup.configure_claude_environment()
        self.assertEqual(
            json.loads(settings.read_text())["env"],
            {"PATH": "/usr/bin", "KEEP": "1", "CQ_ADDR": ""},
        )
