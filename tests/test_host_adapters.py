"""A host defined only by an adapter works in configure, preview and doctor.

Two made-up hosts are registered. Setup code is not changed for either:
configure, preview, host_problems, require_standard_profiles and existing_server
take everything from the adapter.

- `fakehost` is a bare host: its own config layout and writer, no hooks, no
  upstream installers beyond cq.
- `richhost` sets every other part of an adapter: a hooks file in a folder that
  its name does not give, Serena hooks in exec form, `serena setup` and
  GitNexus setup with their own client names, an environment step, a second
  server file, and a settings key and environment key of its own. It reuses the
  JSON server reader and writer, which read those keys from the adapter.

The test imports the setup script (the black-box end-to-end test cannot add a
host) and patches only what reaches outside the temporary home: tool lookup,
the upstream installers and the server list.
"""

import importlib.util
import json
import os
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

# The setup script always writes an absolute Serena home; "/serena" has no drive on Windows.
SERENA_HOME = str(Path("/serena").resolve())
SERENA_ARGS = ["start-mcp-server", "--context", "", "--open-web-dashboard", "false"]


def managed_servers() -> dict:
    return {
        "serena": {
            "command": "/managed/serena",
            "args": list(SERENA_ARGS),
            "env": {"PATH": "/managed/bin", "SERENA_HOME": SERENA_HOME},
            "startup_timeout_sec": 60,
        },
        "gitnexus": {
            "command": "/managed/node",
            "args": ["/managed/gitnexus.js", "mcp"],
            "env": {"PATH": "/managed/bin"},
        },
        "cq": {"command": "/managed/cq", "args": ["mcp"], "env": {"CQ_ADDR": ""}},
    }


# ---- fakehost: its own file layout and writer


def fake_config() -> Path:
    return Path.home() / ".fakehost/settings.json"


def read_fake_servers(adapter, path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")).get(adapter.servers_key, {})


def write_fake_servers(adapter, servers: dict, /, *, dry_run: bool = False) -> str:
    path = adapter.config_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for name, server in servers.items():
        data.setdefault(adapter.servers_key, {})[name] = {
            "command": server["command"],
            "args": server["args"],
            adapter.env_key: server["env"],
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


# ---- richhost: every optional part of an adapter, in places its name does not give


def rich_config() -> Path:
    return Path.home() / ".rich/conf/mcp.json"


def rich_other_server_files() -> set[Path]:
    return {Path.home() / ".rich/conf/alt.json"}


def rich_environment_step(*, dry_run: bool = False) -> str:
    if dry_run:
        return "would write"
    (Path.home() / ".rich/env-step.txt").write_text("ran")
    return "written"


RICH_HOST = setup.HostAdapter(
    name="richhost",
    config_path=rich_config,
    write_config=setup.merge_mcp_servers_json,
    check_config=setup.server_problems,
    serena_client="rich-code",
    gitnexus_client="rich-git",
    serena_context="rich-context",
    extra_server_files=rich_other_server_files,
    servers_key="richServers",
    env_key="vars",
    read_servers=setup.read_claude_servers,
    hooks_file=".rich/conf/hooks.json",
    hook_exec_form=True,
    serena_hooks=(("Start", "", "activate"), ("Stop", "Bash", "cleanup")),
    runs_serena_setup=True,
    environment_step=rich_environment_step,
)


class HostTestCase(unittest.TestCase):
    adapter = FAKE_HOST  # each test class sets its own
    gitnexus_enabled = False

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.commands: list[list[str]] = []
        manifest = {
            "tools": {
                "serena": {"version": "1"},
                "cq": {"version": "1"},
                "gitnexus": {"version": "1", "integration_enabled": self.gitnexus_enabled},
            }
        }
        patchers = [
            patch.dict(setup.ADAPTERS, {self.adapter.name: self.adapter}),
            patch.object(Path, "home", return_value=self.home),
            patch.object(setup, "TOOLS", self.home / "tools"),
            patch.object(setup, "manifest", return_value=manifest),
            patch.object(setup, "installed_version", return_value="1"),
            patch.object(setup, "serena_configuration", return_value={}),
            patch.object(setup, "servers", side_effect=managed_servers),
            patch.object(setup, "required_tool_paths", return_value=set()),
            patch.object(setup, "serena_home", return_value=Path(SERENA_HOME)),
            patch.object(setup, "node_command", return_value="/managed/node"),
            patch.object(setup.shutil, "which", return_value=None),
            patch.object(
                setup,
                "tool_command",
                side_effect=lambda name: [f"/managed/{name}", f"/managed/{name}.js"],
            ),
            patch.object(setup, "run", side_effect=self.run_upstream),
        ]
        if os.name == "nt":
            # Windows tightens file access through PowerShell, which would show up in the
            # recorded commands; test_windows_branches checks that command.
            patchers.append(patch.object(setup, "private_permissions"))
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_upstream(self, command, **kwargs):
        self.commands.append(command)
        return "installed"


class FakeHostTests(HostTestCase):
    adapter = FAKE_HOST

    def setUp(self):
        super().setUp()
        (self.home / ".fakehost").mkdir()
        self.config = self.home / ".fakehost/settings.json"
        self.config.write_text(json.dumps({"theme": "dark"}))

    def test_the_host_is_listed_and_takes_its_settings_from_the_adapter(self):
        self.assertIn("fakehost", setup.selected_hosts("all"))
        servers = setup.host_servers(FAKE_HOST)
        self.assertEqual(servers["serena"]["args"][2], "fake-context")
        self.assertNotIn("startup_timeout_sec", servers["serena"])

    def test_preview_plans_the_host_and_writes_nothing(self):
        before = self.config.read_text()

        result = setup.preview("fakehost")

        [host] = result["hosts"]
        self.assertEqual(host["host"], "fakehost")
        self.assertEqual(host["config"], str(self.config))
        self.assertEqual(host["action"], "would update")
        self.assertEqual(host["managed_servers"], ["serena", "gitnexus", "cq"])
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
                "vars": {"PATH": "/managed/bin", "SERENA_HOME": SERENA_HOME},
            },
        )
        # No serena setup, GitNexus or hooks for this host; cq installs for it by name.
        self.assertEqual(
            self.commands, [["/managed/cq", "/managed/cq.js", "install", "--target", "fakehost"]]
        )
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
        self.assertTrue(setup.existing_server(FAKE_HOST, "serena"))
        self.assertFalse(setup.existing_server(FAKE_HOST, "other"))
        setup.require_standard_profiles("fakehost")

        data = json.loads(self.config.read_text())
        data["fakeServers"]["serena"]["vars"]["SERENA_HOME"] = "/somewhere/else"
        self.config.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError, "fakehost has a different Serena home"):
            setup.require_standard_profiles("fakehost")


class RichHostTests(HostTestCase):
    adapter = RICH_HOST
    gitnexus_enabled = True

    def setUp(self):
        super().setUp()
        self.conf = self.home / ".rich/conf"
        self.conf.mkdir(parents=True)
        self.config = self.conf / "mcp.json"
        self.alt = self.conf / "alt.json"
        self.hooks = self.conf / "hooks.json"
        self.config.write_text(
            json.dumps({"theme": "dark", "richServers": {"mine": {"command": "a"}}})
        )
        self.alt.write_text(json.dumps({"keep": 1, "richServers": {"alt": {"command": "b"}}}))

    def run_upstream(self, command, **kwargs):
        super().run_upstream(command, **kwargs)
        if command[2:] == ["setup", "-c", "rich-git"]:
            self.fake_gitnexus_setup()
        return "installed"

    def fake_gitnexus_setup(self):
        """Do what the real installer does: replace the servers, add a hook for its script."""
        for path in (self.config, self.alt):
            data = json.loads(path.read_text())
            data["richServers"] = {"gitnexus": {"command": "npx"}}
            path.write_text(json.dumps(data))
        script = self.conf / "hooks/gitnexus/gitnexus-hook.cjs"
        script.parent.mkdir(parents=True)
        script.write_text("// hook")
        hook = {"type": "command", "command": f"node {script.as_posix()}"}
        self.hooks.write_text(
            json.dumps({"hooks": {"PostToolUse": [{"matcher": "Bash", "hooks": [hook]}]}})
        )

    def test_configure_runs_each_step_with_the_adapter_values(self):
        [host] = setup.configure("richhost")["hosts"]

        self.assertEqual(host["host"], "richhost")
        self.assertEqual(host["action"], "updated")
        self.assertEqual(
            self.commands,
            [
                ["/managed/serena", "/managed/serena.js", "setup", "rich-code"],
                ["/managed/gitnexus", "/managed/gitnexus.js", "setup", "-c", "rich-git"],
                ["/managed/cq", "/managed/cq.js", "install", "--target", "richhost"],
            ],
        )
        self.assertEqual((self.home / ".rich/env-step.txt").read_text(), "ran")

    def test_hooks_go_to_the_adapters_file_and_use_its_form(self):
        setup.configure("richhost")

        hooks = json.loads(self.hooks.read_text())["hooks"]
        self.assertEqual(
            hooks["Start"],
            [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "timeout": 5,
                            "command": str(self.home / "tools/bin/serena-hooks")
                            + (".exe" if os.name == "nt" else ""),
                            "args": ["activate", "--client=rich-code"],
                        }
                    ]
                }
            ],
        )
        self.assertEqual(hooks["Stop"][0]["matcher"], "Bash")
        # GitNexus's own hook is rewritten in exec form, in the same file.
        [gitnexus_hook] = hooks["PostToolUse"][0]["hooks"]
        self.assertEqual(gitnexus_hook["command"], "/managed/node")
        self.assertEqual(
            gitnexus_hook["args"][0], (setup.ROOT / "scripts/run_gitnexus_hook.mjs").as_posix()
        )
        for guess in (".richhost", ".rich/hooks.json", ".rich/settings.json"):
            self.assertFalse((self.home / guess).exists(), guess)

    def test_upstream_server_edits_are_undone_in_every_server_file(self):
        setup.configure("richhost")

        written = json.loads(self.config.read_text())
        self.assertEqual(written["theme"], "dark")
        self.assertIn("mine", written["richServers"])
        self.assertEqual(written["richServers"]["gitnexus"]["command"], "/managed/node")
        self.assertEqual(
            json.loads(self.alt.read_text()), {"keep": 1, "richServers": {"alt": {"command": "b"}}}
        )

    def test_every_file_it_may_change_is_backed_up_first(self):
        setup.configure("richhost")

        backed_up = {path.name for path in (self.home / "tools/config-backups").glob("*/*")}
        self.assertEqual(backed_up, {"mcp.json", "alt.json", "hooks.json"})

    def test_preview_reports_the_environment_step_and_hooks_without_writing(self):
        before = self.config.read_text()

        [host] = setup.preview("richhost")["hosts"]

        self.assertEqual(host["environment_action"], "would write")
        self.assertEqual(host["serena_hooks"], "would create")
        self.assertEqual(self.config.read_text(), before)
        self.assertFalse((self.home / ".rich/env-step.txt").exists())
        self.assertFalse(self.hooks.exists())

    def test_host_problems_is_empty_after_configure(self):
        setup.configure("richhost")
        self.assertEqual(setup.host_problems("richhost"), [])

        self.hooks.unlink()
        self.assertEqual(
            setup.host_problems("richhost"),
            [
                f"Serena hooks in {self.hooks} are missing or stale",
                f"GitNexus hooks in {self.hooks} are missing or stale",
            ],
        )


class UnknownSkillHostTests(HostTestCase):
    """The skills check covers only hosts scripts/install_skills.py knows."""

    adapter = FAKE_HOST

    def test_skill_health_skips_a_host_the_installer_does_not_know(self):
        result = setup.skill_health("fakehost")

        self.assertEqual(result["hosts"], [])
        self.assertEqual(
            result["skipped"],
            ["fakehost: skills not checked; scripts/install_skills.py does not know this host"],
        )


if __name__ == "__main__":
    unittest.main()
