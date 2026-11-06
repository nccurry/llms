"""Run `manage_agent_tools.py --command configure` in a fake home and check the result.

The setup script is a black box here. The test copies it into a temporary
repository, seeds a temporary home, fixes the environment, and runs the
script's command line. Nothing inside the script is patched or imported, so
the script's functions can be renamed or split without touching this test.

The temporary repository holds a copy of `scripts/` (everything in it),
`agent-dependencies.json`, and a read-only link to `skills/`. Setup code must
stay under `scripts/`, or this test must be told about the new place. The
fake tools folder (`.tools/agent-tools`), the home and the PATH folders are
built from scratch in the sandbox.

What is faked: the upstream installers and version probes (serena, cq,
gitnexus, ast-grep, Serena's own Python) and the client programs on PATH. The
stand-ins are in tests/fixtures/configure/ (fake_upstream_tools.py and
fake_gitnexus_cli.js).

What is real: the setup script, and Node with the pinned `jsonc-parser`
package, which the script and the GitNexus stand-in use to edit opencode.jsonc
without losing comments. They come from the pinned install in this checkout
(`.tools/agent-tools`). The tests are skipped when they are missing, unless
LLMS_REQUIRE_PINNED_TOOLS is set, which makes a missing install a failure.

The main run (class ConfigureEndToEndTests) seeds tests/fixtures/configure/seed,
runs configure twice, and compares the written files with tests/fixtures/
configure/golden. Machine paths are replaced by placeholders before comparing:
{HOME}, {REPO}, {TOOLS}, {NODE_DIR}, {UV_DIR}, {TASK_DIR} and {CLIENT_DIR}.
Each scenario (class ConfigureScenarioTests) adds seed files from
tests/fixtures/configure/scenarios/<name>/seed and compares the files in its
golden folder. To write the golden files again after an approved change in what
setup writes, run the tests with LLMS_WRITE_GOLDEN=1; they then fail on purpose
so a rewrite is never mistaken for a pass. Review the diff.
"""

from __future__ import annotations

import base64
import dataclasses
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
SCENARIOS = FIXTURES / "scenarios"
FAKE_TOOLS = FIXTURES / "fake_upstream_tools.py"
FAKE_GITNEXUS_CLI = FIXTURES / "fake_gitnexus_cli.js"
PINNED = REPO_ROOT / ".tools/agent-tools"
REGEN_HINT = "after an approved change, run the tests with LLMS_WRITE_GOLDEN=1 and review the diff"
POSIX_ONLY = "the fake tools are shell scripts; setup is checked on POSIX only"

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
# The mode each golden file has after setup. The two AGENTS.md files are made by the fake cq,
# not by setup, and the fakes make new files 0644. Setup makes serena_config.yml, so it is private.
EXPECTED_MODES = {
    ".claude.json": 0o600,
    ".claude/settings.json": 0o600,
    ".codex/config.toml": 0o600,
    ".codex/hooks.json": 0o644,
    ".codex/AGENTS.md": 0o644,
    ".config/opencode/opencode.jsonc": 0o644,
    ".config/opencode/AGENTS.md": 0o644,
    ".pi/agent/AGENTS.md": 0o644,
    ".pi/agent/settings.json": 0o644,
    ".serena/serena_config.yml": 0o600,
}
ENCODED_COMMAND = re.compile(r"-EncodedCommand ([A-Za-z0-9+/=]+)")
SAFE_PATH = re.compile(r"[A-Za-z0-9_./-]+")
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


def require_pinned_tools() -> tuple[Path, Path]:
    """Return the real tools, or skip (fail when LLMS_REQUIRE_PINNED_TOOLS is set)."""
    tools = pinned_node_and_jsonc_parser()
    if tools is None:
        reason = (
            "Node and the pinned jsonc-parser are missing; "
            "run ./bootstrap.sh deps:install and tools:install"
        )
        if os.environ.get("LLMS_REQUIRE_PINNED_TOOLS"):
            raise AssertionError(reason)
        raise unittest.SkipTest(reason)
    return tools


def make_sandbox_root() -> Path:
    """A new folder whose path has only letters, digits and `_./-` (a space changes quoting)."""
    fallback = Path("/tmp")  # noqa: S108 - used only when the default folder has an odd path
    for base in (Path(tempfile.gettempdir()).resolve(), fallback):
        if SAFE_PATH.fullmatch(str(base)) and base.is_dir():
            return Path(tempfile.mkdtemp(prefix="llms-configure-", dir=base)).resolve()
    raise unittest.SkipTest("no temporary folder with a plain path (spaces change the output)")


def write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


@dataclasses.dataclass
class Options:
    """What differs between runs: seed files, client programs and installer behavior."""

    scenario: str | None = None
    claude_cli: bool = True
    opencode_version: str = "1.18.20"
    serena_setup_fails: bool = False


class Sandbox:
    """A temporary home, repository copy and fake tools folder with a fixed environment."""

    def __init__(self, tools: tuple[Path, Path], options: Options) -> None:
        self.root = make_sandbox_root()
        self.options = options
        self.home = self.root / "home"
        self.repo = self.root / "repo"
        self.tools = self.repo / ".tools/agent-tools"
        self.node_dir = self.root / "runtime/node"
        self.uv_dir = self.root / "runtime/uv"
        self.task_dir = self.root / "runtime/task"
        self.client_dir = self.root / "clients"
        self.temp_dir = self.root / "tmp"
        self.script = self.repo / "scripts/manage_agent_tools.py"
        self.manifest = self.repo / "agent-dependencies.json"
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.client_dir),
            "LLMS_ORIGINAL_PATH": str(self.client_dir),
            "SERENA_HOME": str(self.home / ".serena"),
            "TMPDIR": str(self.temp_dir),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.temp_dir.mkdir()
        self.copy_repository()
        self.seed_home()
        self.write_fake_tools(*tools)

    def remove(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def fake_command(self, tool: str, **environment: str) -> str:
        """A shell wrapper that hands its own path and arguments to the stand-in for `tool`."""
        variables = {"LLMS_FAKE_MANIFEST": str(self.manifest), **environment}
        exports = "".join(f"export {k}={shlex.quote(v)}\n" for k, v in variables.items())
        return (
            f"#!/bin/sh\n{exports}"
            f'exec {shlex.quote(sys.executable)} {shlex.quote(str(FAKE_TOOLS))} {tool} "$0" "$@"\n'
        )

    def copy_repository(self) -> None:
        shutil.copytree(
            REPO_ROOT / "scripts",
            self.repo / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copy(REPO_ROOT / "agent-dependencies.json", self.manifest)
        # The skill check reads the skills folder and never writes to it.
        (self.repo / "skills").symlink_to(REPO_ROOT / "skills")

    def seed_home(self) -> None:
        folders = [SEED]
        if self.options.scenario:
            folders.append(SCENARIOS / self.options.scenario / "seed")
        for folder in folders:
            for source in sorted(folder.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(folder)
                target = self.home / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (
                    source.read_text(encoding="utf-8")
                    .replace("{HOME}", str(self.home))
                    .replace("{TOOLS}", str(self.tools))
                )
                target.write_text(text, encoding="utf-8")
                target.chmod(SEED_MODES.get(relative.as_posix(), 0o600))

    def write_fake_tools(self, node: Path, jsonc_parser: Path) -> None:
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        bin_dir = self.tools / "bin"
        serena_setup = {"LLMS_FAKE_SERENA_SETUP": "fail"} if self.options.serena_setup_fails else {}
        write_executable(bin_dir / "serena", self.fake_command("serena", **serena_setup))
        write_executable(bin_dir / "serena-hooks", self.fake_command("serena-hooks"))
        write_executable(bin_dir / "cq", self.fake_command("cq"))
        write_executable(
            self.tools / "uv/serena-agent/bin/python", self.fake_command("serena-python")
        )
        # ast-grep and GitNexus are npm packages; the script finds their entry in package.json.
        npm = self.tools / "npm"
        ast_grep = npm / "node_modules/@ast-grep/cli"
        ast_grep.mkdir(parents=True)
        (ast_grep / "package.json").write_text(
            json.dumps({"name": "@ast-grep/cli", "bin": {"ast-grep": "ast-grep"}}),
            encoding="utf-8",
        )
        write_executable(ast_grep / "ast-grep", self.fake_command("ast-grep"))
        gitnexus = npm / "node_modules/gitnexus"
        (gitnexus / "dist/cli").mkdir(parents=True)
        (gitnexus / "package.json").write_text(
            json.dumps(
                {
                    "name": "gitnexus",
                    "version": manifest["tools"]["gitnexus"]["version"],
                    "bin": {"gitnexus": "dist/cli/index.js"},
                }
            ),
            encoding="utf-8",
        )
        config = {
            "python": sys.executable,
            "fakeTools": str(FAKE_TOOLS),
            "manifest": str(self.manifest),
        }
        (gitnexus / "dist/cli/index.js").write_text(
            f"const CONFIG = {json.dumps(config)};\n"
            + FAKE_GITNEXUS_CLI.read_text(encoding="utf-8"),
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
        self.client_dir.mkdir()
        clients = ["codex", *(["claude"] if self.options.claude_cli else [])]
        for client in clients:
            write_executable(
                self.client_dir / client, "#!/bin/sh\necho unexpected call >&2\nexit 3\n"
            )
        write_executable(
            self.client_dir / "opencode", f"#!/bin/sh\necho {self.options.opencode_version}\n"
        )

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

    def configure(self) -> subprocess.CompletedProcess[str]:
        return self.run("--command", "configure", "--target", "all")

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

    def host_reasons(self) -> dict[str, list[str]]:
        """Ask `doctor` why each host's configuration differs from what configure writes."""
        result = self.run("--command", "doctor", "--target", "all", "--output", "json")
        try:
            report = json.loads(result.stdout)
        except ValueError:
            raise AssertionError(
                f"doctor printed no JSON:\n{result.stdout}\n{result.stderr}"
            ) from None
        if "hosts" not in report:
            raise AssertionError(f"doctor failed: {report}\n{result.stderr}")
        return {entry["host"]: entry["reasons"] for entry in report["hosts"]}


def compare_with_golden(
    case: unittest.TestCase, sandbox: Sandbox, golden_dir: Path, relative: str, text: str
) -> None:
    """Check one written file against its golden copy, or rewrite it in LLMS_WRITE_GOLDEN mode."""
    actual = sandbox.normalize(text)
    case.assertNotIn(str(sandbox.root), actual, "a machine path is not a placeholder")
    golden = golden_dir / relative
    if os.environ.get("LLMS_WRITE_GOLDEN") == "1":
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(actual, encoding="utf-8")
        case.fail(f"golden file rewritten: {golden}; review the diff")
    if not golden.is_file():
        case.fail(f"golden file missing: {golden}; {REGEN_HINT}")
    case.assertEqual(
        actual,
        golden.read_text(encoding="utf-8"),
        f"{relative} differs from {golden}; {REGEN_HINT}",
    )


@unittest.skipUnless(os.name == "posix", POSIX_ONLY)
class ConfigureEndToEndTests(unittest.TestCase):
    maxDiff = None
    sandbox: Sandbox
    doctor_before: dict[str, list[str]]
    first_run: subprocess.CompletedProcess[str]
    after_first: dict[str, tuple[bytes, int]]
    second_run: subprocess.CompletedProcess[str]
    after_second: dict[str, tuple[bytes, int]]
    doctor_after: dict[str, list[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.sandbox = Sandbox(require_pinned_tools(), Options())
        cls.addClassCleanup(cls.sandbox.remove)
        cls.doctor_before = cls.sandbox.host_reasons()
        cls.first_run = cls.sandbox.configure()
        cls.after_first = cls.sandbox.snapshot()
        cls.second_run = cls.sandbox.configure()
        cls.after_second = cls.sandbox.snapshot()
        cls.doctor_after = cls.sandbox.host_reasons()

    def read(self, relative: str) -> str:
        return self.after_first[relative][0].decode("utf-8")

    def test_golden_and_seed_files_are_tracked_by_git(self) -> None:
        # A rule such as `.serena/` in .gitignore can hide a golden file from a fresh clone.
        if shutil.which("git") is None or not (REPO_ROOT / ".git").exists():
            self.skipTest("not a git checkout")
        files = [GOLDEN / relative for relative in GOLDEN_FILES]
        files += [path for path in SEED.rglob("*") if path.is_file()]
        files += [path for path in SCENARIOS.rglob("*") if path.is_file()]
        for path in files:
            with self.subTest(file=path.relative_to(REPO_ROOT).as_posix()):
                self.assertTrue(path.is_file(), f"fixture file missing: {path}; {REGEN_HINT}")
                tracked = subprocess.run(
                    ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    tracked.returncode,
                    0,
                    f"{path} is not tracked by git (ignored?): {tracked.stderr}",
                )

    def test_both_runs_succeed(self) -> None:
        for name, run in (("first", self.first_run), ("second", self.second_run)):
            with self.subTest(run=name):
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_first_run_matches_golden_files(self) -> None:
        for relative in GOLDEN_FILES:
            with self.subTest(file=relative):
                self.assertIn(relative, self.after_first, f"configure did not write {relative}")
                compare_with_golden(self, self.sandbox, GOLDEN, relative, self.read(relative))

    def test_golden_files_have_the_expected_modes(self) -> None:
        self.assertEqual(set(EXPECTED_MODES), set(GOLDEN_FILES))
        for relative, expected in EXPECTED_MODES.items():
            with self.subTest(file=relative):
                self.assertEqual(
                    f"{self.after_first[relative][1]:o}", f"{expected:o}", f"mode of {relative}"
                )

    def test_second_run_writes_the_same_files(self) -> None:
        self.assertEqual(sorted(self.after_second), sorted(self.after_first))

    def test_second_run_keeps_every_file_unchanged(self) -> None:
        for relative, (text, mode) in self.after_first.items():
            with self.subTest(file=relative):
                again_text, again_mode = self.after_second[relative]
                self.assertEqual(again_text.decode("utf-8"), text.decode("utf-8"))
                self.assertEqual(f"{again_mode:o}", f"{mode:o}", f"mode of {relative}")

    def test_no_file_is_writable_by_group_or_others(self) -> None:
        for relative, (_, mode) in self.after_first.items():
            with self.subTest(file=relative):
                self.assertEqual(mode & 0o022, 0, f"{relative} is writable by others: {mode:o}")

    def test_server_only_opencode_json_is_removed_after_the_installer_made_it(self) -> None:
        self.assertNotIn(".config/opencode/opencode.json", self.after_first)
        # Setup backs a file up before it deletes it, so a backup proves the fake cq made it.
        backups = list(self.sandbox.tools.glob("config-backups/*/opencode.json"))
        self.assertTrue(backups, "no backup of opencode.json: the fake installer did not make one")
        created = json.loads(backups[0].read_text(encoding="utf-8"))
        self.assertEqual(list(created), ["$schema", "mcp"])

    def test_claude_files_keep_user_content(self) -> None:
        config = json.loads(self.read(".claude.json"))
        seed = json.loads((SEED / ".claude.json").read_text(encoding="utf-8"))
        for key in ("numStartups", "userID", "oauthAccount", "projects"):
            self.assertEqual(config.get(key), seed[key], f"{key} changed")
        for name, server in seed["mcpServers"].items():
            self.assertEqual(config["mcpServers"][name], server)
        added = set(config["mcpServers"]) - set(seed["mcpServers"])
        self.assertEqual(added, {"serena", "gitnexus"})
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
        agents = self.read(".pi/agent/AGENTS.md")
        self.assertTrue(agents.startswith("# My notes\n\nPrefer short answers.\n"))
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


@unittest.skipUnless(os.name == "posix", POSIX_ONLY)
class ConfigureScenarioTests(unittest.TestCase):
    """One seed variant per test, run once through the same command line."""

    maxDiff = None

    def start(self, options: Options) -> Sandbox:
        sandbox = Sandbox(require_pinned_tools(), options)
        self.addCleanup(sandbox.remove)
        return sandbox

    def check_golden(self, sandbox: Sandbox, scenario: str) -> None:
        folder = SCENARIOS / scenario / "golden"
        files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
        self.assertTrue(files, f"scenario {scenario} has no golden files")
        written = sandbox.snapshot()
        for relative in files:
            with self.subTest(file=relative):
                self.assertIn(relative, written)
                text = written[relative][0].decode("utf-8")
                compare_with_golden(self, sandbox, folder, relative, text)

    def test_codex_home_elsewhere_stops_before_writing(self) -> None:
        sandbox = self.start(Options())
        sandbox.env["CODEX_HOME"] = str(sandbox.root / "other-codex")
        before = sandbox.snapshot()
        result = sandbox.configure()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("CODEX_HOME is set to", result.stdout)
        self.assertEqual(sandbox.snapshot(), before)

    def test_serena_home_differing_from_the_managed_one_stops_setup(self) -> None:
        sandbox = self.start(Options(scenario="serena_home_mismatch"))
        before = sandbox.snapshot()
        result = sandbox.configure()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("claude has a different Serena home", result.stdout)
        self.assertEqual(sandbox.snapshot(), before)

    def test_old_manual_cq_entry_moves_into_the_cq_plugin_setup(self) -> None:
        sandbox = self.start(Options(scenario="cq_plugin_manual_entry"))
        result = sandbox.configure()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("dropped EXAMPLE_EXTRA from the old cq server entry", result.stdout)
        self.assertNotIn("dropped UV_", result.stdout)
        written = sandbox.snapshot()
        config = json.loads(written[".claude.json"][0])
        self.assertNotIn("cq", config["mcpServers"])
        env = json.loads(written[".claude/settings.json"][0])["env"]
        self.assertEqual(env["UV_PYTHON_INSTALL_DIR"], "/old/python")
        self.assertEqual(env["UV_CACHE_DIR"], "/old/cache")
        self.assertNotIn("EXAMPLE_EXTRA", env)
        self.check_golden(sandbox, "cq_plugin_manual_entry")
        self.assertEqual(sandbox.host_reasons()["claude"], [])

    def test_unmanaged_cq_entry_conflicts_with_the_cq_plugin(self) -> None:
        sandbox = self.start(Options(scenario="cq_plugin_foreign_entry"))
        result = sandbox.configure()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("An existing unmanaged Claude cq server conflicts", result.stdout)
        config = json.loads(sandbox.snapshot()[".claude.json"][0])
        self.assertEqual(config["mcpServers"]["cq"]["command"], "/opt/example/other-cq")

    def test_opencode_2_gets_servers_under_mcp_servers(self) -> None:
        sandbox = self.start(Options(scenario="opencode_2", opencode_version="2.1.0"))
        result = sandbox.configure()
        self.assertEqual(result.returncode, 0, result.stdout)
        written = sandbox.snapshot()[".config/opencode/opencode.jsonc"][0].decode("utf-8")
        self.assertIn('"servers": {', written)
        self.check_golden(sandbox, "opencode_2")

    def test_missing_claude_cli_leaves_a_cq_plugin_follow_up(self) -> None:
        sandbox = self.start(Options(scenario="no_claude_cli", claude_cli=False))
        result = sandbox.configure()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("cq's Claude plugin installation requires Claude CLI", result.stdout)
        self.check_golden(sandbox, "no_claude_cli")

    def test_failing_serena_setup_makes_setup_write_the_entry_itself(self) -> None:
        sandbox = self.start(Options(scenario="serena_setup_fails", serena_setup_fails=True))
        result = sandbox.configure()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("serena setup codex failed, so this script wrote Serena's", result.stdout)
        self.assertIn("serena setup claude-code failed", result.stdout)
        self.check_golden(sandbox, "serena_setup_fails")

    def test_user_owned_opencode_json_is_kept(self) -> None:
        sandbox = self.start(Options(scenario="opencode_json_user_file"))
        result = sandbox.configure()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(".config/opencode/opencode.json", sandbox.snapshot())
        self.check_golden(sandbox, "opencode_json_user_file")


if __name__ == "__main__":
    unittest.main()
