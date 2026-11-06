"""A host defined only by an adapter works in configure, preview and doctor.

This registers a made-up host with its own config file layout. Setup code is
not changed for it: configure, preview, host_problems and
require_standard_profiles take everything from the adapter. The test imports
the setup script (the black-box end-to-end test cannot add a host) and patches
only what reaches outside the temporary home: tool lookup, the upstream
installers and the server list.
"""

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
assert spec is not None and spec.loader is not None
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

SERENA_ARGS = ["start-mcp-server", "--context", "", "--open-web-dashboard", "false"]


def fake_config() -> Path:
    return Path.home() / ".fakehost/settings.json"


def read_fake_servers(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")).get("fakeServers", {})


def write_fake_servers(path: Path, servers: dict, *, dry_run: bool = False) -> str:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for name, server in servers.items():
        data.setdefault("fakeServers", {})[name] = {
            "command": server["command"],
            "args": server["args"],
            "vars": server["env"],
        }
    return setup.update_file(path, json.dumps(data, indent=2) + "\n", dry_run=dry_run)


FAKE_HOST = setup.HostAdapter(
    name="fakehost",
    config_path=fake_config,
    write_config=write_fake_servers,
    check_config=setup.server_problems,
    serena_client="fake-client",
    gitnexus_client="fake-client",
    serena_context="fake-context",
    servers_key="fakeServers",
    env_key="vars",
    read_servers=read_fake_servers,
)


def managed_servers() -> dict:
    return {
        "serena": {
            "command": "/managed/serena",
            "args": list(SERENA_ARGS),
            "env": {"PATH": "/managed/bin", "SERENA_HOME": "/serena"},
            "startup_timeout_sec": 60,
        },
        "cq": {"command": "/managed/cq", "args": ["mcp"], "env": {"CQ_ADDR": ""}},
    }


class FakeHostAdapterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        (self.home / ".fakehost").mkdir()
        self.config = self.home / ".fakehost/settings.json"
        self.config.write_text(json.dumps({"theme": "dark"}))
        self.commands: list[list[str]] = []
        manifest = {
            "tools": {
                "serena": {"version": "1"},
                "cq": {"version": "1"},
                "gitnexus": {"version": "1", "integration_enabled": False},
            }
        }

        def run(command, **kwargs):
            self.commands.append(command)
            return "installed"

        patchers = [
            patch.dict(setup.ADAPTERS, {"fakehost": FAKE_HOST}),
            patch.object(Path, "home", return_value=self.home),
            patch.object(setup, "TOOLS", self.home / "tools"),
            patch.object(setup, "manifest", return_value=manifest),
            patch.object(setup, "installed_version", return_value="1"),
            patch.object(setup, "serena_configuration", return_value={}),
            patch.object(setup, "servers", side_effect=managed_servers),
            patch.object(setup, "required_tool_paths", return_value=set()),
            patch.object(setup, "serena_home", return_value=Path("/serena")),
            patch.object(setup.shutil, "which", return_value=None),
            patch.object(setup, "tool_command", side_effect=lambda name: [f"/managed/{name}"]),
            patch.object(setup, "run", side_effect=run),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_host_is_listed_and_takes_its_settings_from_the_adapter(self):
        self.assertIn("fakehost", setup.selected_hosts("all"))
        servers = setup.host_servers("fakehost")
        self.assertEqual(servers["serena"]["args"][2], "fake-context")
        self.assertNotIn("startup_timeout_sec", servers["serena"])

    def test_preview_plans_the_host_and_writes_nothing(self):
        before = self.config.read_text()

        result = setup.preview("fakehost")

        [host] = result["hosts"]
        self.assertEqual(host["host"], "fakehost")
        self.assertEqual(host["config"], str(self.config))
        self.assertEqual(host["action"], "would update")
        self.assertEqual(host["managed_servers"], ["serena", "cq"])
        self.assertIsNone(host["environment_action"])
        self.assertEqual(host["serena_hooks"], "not applicable")
        self.assertEqual(self.config.read_text(), before)

    def test_configure_backs_up_runs_cq_and_writes_the_servers(self):
        result = setup.configure("fakehost")

        [host] = result["hosts"]
        self.assertEqual(host["host"], "fakehost")
        self.assertEqual(host["action"], "updated")
        self.assertEqual(host["limitations"], [])
        written = json.loads(self.config.read_text())
        self.assertEqual(written["theme"], "dark")
        self.assertEqual(
            written["fakeServers"]["serena"],
            {
                "command": "/managed/serena",
                "args": ["start-mcp-server", "--context", "fake-context", *SERENA_ARGS[3:]],
                "vars": {"PATH": "/managed/bin", "SERENA_HOME": "/serena"},
            },
        )
        # No serena setup or hooks for this host; cq installs for it by name.
        self.assertEqual(self.commands, [["/managed/cq", "install", "--target", "fakehost"]])
        backups = sorted((self.home / "tools/config-backups").glob("*/settings.json"))
        self.assertEqual(json.loads(backups[0].read_text()), {"theme": "dark"})

    def test_host_problems_follows_the_adapter_and_clears_after_configure(self):
        self.assertIn(f"serena server missing from {self.config}", setup.host_problems("fakehost"))

        setup.configure("fakehost")
        self.assertEqual(setup.host_problems("fakehost"), [])

        data = json.loads(self.config.read_text())
        data["fakeServers"]["serena"]["command"] = "/old/serena"
        data["fakeServers"]["cq"]["vars"]["CQ_ADDR"] = "https://remote"
        self.config.write_text(json.dumps(data))
        self.assertEqual(
            setup.host_problems("fakehost"),
            [
                f"serena server in {self.config} runs a different command",
                f"cq server in {self.config} has different environment values",
            ],
        )

    def test_host_problems_reports_a_missing_config_file(self):
        self.config.unlink()
        self.assertEqual(setup.host_problems("fakehost"), [f"{self.config} not found"])

    def test_existing_server_and_serena_home_checks_read_the_adapter_layout(self):
        setup.configure("fakehost")
        self.assertTrue(setup.existing_server("fakehost", "serena"))
        self.assertFalse(setup.existing_server("fakehost", "other"))
        setup.require_standard_profiles("fakehost")

        data = json.loads(self.config.read_text())
        data["fakeServers"]["serena"]["vars"]["SERENA_HOME"] = "/somewhere/else"
        self.config.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError, "fakehost has a different Serena home"):
            setup.require_standard_profiles("fakehost")


if __name__ == "__main__":
    unittest.main()
