"""Run `manage_agent_tools.py --command configure` twice in a fake home and check the result.

The setup script is a black box here. The test copies it into a temporary
repository, seeds a temporary home, fixes the environment, and runs the
script's command line. Nothing inside the script is patched or imported, so
the script's functions can be renamed or split without touching this test.

What is faked: the upstream installers and version probes (serena, cq,
gitnexus, ast-grep, Serena's own Python) and the client programs on PATH. The
stand-ins are in tests/fixtures/configure/fake_upstream_tools.py.

What is real: the setup script, and Node with the pinned `jsonc-parser`
package, which the script uses to edit opencode.jsonc without losing comments.
They come from the pinned install in this checkout (`.tools/agent-tools`). The
test is skipped when they are missing, unless LLMS_REQUIRE_PINNED_TOOLS is set,
which makes a missing install a failure.

Golden copies of the written files are in tests/fixtures/configure/golden.
Machine paths are replaced by placeholders before comparing: {HOME}, {REPO},
{TOOLS}, {NODE_DIR}, {UV_DIR}, {TASK_DIR} and {CLIENT_DIR}. To write the golden
files again after an approved change in what setup writes, run the test with
LLMS_WRITE_GOLDEN=1 and review the diff.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests/fixtures/configure"
SEED = FIXTURES / "seed"
GOLDEN = FIXTURES / "golden"
FAKE_TOOLS = FIXTURES / "fake_upstream_tools.py"
PINNED = REPO_ROOT / ".tools/agent-tools"

# FIX-006: the files the golden copies cover, relative to the home folder.
GOLDEN_FILES = (
    ".claude.json",
    ".claude/settings.json",
    ".codex/config.toml",
    ".codex/hooks.json",
    ".codex/AGENTS.md",
    ".config/opencode/opencode.jsonc",
    ".config/opencode/AGENTS.md",
    ".pi/agent/AGENTS.md",
    ".pi/agent/settings.json",
    ".serena/serena_config.yml",
)
# Seeded files are mode 0600 unless listed here (git does not keep these modes).
SEED_MODES = {
    ".codex/hooks.json": 0o664,
    ".config/opencode/opencode.jsonc": 0o644,
    ".pi/agent/AGENTS.md": 0o644,
    ".pi/agent/settings.json": 0o644,
}
ENCODED_COMMAND = re.compile(r"-EncodedCommand ([A-Za-z0-9+/=]+)")
HOSTS = ("codex", "claude", "pi", "opencode")


def pinned_node_and_jsonc_parser() -> tuple[Path, Path] | None:
    """Return the pinned Node and the jsonc-parser folder, or None when not installed."""
    receipt = PINNED / "runtime.json"
    recorded = (
        json.loads(receipt.read_text(encoding="utf-8")).get("node") if receipt.is_file() else None
    )
    node = recorded if recorded and Path(recorded).is_file() else shutil.which("node")
    parser = PINNED / "npm/node_modules/jsonc-parser"
    if node and (parser / "package.json").is_file():
        return Path(node), parser
    return None


def write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def fake_command(tool: str) -> str:
    """A shell wrapper that hands its own path and arguments to the stand-in for `tool`."""
    return (
        "#!/bin/sh\n"
        f'exec {shlex.quote(sys.executable)} {shlex.quote(str(FAKE_TOOLS))} {tool} "$0" "$@"\n'
    )


class Sandbox:
    """A temporary home, repository copy and fake tools folder with a fixed environment."""

    def __init__(self, root: Path, node: Path, jsonc_parser: Path) -> None:
        self.root = root.resolve()
        self.home = self.root / "home"
        self.repo = self.root / "repo"
        self.tools = self.repo / ".tools/agent-tools"
        self.node_dir = self.root / "runtime/node"
        self.uv_dir = self.root / "runtime/uv"
        self.task_dir = self.root / "runtime/task"
        self.client_dir = self.root / "clients"
        self.temp_dir = self.root / "tmp"
        self.script = self.repo / "scripts/manage_agent_tools.py"
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.client_dir),
            "LLMS_ORIGINAL_PATH": str(self.client_dir),
            "SERENA_HOME": str(self.home / ".serena"),
            "TMPDIR": str(self.temp_dir),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LLMS_FAKE_MANIFEST": str(self.repo / "agent-dependencies.json"),
        }
        self.temp_dir.mkdir()
        self.copy_repository()
        self.seed_home()
        self.write_fake_tools(node, jsonc_parser)

    def copy_repository(self) -> None:
        shutil.copytree(
            REPO_ROOT / "scripts",
            self.repo / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copy(REPO_ROOT / "agent-dependencies.json", self.repo / "agent-dependencies.json")
        # The skill check reads the skills folder and never writes to it.
        (self.repo / "skills").symlink_to(REPO_ROOT / "skills")

    def seed_home(self) -> None:
        for source in sorted(SEED.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(SEED)
            target = self.home / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            text = source.read_text(encoding="utf-8").replace("{HOME}", str(self.home))
            target.write_text(text, encoding="utf-8")
            target.chmod(SEED_MODES.get(relative.as_posix(), 0o600))

    def write_fake_tools(self, node: Path, jsonc_parser: Path) -> None:
        manifest = json.loads((self.repo / "agent-dependencies.json").read_text(encoding="utf-8"))
        versions = {name: spec["version"] for name, spec in manifest["tools"].items()}
        bin_dir = self.tools / "bin"
        write_executable(bin_dir / "serena", fake_command("serena"))
        write_executable(bin_dir / "serena-hooks", fake_command("serena-hooks"))
        write_executable(bin_dir / "cq", fake_command("cq"))
        write_executable(self.tools / "uv/serena-agent/bin/python", fake_command("serena-python"))
        # ast-grep and GitNexus are npm packages; the script finds their entry in package.json.
        npm = self.tools / "npm"
        ast_grep = npm / "node_modules/@ast-grep/cli"
        (ast_grep).mkdir(parents=True)
        (ast_grep / "package.json").write_text(
            json.dumps({"name": "@ast-grep/cli", "bin": {"ast-grep": "ast-grep"}}), encoding="utf-8"
        )
        write_executable(ast_grep / "ast-grep", fake_command("ast-grep"))
        gitnexus = npm / "node_modules/gitnexus"
        (gitnexus / "dist/cli").mkdir(parents=True)
        (gitnexus / "package.json").write_text(
            json.dumps(
                {
                    "name": "gitnexus",
                    "version": versions["gitnexus"],
                    "bin": {"gitnexus": "dist/cli/index.js"},
                }
            ),
            encoding="utf-8",
        )
        (gitnexus / "dist/cli/index.js").write_text(
            "const { spawnSync } = require('node:child_process');\n"
            f"const command = [{json.dumps(str(FAKE_TOOLS))}, 'gitnexus', __filename,"
            " ...process.argv.slice(2)];\n"
            f"const run = spawnSync({json.dumps(sys.executable)}, command,"
            " { stdio: 'inherit' });\n"
            "process.exit(run.status ?? 1);\n",
            encoding="utf-8",
        )
        # The script resolves jsonc-parser from the package.json beside node_modules.
        (npm / "package.json").write_text("{}\n", encoding="utf-8")
        shutil.copytree(jsonc_parser, npm / "node_modules/jsonc-parser")
        # Node and the runtime folders the script reads from runtime.json.
        self.node_dir.mkdir(parents=True)
        (self.node_dir / "node").symlink_to(node)
        write_executable(self.uv_dir / "uv", "#!/bin/sh\nexit 3\n")
        write_executable(self.task_dir / "task", "#!/bin/sh\nexit 3\n")
        (self.tools / "runtime.json").write_text(
            json.dumps(
                {
                    "node": str(self.node_dir / "node"),
                    "uv": str(self.uv_dir / "uv"),
                    "task": str(self.task_dir / "task"),
                }
            ),
            encoding="utf-8",
        )
        # Client programs on PATH. Setup only looks for them; calling one is a failure.
        for client in ("claude", "codex"):
            write_executable(
                self.client_dir / client, "#!/bin/sh\necho unexpected call >&2\nexit 3\n"
            )
        write_executable(self.client_dir / "opencode", "#!/bin/sh\necho 1.18.20\n")

    def run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), *arguments],
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
            check=False,
        )

    def snapshot(self) -> dict[str, tuple[bytes, int]]:
        """Bytes and permission bits of every file in the home folder."""
        return {
            path.relative_to(self.home).as_posix(): (
                path.read_bytes(),
                stat.S_IMODE(path.stat().st_mode),
            )
            for path in sorted(self.home.rglob("*"))
            if path.is_file()
        }

    def normalize(self, text: str) -> str:
        """Replace machine paths by placeholders; show PowerShell commands as plain text."""

        def decode(match: re.Match[str]) -> str:
            script = base64.b64decode(match.group(1)).decode("utf-16-le")
            return f"-EncodedCommand [decoded: {script}]"

        text = ENCODED_COMMAND.sub(decode, text)
        for path, placeholder in (
            (self.tools, "{TOOLS}"),
            (self.repo, "{REPO}"),
            (self.home, "{HOME}"),
            (self.node_dir, "{NODE_DIR}"),
            (self.uv_dir, "{UV_DIR}"),
            (self.task_dir, "{TASK_DIR}"),
            (self.client_dir, "{CLIENT_DIR}"),
        ):
            text = text.replace(str(path), placeholder)
        return text


@unittest.skipUnless(
    os.name == "posix", "the fake tools are shell scripts; setup is checked on POSIX only"
)
class ConfigureEndToEndTests(unittest.TestCase):
    sandbox: Sandbox
    doctor_before: dict[str, list[str]]
    first_run: subprocess.CompletedProcess[str]
    after_first: dict[str, tuple[bytes, int]]
    second_run: subprocess.CompletedProcess[str]
    after_second: dict[str, tuple[bytes, int]]
    doctor_after: dict[str, list[str]]

    @classmethod
    def setUpClass(cls) -> None:
        tools = pinned_node_and_jsonc_parser()
        if tools is None:
            reason = (
                "Node and the pinned jsonc-parser are missing; "
                "run ./bootstrap.sh deps:install and tools:install"
            )
            if os.environ.get("LLMS_REQUIRE_PINNED_TOOLS"):
                raise AssertionError(reason)
            raise unittest.SkipTest(reason)
        root = Path(tempfile.mkdtemp(prefix="llms-configure-"))
        cls.addClassCleanup(shutil.rmtree, root, ignore_errors=True)
        cls.sandbox = Sandbox(root, *tools)
        cls.doctor_before = cls.host_reasons()
        cls.first_run = cls.sandbox.run("--command", "configure", "--target", "all")
        cls.after_first = cls.sandbox.snapshot()
        cls.second_run = cls.sandbox.run("--command", "configure", "--target", "all")
        cls.after_second = cls.sandbox.snapshot()
        cls.doctor_after = cls.host_reasons()

    @classmethod
    def host_reasons(cls) -> dict[str, list[str]]:
        """Ask `doctor` why each host's configuration differs from what configure writes."""
        result = cls.sandbox.run("--command", "doctor", "--target", "all", "--output", "json")
        report = json.loads(result.stdout)
        return {entry["host"]: entry["reasons"] for entry in report["hosts"]}

    def read(self, relative: str) -> str:
        return self.after_first[relative][0].decode("utf-8")

    def test_both_runs_succeed(self) -> None:
        for name, run in (("first", self.first_run), ("second", self.second_run)):
            with self.subTest(run=name):
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_first_run_matches_golden_files(self) -> None:
        for relative in GOLDEN_FILES:
            with self.subTest(file=relative):
                self.assertIn(relative, self.after_first, f"configure did not write {relative}")
                actual = self.sandbox.normalize(self.read(relative))
                self.assertNotIn(
                    str(self.sandbox.root), actual, "a machine path is not a placeholder"
                )
                golden = GOLDEN / relative
                if os.environ.get("LLMS_WRITE_GOLDEN"):
                    golden.parent.mkdir(parents=True, exist_ok=True)
                    golden.write_text(actual, encoding="utf-8")
                self.assertEqual(actual, golden.read_text(encoding="utf-8"))

    def test_second_run_changes_no_file(self) -> None:
        self.assertEqual(sorted(self.after_second), sorted(self.after_first))
        for relative, first in self.after_first.items():
            with self.subTest(file=relative):
                self.assertEqual(self.after_second[relative], first)

    def test_codex_hooks_file_loses_group_write(self) -> None:
        self.assertEqual(self.after_first[".codex/hooks.json"][1], 0o644)
        for relative, (_, mode) in self.after_first.items():
            with self.subTest(file=relative):
                self.assertEqual(mode & 0o022, 0, f"{relative} is writable by others: {mode:o}")

    def test_server_only_opencode_json_is_removed(self) -> None:
        self.assertNotIn(".config/opencode/opencode.json", self.after_first)

    def test_claude_files_keep_user_content(self) -> None:
        config = json.loads(self.read(".claude.json"))
        seed = json.loads((SEED / ".claude.json").read_text(encoding="utf-8"))
        for key in ("numStartups", "userID", "oauthAccount", "projects"):
            self.assertEqual(config.get(key), seed[key], f"{key} changed")
        for name, server in seed["mcpServers"].items():
            self.assertEqual(config["mcpServers"][name], server)
        self.assertEqual(
            set(config["mcpServers"]) - set(seed["mcpServers"]), {"serena", "gitnexus"}
        )
        settings = json.loads(self.read(".claude/settings.json"))
        seed_settings = json.loads((SEED / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["model"], seed_settings["model"])
        self.assertEqual(settings["enabledPlugins"], seed_settings["enabledPlugins"])
        self.assertEqual(settings["env"]["EXAMPLE_FLAG"], "1")
        self.assertEqual(settings["env"]["CQ_ADDR"], "")
        self.assertIn(seed_settings["hooks"]["PostToolUse"][0], settings["hooks"]["PostToolUse"])

    def test_codex_files_keep_user_content(self) -> None:
        config = self.read(".codex/config.toml")
        self.assertIn("# Example Codex settings. Setup must keep these comments.", config)
        self.assertIn('[profiles.review]\nmodel = "example-review-model" # a profile table', config)
        self.assertIn('[mcp_servers.example-docs]\ncommand = "/opt/example/docs-server"', config)
        hooks = json.loads(self.read(".codex/hooks.json"))["hooks"]
        user_start = {"type": "command", "command": "/opt/example/codex-start.sh"}
        self.assertIn(user_start, [h for g in hooks["SessionStart"] for h in g["hooks"]])
        owned = [
            hook
            for group in hooks["PostToolUse"]
            for hook in group["hooks"]
            if "run_gitnexus_hook.mjs" in hook["command"]
        ]
        self.assertEqual(len(owned), 1)
        self.assertNotIn("gitnexus", json.dumps(hooks.get("PreToolUse", [])))

    def test_opencode_files_keep_user_content(self) -> None:
        config = self.read(".config/opencode/opencode.jsonc")
        self.assertIn("// Example OpenCode settings. Setup must keep these comments.", config)
        self.assertIn('"autoupdate": false, // a user setting', config)
        self.assertIn("// User servers, one per name under mcp.", config)
        for name in ("example-search", "example-remote"):
            self.assertIn(name, config)

    def test_pi_files_keep_user_content(self) -> None:
        self.assertTrue(
            self.read(".pi/agent/AGENTS.md").startswith("# My notes\n\nPrefer short answers.\n")
        )
        settings = json.loads(self.read(".pi/agent/settings.json"))
        self.assertEqual(settings["theme"], "example-dark")
        self.assertTrue(settings["shellCommandPrefix"].startswith("export EXAMPLE_VAR=1;"))

    def test_doctor_found_problems_before_configure(self) -> None:
        # Without this, "no problems after configure" could be true because doctor looks at nothing.
        self.assertEqual(set(self.doctor_before), set(HOSTS))
        self.assertTrue(all(self.doctor_before[host] for host in HOSTS), self.doctor_before)

    def test_doctor_reports_no_host_problems_after_configure(self) -> None:
        self.assertEqual(set(self.doctor_after), set(HOSTS))
        self.assertEqual(self.doctor_after, {host: [] for host in HOSTS})


if __name__ == "__main__":
    unittest.main()
