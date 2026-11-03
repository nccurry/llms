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
