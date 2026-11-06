"""Tools are described by `agent-dependencies.json`: a fifth tool needs only a manifest entry.

The tests import the setup script and patch only what reaches outside a temporary folder:
the manifest path, the repository and tools folders, `run` and `download`.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "manage_agent_tools", ROOT / "scripts/manage_agent_tools.py"
)
assert spec is not None and spec.loader is not None
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

REAL_MANIFEST: dict[str, Any] = json.loads(
    (ROOT / "agent-dependencies.json").read_text(encoding="utf-8")
)
TOOL_NAMES = ", ".join(REAL_MANIFEST["tools"])
INSTALLER_NAMES = "uv, npm, github-release"
ENTRY_RULE = "must be a path inside the package when runs_with is node"
RELEASE_RULE = "must be <source>/releases/download/<tag>, with the tag ending in the version"


def real_entry(name: str) -> dict[str, Any]:
    return deepcopy(REAL_MANIFEST["tools"][name])


def real_tool(name: str) -> Any:
    return setup.parse_tools(deepcopy(REAL_MANIFEST))[name]


def with_installer(kind: str, **changes: Any) -> contextlib.AbstractContextManager[Any]:
    """Replace some functions of one installer record for the length of a block."""
    return patch.dict(setup.INSTALLERS, {kind: setup.INSTALLERS[kind]._replace(**changes)})


class TempManifestCase(unittest.TestCase):
    """A repository folder and tools folder in a temporary directory, with a manifest to edit."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.tools = self.root / ".tools/agent-tools"
        (self.root / "agent-tools").mkdir(parents=True)
        self.tools.mkdir(parents=True)
        self.manifest_path = self.root / "agent-dependencies.json"
        self.write_manifest(deepcopy(REAL_MANIFEST))
        for name, value in (
            ("ROOT", self.root),
            ("TOOLS", self.tools),
            ("MANIFEST", self.manifest_path),
        ):
            patcher = patch.object(setup, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        if os.name == "nt":
            # Windows tightens file access through PowerShell, which would show up in the
            # recorded commands; test_windows_branches checks that command.
            patcher = patch.object(setup, "private_permissions")
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_manifest(self, data: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(data), encoding="utf-8")

    def with_tool(self, name: str, entry: dict[str, Any]) -> None:
        data = deepcopy(REAL_MANIFEST)
        data["tools"][name] = entry
        self.write_manifest(data)

    def with_field(self, tool: str, field: str, value: Any) -> None:
        """Set a field of one of the real tools; None removes it."""
        data = deepcopy(REAL_MANIFEST)
        if value is None:
            del data["tools"][tool][field]
        else:
            data["tools"][tool][field] = value
        self.write_manifest(data)

    def main(self, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = setup.main(list(arguments))
        return status, output.getvalue()

    def files(self) -> list[str]:
        return sorted(str(path) for path in self.root.rglob("*"))


NEW_NPM_TOOL = {
    "package": "example-cli",
    "version": "2.0.0",
    "installer": "npm",
    "bin": "example",
    "runs_with": "node",
    "entry": "bin/example.js",
    "source": "https://example.invalid/example-cli",
}

NEW_UV_TOOL = {
    "package": "example-py",
    "version": "3.1.0",
    "installer": "uv",
    "bin": "example-py",
    "python": "3.12",
    "dependency_overrides": {"urllib3": "2.8.0"},
}


class FifthNpmToolTests(TempManifestCase):
    """Adding a fifth tool installed from npm changes only the manifest."""

    def setUp(self) -> None:
        super().setUp()
        self.with_tool("example", NEW_NPM_TOOL)

    def test_the_npm_package_lists_it(self) -> None:
        dependencies = setup.npm_package()["dependencies"]
        self.assertEqual(dependencies["example-cli"], "2.0.0")
        self.assertEqual(list(dependencies), ["@ast-grep/cli", "gitnexus", "example-cli"])

    def test_its_command_comes_from_its_fields_before_it_is_installed(self) -> None:
        with patch.object(setup, "node_command", return_value="/node"):
            command = setup.tool_command("example")
        package = self.tools / "npm/node_modules/example-cli"
        self.assertEqual(command, ["/node", str(package / "bin/example.js")])

    def test_its_command_comes_from_package_metadata_once_installed(self) -> None:
        package = self.tools / "npm/node_modules/example-cli"
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"bin": {"example": "lib/main.js"}}), encoding="utf-8"
        )
        with patch.object(setup, "node_command", return_value="/node"):
            command = setup.tool_command("example")
        self.assertEqual(command, ["/node", str(package / "lib/main.js")])

    def test_a_native_npm_tool_runs_its_bin_file(self) -> None:
        native = {k: v for k, v in NEW_NPM_TOOL.items() if k != "entry"}
        self.with_tool("example", {**native, "runs_with": "native"})
        package = self.tools / "npm/node_modules/example-cli"
        with patch.object(setup.os, "name", "posix"):
            self.assertEqual(setup.tool_command("example"), [str(package / "example")])

    def test_the_tool_option_accepts_it(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: Any) -> Any:
            calls.append(command)
            return type("Finished", (), {"returncode": 0})()

        with (
            patch.object(setup, "node_command", return_value="/node"),
            patch.object(setup, "installed_version", return_value="2.0.0"),
            patch.object(setup.subprocess, "run", side_effect=fake_run),
        ):
            status, _ = self.main("--command", "run", "--tool", "example", "--", "--help")
        self.assertEqual(status, 0)
        package = self.tools / "npm/node_modules/example-cli"
        self.assertEqual(calls, [["/node", str(package / "bin/example.js"), "--help"]])

    def test_one_npm_install_covers_every_npm_tool(self) -> None:
        versions = {"ast-grep": "0.0.0", "gitnexus": "0.0.0", "example": "0.0.0"}
        pinned = {name: tool.version for name, tool in setup.tools().items()}
        installs: list[str] = []

        def fake_install(tool: Any) -> None:
            installs.append(tool.name)
            versions.update({name: pinned[name] for name in versions})

        installed_types: set[str] = set()
        with (
            patch.object(setup, "installed_version", side_effect=versions.__getitem__),
            with_installer("npm", install=fake_install, is_stale=lambda tool: False),
            patch.object(setup, "tool_command", return_value=["x"]),
        ):
            results = [
                setup.install_tool(setup.tools()[name], installed_types) for name in versions
            ]
        self.assertEqual(installs, ["ast-grep"])
        self.assertEqual([result["action"] for result in results], ["installed"] * 3)


class NodeScriptTests(TempManifestCase):
    def test_a_node_tool_has_a_script(self) -> None:
        with patch.object(setup, "node_command", return_value="/node"):
            script = setup.node_script("gitnexus")
        self.assertEqual(script, str(self.tools / "npm/node_modules/gitnexus/dist/cli/index.js"))

    def test_other_tools_have_none(self) -> None:
        for name in ("ast-grep", "cq", "serena"):
            with self.subTest(tool=name), self.assertRaisesRegex(RuntimeError, "does not run with"):
                setup.node_script(name)


class ManifestValidationTests(TempManifestCase):
    def check_message(self, expected: str) -> None:
        with self.assertRaises(setup.ManifestError) as caught:
            setup.manifest()
        self.assertEqual(str(caught.exception), f"agent-dependencies.json {expected}")

    def test_an_unknown_installer_names_the_tool_and_the_field(self) -> None:
        self.with_field("gitnexus", "installer", "pip")
        self.check_message(f"tools.gitnexus.installer must be one of {INSTALLER_NAMES}")

    def test_a_missing_installer_is_the_same_error(self) -> None:
        self.with_field("cq", "installer", None)
        self.check_message(f"tools.cq.installer must be one of {INSTALLER_NAMES}")

    def test_the_schema_version_is_checked(self) -> None:
        data = deepcopy(REAL_MANIFEST)
        data["schema_version"] = 2
        self.write_manifest(data)
        with self.assertRaisesRegex(setup.ManifestError, "Unsupported agent-dependencies.json"):
            setup.manifest()

    def test_a_missing_bin(self) -> None:
        self.with_field("ast-grep", "bin", None)
        self.check_message(f"tools.ast-grep.bin {setup.PLAIN_RULE}")

    def test_an_npm_tool_needs_runs_with(self) -> None:
        self.with_field("gitnexus", "runs_with", None)
        self.check_message("tools.gitnexus.runs_with must be one of native, node")

    def test_a_node_tool_needs_an_entry(self) -> None:
        self.with_field("gitnexus", "entry", None)
        self.check_message(f"tools.gitnexus.entry {ENTRY_RULE}")

    def test_runs_with_and_entry_are_only_for_npm(self) -> None:
        for field in ("runs_with", "entry"):
            with self.subTest(field=field):
                self.with_field("cq", field, "native")
                self.check_message(f"tools.cq.{field} is only for tools whose installer is npm")

    def test_required_fields_for_each_installer(self) -> None:
        cases = [
            ("serena", "package", "must be a package name"),
            ("serena", "python", "must be a Python version such as 3.13"),
            ("serena", "version", "must be a version"),
            ("gitnexus", "package", "must be a package name"),
            ("cq", "version", "must be a version"),
            ("cq", "source", "must be a GitHub repository URL when installer is github-release"),
            ("cq", "release", RELEASE_RULE),
            ("cq", "checksums", "must map asset names to SHA-256 checksums"),
        ]
        for tool, field, message in cases:
            with self.subTest(tool=tool, field=field):
                self.with_field(tool, field, None)
                self.check_message(f"tools.{tool}.{field} {message}")

    def test_names_that_leave_the_tools_folder_are_refused(self) -> None:
        bad = ["../x", "/abs", "C:x", "-x", "a/b", "a\\b", "x..y", "", " x", "a\n"]
        for value in bad:
            for tool in ("cq", "serena", "ast-grep"):
                with self.subTest(tool=tool, field="bin", value=value):
                    self.with_field(tool, "bin", value)
                    self.check_message(f"tools.{tool}.bin {setup.PLAIN_RULE}")
            with self.subTest(field="extra_bins", value=value):
                self.with_field("serena", "extra_bins", [value])
                self.check_message("tools.serena.extra_bins must be a list of plain names")
            with self.subTest(field="tool name", value=value):
                self.with_tool(value, real_entry("cq"))
                with self.assertRaisesRegex(setup.ManifestError, "must be a plain name"):
                    setup.manifest()

    def test_packages_must_be_package_names(self) -> None:
        for value in ["-x", "a..b", "a\\b", "../x", "/abs", "C:x", "@scope", "@/x", "a b"]:
            for tool in ("serena", "gitnexus"):
                with self.subTest(tool=tool, value=value):
                    self.with_field(tool, "package", value)
                    self.check_message(f"tools.{tool}.package must be a package name")
        self.with_field("gitnexus", "package", "@scope/name")
        self.assertIn("gitnexus", setup.manifest()["tools"])

    def test_entries_must_stay_inside_the_package(self) -> None:
        bad = ["../x", "a/../x", "/abs", "C:x", "a\\b", "", "x.js\n"]
        bad += [".. /x", "a/.. ", " ..", "a/. /b", "a/b.", "a /b", "./a"]
        for value in bad:
            with self.subTest(value=value):
                self.with_field("gitnexus", "entry", value)
                self.check_message(f"tools.gitnexus.entry {ENTRY_RULE}")

    def test_a_release_must_name_a_tag_ending_in_the_version(self) -> None:
        wrong = [
            "https://github.com/mozilla-ai/cq/releases/download/cli/v9.9.9",
            "https://github.com/x/y/releases/latest",
            "http://github.com/x/y/releases/download/v0.18.0",
            "https://evil.com/download/v0.18.0",
            "https://github.com@evil.com/o/r/releases/download/v0.18.0",
            "https://evil.com/x?/download/v0.18.0",
            "https://github.com/o/r/releases/download/../../../../evil/v0.18.0",
            "https://github.com/other/repo/releases/download/cli/v0.18.0",
            "https://github.com/mozilla-ai/cq/releases/download/cli/v0.18.0?x=1",
            "https://github.com/mozilla-ai/cq/releases/download/cli/v0.18.0\n",
            "https://github.com/mozilla-ai/cq/releases/download/cli/#v0.18.0",
        ]
        for value in wrong:
            with self.subTest(value=value):
                self.with_field("cq", "release", value)
                self.check_message(f"tools.cq.release {RELEASE_RULE}")

    def test_a_trailing_newline_is_refused_everywhere(self) -> None:
        cases = [
            ("serena", "bin", "serena\n"),
            ("serena", "package", "serena-agent\n"),
            ("serena", "version", "1.7.0\n"),
            ("serena", "python", "3.13\n"),
            ("gitnexus", "package", "@s/p\n"),
            ("gitnexus", "entry", "dist/x.js\n"),
            ("cq", "source", "https://github.com/mozilla-ai/cq\n"),
            ("serena", "extra_bins", ["serena-hooks\n"]),
            ("serena", "dependency_overrides", {"urllib3\n": "2.8.0"}),
            ("serena", "dependency_overrides", {"urllib3": "2.8.0\n"}),
        ]
        for tool, field, value in cases:
            with self.subTest(tool=tool, field=field, value=value):
                self.with_field(tool, field, value)
                with self.assertRaises(setup.ManifestError):
                    setup.manifest()

    def test_the_source_must_be_a_github_repository(self) -> None:
        for value in ["https://example.com/a/b", "https://github.com/a", "git@github.com:a/b", 5]:
            with self.subTest(value=value):
                self.with_field("cq", "source", value)
                with self.assertRaisesRegex(setup.ManifestError, "tools.cq.source must be"):
                    setup.manifest()

    def test_dependency_overrides_must_map_packages_to_versions(self) -> None:
        for value in [["urllib3"], {"-x": "1"}, {"urllib3": "1 --pre"}, {"urllib3": 2}]:
            with self.subTest(value=value):
                self.with_field("serena", "dependency_overrides", value)
                self.check_message(
                    "tools.serena.dependency_overrides must map package names to versions"
                )

    def test_every_command_stops_before_any_download_install_or_write(self) -> None:
        self.with_field("gitnexus", "installer", "pip")
        before = self.files()
        message = (
            f"agent-dependencies.json tools.gitnexus.installer must be one of {INSTALLER_NAMES}"
        )
        for command in setup.COMMANDS:
            with (
                self.subTest(command=command),
                patch.object(setup, "download") as download,
                patch.object(setup, "run") as run,
                patch.object(setup.subprocess, "run") as subprocess_run,
            ):
                arguments = ["--command", command, *(["--tool", "serena"] * (command == "run"))]
                status, text = self.main(*arguments)
                self.assertEqual(status, 1)
                self.assertIn(message, text)
                for fake in (download, run, subprocess_run):
                    fake.assert_not_called()
                self.assertEqual(self.files(), before)

    def test_the_error_names_the_task_the_user_ran(self) -> None:
        self.with_field("gitnexus", "installer", "pip")
        _, text = self.main("--command", "install")
        self.assertEqual(
            text,
            "tools:install: agent-dependencies.json tools.gitnexus.installer must be one of "
            f"{INSTALLER_NAMES}\n",
        )

    def test_an_unknown_tool_lists_the_valid_names(self) -> None:
        status, text = self.main("--command", "run", "--tool", "nope", "--", "--version")
        self.assertEqual(status, 1)
        self.assertEqual(text, f"tools:run: unknown tool 'nope'; choose one of {TOOL_NAMES}\n")


class UvInstallerTests(TempManifestCase):
    def setUp(self) -> None:
        super().setUp()
        self.serena = real_tool("serena")
        self.uv = setup.INSTALLERS["uv"]

    def test_install_command(self) -> None:
        constraints = self.root / "agent-tools/serena-constraints.txt"
        constraints.write_text("a==1\n", encoding="utf-8")
        calls: list[list[str]] = []
        with (
            patch.object(setup.shutil, "which", return_value="/bin/uv"),
            patch.object(setup, "run", side_effect=lambda command, **_: calls.append(command)),
        ):
            self.uv.install(self.serena)
        self.assertEqual(
            calls,
            [
                [
                    "/bin/uv",
                    "tool",
                    "install",
                    "--python",
                    self.serena.python,
                    "--force",
                    f"{self.serena.package}=={self.serena.version}",
                    "--overrides",
                    str(self.tools / "serena-overrides.txt"),
                    "--constraints",
                    str(constraints),
                ]
            ],
        )
        self.assertEqual((self.tools / "serena-constraints.txt").read_text(), "a==1\n")
        overrides = (self.tools / "serena-overrides.txt").read_text(encoding="utf-8")
        for package, version in self.serena.dependency_overrides.items():
            self.assertIn(f"{package}=={version}\n", overrides)

    def test_install_without_a_constraints_file_adds_no_constraints(self) -> None:
        calls: list[list[str]] = []
        with (
            patch.object(setup.shutil, "which", return_value="/bin/uv"),
            patch.object(setup, "run", side_effect=lambda command, **_: calls.append(command)),
        ):
            self.uv.install(self.serena)
        self.assertNotIn("--constraints", calls[0])

    def test_install_needs_uv(self) -> None:
        with (
            patch.object(setup.shutil, "which", return_value=None),
            self.assertRaisesRegex(RuntimeError, "uv is missing"),
        ):
            self.uv.install(self.serena)

    def test_command_is_the_bin_in_the_tools_folder(self) -> None:
        with patch.object(setup.os, "name", "posix"):
            command = self.uv.command(self.serena)
        self.assertEqual(command, [str(self.tools / "bin/serena")])

    def test_version_comes_from_package_metadata_with_the_name_as_an_argument(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: Any) -> str:
            calls.append(command)
            return self.serena.version

        with (
            patch.object(setup.os, "name", "posix"),
            patch.object(setup, "run", side_effect=fake_run),
        ):
            version = self.uv.installed_version(self.serena)
        self.assertEqual(version, self.serena.version)
        python = self.tools / "uv" / self.serena.package / "bin/python"
        self.assertEqual(calls[0][0], str(python))
        self.assertEqual(calls[0][-1], self.serena.package)
        self.assertNotIn(self.serena.package, calls[0][2])

    def test_latest_version_comes_from_pypi(self) -> None:
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return json.dumps({"info": {"version": "1.8.0"}}).encode()

        with patch.object(setup, "download", side_effect=fake_download):
            latest = self.uv.latest_version(self.serena)
        self.assertEqual(latest, "1.8.0")
        self.assertEqual(urls, [f"https://pypi.org/pypi/{self.serena.package}/json"])

    def test_stale_when_the_constraints_file_differs(self) -> None:
        (self.root / "agent-tools/serena-constraints.txt").write_text("a==1\n", encoding="utf-8")
        with patch.object(
            setup, "override_versions", return_value=dict(self.serena.dependency_overrides)
        ):
            self.assertTrue(self.uv.is_stale(self.serena))
            (self.tools / "serena-constraints.txt").write_text("a==1\n", encoding="utf-8")
            self.assertFalse(self.uv.is_stale(self.serena))

    def test_stale_when_an_override_is_not_installed(self) -> None:
        with patch.object(setup, "override_versions", return_value={}):
            self.assertTrue(self.uv.is_stale(self.serena))
            problems = self.uv.problems(self.serena)
        self.assertEqual(
            problems,
            [
                "serena's pinned security patches (dependency_overrides in "
                "agent-dependencies.json) are not installed; run ./bootstrap.sh tools:install"
            ],
        )

    def test_doctor_reports_missing_overrides(self) -> None:
        with (
            patch.object(setup, "override_versions", return_value={}),
            patch.object(setup, "installed_version", side_effect=lambda n: real_tool(n).version),
            patch.object(setup, "selected_hosts", return_value=()),
            patch.object(setup, "skill_health", return_value={"problems": [], "hosts": []}),
            patch.object(setup, "serena_configuration", return_value={"configured": True}),
        ):
            result = setup.doctor("all")
        self.assertEqual(len(result["problems"]), 1)
        self.assertIn("serena's pinned security patches", result["problems"][0])
        self.assertFalse(result["healthy"])


class InstallToolTests(TempManifestCase):
    """The order of steps in `install_tool`, with the installer's functions faked."""

    def setUp(self) -> None:
        super().setUp()
        self.serena = real_tool("serena")
        self.installs: list[str] = []
        self.versions = {"serena": self.serena.version}

    def install_tool(
        self, overrides: dict[str, str] | None = None, **changes: Any
    ) -> dict[str, Any]:
        """Run install_tool; `overrides` are the dependency versions found in the environment."""
        found = dict(self.serena.dependency_overrides) if overrides is None else overrides

        def fake_install(tool: Any) -> None:
            self.installs.append(tool.name)

        defaults: dict[str, Any] = {"install": fake_install, "is_stale": lambda tool: False}
        with (
            with_installer("uv", **{**defaults, **changes}),
            patch.object(setup, "installed_version", side_effect=self.versions.__getitem__),
            patch.object(setup, "tool_command", return_value=["serena"]),
            patch.object(setup, "override_versions", return_value=found),
        ):
            return setup.install_tool(self.serena, set())

    def test_current_and_not_stale_installs_nothing(self) -> None:
        result = self.install_tool()
        self.assertEqual((self.installs, result["action"]), ([], "unchanged"))

    def test_current_version_with_stale_dependencies_installs(self) -> None:
        result = self.install_tool(is_stale=lambda tool: True)
        self.assertEqual((self.installs, result["action"]), (["serena"], "installed"))

    def test_a_wrong_version_installs(self) -> None:
        self.versions["serena"] = "0.0.1"

        def fix(tool: Any) -> None:
            self.installs.append(tool.name)
            self.versions["serena"] = tool.version

        result = self.install_tool(install=fix)
        self.assertEqual((self.installs, result["action"]), (["serena"], "installed"))

    def test_a_version_that_is_still_wrong_after_install_is_an_error(self) -> None:
        self.versions["serena"] = "0.0.1"
        with self.assertRaisesRegex(
            RuntimeError, f"serena: expected {self.serena.version}, installed version is '0.0.1'"
        ):
            self.install_tool()
        self.assertEqual(self.installs, ["serena"])

    def test_missing_overrides_after_install_are_an_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "serena's pinned security patches"):
            self.install_tool(overrides={}, is_stale=lambda tool: True)
        self.assertEqual(self.installs, ["serena"])


class NpmInstallerTests(TempManifestCase):
    def setUp(self) -> None:
        super().setUp()
        self.npm = setup.INSTALLERS["npm"]
        self.lock_source = self.root / "agent-tools/package-lock.json"

    def test_install_runs_npm_ci_on_the_committed_lock(self) -> None:
        dependencies = setup.npm_package()["dependencies"]
        lock = {"packages": {"": {"dependencies": dependencies}}}
        self.lock_source.write_text(json.dumps(lock))
        calls: list[list[str]] = []
        with (
            patch.object(setup, "npm_command", return_value=["/node", "/npm-cli.js"]),
            patch.object(setup, "run", side_effect=lambda command, **_: calls.append(command)),
        ):
            self.npm.install(real_tool("gitnexus"))
        self.assertEqual(
            calls,
            [
                [
                    "/node",
                    "/npm-cli.js",
                    "ci",
                    "--prefix",
                    str(self.tools / "npm"),
                    "--no-audit",
                    "--no-fund",
                ]
            ],
        )
        package = json.loads((self.tools / "npm/package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["dependencies"], dependencies)

    def test_install_refuses_a_lock_that_does_not_match_the_pins(self) -> None:
        self.lock_source.write_text(json.dumps({"packages": {"": {"dependencies": {}}}}))
        with self.assertRaisesRegex(RuntimeError, "npm lock does not match"):
            self.npm.install(real_tool("gitnexus"))

    def install_files(self, *, lock: str, package: Any) -> None:
        (self.tools / "npm").mkdir(parents=True, exist_ok=True)
        self.lock_source.write_text("lock\n", encoding="utf-8")
        (self.tools / "npm/package-lock.json").write_text(lock, encoding="utf-8")
        (self.tools / "npm/package.json").write_text(json.dumps(package), encoding="utf-8")

    def test_not_stale_when_lock_and_package_json_match(self) -> None:
        self.install_files(lock="lock\n", package=setup.npm_package())
        self.assertFalse(self.npm.is_stale(real_tool("gitnexus")))

    def test_stale_when_the_installed_package_json_differs(self) -> None:
        self.install_files(lock="lock\n", package={**setup.npm_package(), "version": "9.9.9"})
        self.assertTrue(self.npm.is_stale(real_tool("gitnexus")))

    def test_stale_when_the_installed_lock_differs(self) -> None:
        self.install_files(lock="old\n", package=setup.npm_package())
        self.assertTrue(self.npm.is_stale(real_tool("gitnexus")))

    def test_stale_when_nothing_is_installed(self) -> None:
        self.assertTrue(self.npm.is_stale(real_tool("gitnexus")))

    def test_version_comes_from_dash_dash_version(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: Any) -> str:
            calls.append(command)
            return "ast-grep 0.50.0"

        with (
            patch.object(setup.os, "name", "posix"),
            patch.object(setup, "run", side_effect=fake_run),
        ):
            version = self.npm.installed_version(real_tool("ast-grep"))
        self.assertEqual(version, "0.50.0")
        self.assertEqual(
            calls, [[str(self.tools / "npm/node_modules/@ast-grep/cli/ast-grep"), "--version"]]
        )

    def test_latest_version_comes_from_the_npm_registry(self) -> None:
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return json.dumps({"version": "0.51.0"}).encode()

        with patch.object(setup, "download", side_effect=fake_download):
            latest = self.npm.latest_version(real_tool("ast-grep"))
        self.assertEqual(latest, "0.51.0")
        self.assertEqual(urls, ["https://registry.npmjs.org/@ast-grep/cli/latest"])


class LockTests(TempManifestCase):
    """`tools:lock` writes one lock per installer type, with these exact command lines."""

    def fake_run(self, calls: list[tuple[list[str], dict[str, Any]]]) -> Callable[..., str]:
        def run(command: list[str], **kwargs: Any) -> str:
            calls.append((command, kwargs))
            if "--output-file" in command:
                Path(command[command.index("--output-file") + 1]).write_text("resolved\n")
            if "--package-lock-only" in command:
                prefix = Path(command[command.index("--prefix") + 1])
                (prefix / "package-lock.json").write_text("npm lock\n")
            return ""

        return run

    def lock(self) -> tuple[list[tuple[list[str], dict[str, Any]]], dict[str, Any]]:
        calls: list[tuple[list[str], dict[str, Any]]] = []
        with (
            patch.object(setup, "run", side_effect=self.fake_run(calls)),
            patch.object(setup.shutil, "which", return_value="/bin/uv"),
            patch.object(setup, "npm_command", return_value=["/node", "/npm-cli.js"]),
        ):
            return calls, setup.lock()

    def test_npm_lock_comes_first_then_each_uv_tool(self) -> None:
        self.with_tool("example", NEW_UV_TOOL)
        calls, result = self.lock()
        commands = [command for command, _ in calls]
        serena = real_tool("serena")
        self.assertEqual(len(commands), 3)
        npm, uv_serena, uv_example = commands
        self.assertEqual(npm[:2], ["/node", "/npm-cli.js"])
        for flag in ("install", "--package-lock-only", "--ignore-scripts", "--no-audit"):
            self.assertIn(flag, npm)
        self.assertEqual(uv_serena[:5], ["/bin/uv", "pip", "compile", "-", "--universal"])
        self.assertEqual(uv_serena[5:7], ["--python-version", serena.python])
        self.assertIn("--overrides", uv_serena)
        self.assertEqual(calls[1][1]["input_text"], f"{serena.package}=={serena.version}\n")
        self.assertEqual(calls[2][1]["input_text"], "example-py==3.1.0\n")
        self.assertEqual(uv_example[:5], ["/bin/uv", "pip", "compile", "-", "--universal"])
        self.assertEqual(uv_example[5:7], ["--python-version", "3.12"])
        self.assertEqual(
            [Path(lock["lockfile"]).name for lock in result["locks"]],
            ["package-lock.json", "serena-constraints.txt", "example-constraints.txt"],
        )
        written = self.root / "agent-tools/example-constraints.txt"
        self.assertEqual(written.read_text(), "resolved\n")
        self.assertEqual((self.root / "agent-tools/package-lock.json").read_text(), "npm lock\n")

    def test_a_manifest_without_npm_tools_writes_no_npm_lock(self) -> None:
        data = deepcopy(REAL_MANIFEST)
        data["tools"] = {name: data["tools"][name] for name in ("serena", "cq")}
        self.write_manifest(data)
        calls, _ = self.lock()
        self.assertEqual(len(calls), 1)
        self.assertIn("pip", calls[0][0])


class GithubReleaseInstallerTests(TempManifestCase):
    def archive(self, member: str, content: bytes) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            info = tarfile.TarInfo(member)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        return buffer.getvalue()

    def linux_x86_64(self) -> contextlib.AbstractContextManager[Any]:
        @contextlib.contextmanager
        def patched() -> Iterator[None]:
            with (
                patch.object(setup.platform, "system", return_value="Linux"),
                patch.object(setup.platform, "machine", return_value="x86_64"),
            ):
                yield

        return patched()

    def release_tool(self, name: str, payload: bytes) -> Any:
        """The manifest's cq entry under another tool name, with the checksum of the payload."""
        entry = real_entry("cq")
        entry["checksums"]["cq_Linux_x86_64.tar.gz"] = hashlib.sha256(payload).hexdigest()
        self.with_tool(name, entry)
        return setup.tools()[name]

    def test_install_downloads_checks_and_writes_the_executable(self) -> None:
        payload = self.archive("cq_Linux_x86_64/cq", b"#!/bin/sh\n")
        cq = self.release_tool("cq", payload)
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return payload

        with self.linux_x86_64(), patch.object(setup, "download", side_effect=fake_download):
            setup.INSTALLERS["github-release"].install(cq)
        self.assertEqual(urls, [f"{cq.release}/cq_Linux_x86_64.tar.gz"])
        installed = self.tools / "bin/cq"
        self.assertEqual(installed.read_bytes(), b"#!/bin/sh\n")
        if os.name != "nt":  # Windows has no executable bit.
            self.assertTrue(installed.stat().st_mode & 0o100)

    def test_the_asset_and_file_names_come_from_bin_not_the_tool_name(self) -> None:
        payload = self.archive("dist/cq", b"binary")
        tool = self.release_tool("queue-tool", payload)
        self.assertEqual(tool.bin, "cq")
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return payload

        with self.linux_x86_64(), patch.object(setup, "download", side_effect=fake_download):
            setup.INSTALLERS["github-release"].install(tool)
        self.assertEqual(urls, [f"{tool.release}/cq_Linux_x86_64.tar.gz"])
        self.assertEqual((self.tools / "bin/cq").read_bytes(), b"binary")
        self.assertFalse((self.tools / "bin/queue-tool").exists())

    def test_install_refuses_a_download_that_does_not_match_its_checksum(self) -> None:
        cq = real_tool("cq")
        with (
            self.linux_x86_64(),
            patch.object(setup, "download", return_value=b"tampered"),
            self.assertRaisesRegex(RuntimeError, "cq release checksum mismatch"),
        ):
            setup.INSTALLERS["github-release"].install(cq)
        self.assertFalse((self.tools / "bin/cq").exists())

    def test_install_needs_exactly_one_executable_in_the_archive(self) -> None:
        payload = self.archive("README", b"text")
        cq = self.release_tool("cq", payload)
        with (
            self.linux_x86_64(),
            patch.object(setup, "download", return_value=payload),
            self.assertRaisesRegex(RuntimeError, "must contain exactly one executable"),
        ):
            setup.INSTALLERS["github-release"].install(cq)

    def test_version_comes_from_dash_dash_version(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: Any) -> str:
            calls.append(command)
            return "cq version 0.18.0"

        with (
            patch.object(setup.os, "name", "posix"),
            patch.object(setup, "run", side_effect=fake_run),
        ):
            version = setup.INSTALLERS["github-release"].installed_version(real_tool("cq"))
        self.assertEqual(version, "0.18.0")
        self.assertEqual(calls, [[str(self.tools / "bin/cq"), "--version"]])

    def latest(self, releases: list[dict[str, Any]]) -> tuple[str, list[str]]:
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return json.dumps(releases).encode()

        with patch.object(setup, "download", side_effect=fake_download):
            return setup.INSTALLERS["github-release"].latest_version(real_tool("cq")), urls

    def test_latest_version_is_the_newest_stable_release_with_the_pinned_tag_style(self) -> None:
        latest, urls = self.latest(
            [
                {"tag_name": "cli/v0.20.0-rc1", "prerelease": True},
                {"tag_name": "plugin/v9.0.0", "prerelease": False},
                {"tag_name": "cli/v0.19.0", "prerelease": False},
                {"tag_name": "cli/v0.18.0", "prerelease": False},
            ]
        )
        self.assertEqual(latest, "0.19.0")
        self.assertEqual(urls, ["https://api.github.com/repos/mozilla-ai/cq/releases?per_page=30"])

    def test_no_matching_release_is_a_clear_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "cq: no stable release"):
            self.latest([{"tag_name": "plugin/v9.0.0", "prerelease": False}])


class CheckCommandTests(TempManifestCase):
    def test_every_installer_looks_up_its_latest_version(self) -> None:
        self.with_tool("example", NEW_NPM_TOOL)
        pages = {
            "https://pypi.org/pypi/serena-agent/json": {"info": {"version": "1.1.1"}},
            "https://registry.npmjs.org/@ast-grep/cli/latest": {"version": "2.2.2"},
            "https://registry.npmjs.org/gitnexus/latest": {"version": "3.3.3"},
            "https://registry.npmjs.org/example-cli/latest": {"version": "4.4.4"},
            "https://api.github.com/repos/mozilla-ai/cq/releases?per_page=30": [
                {"tag_name": "cli/v5.5.5", "prerelease": False}
            ],
        }
        with (
            patch.object(
                setup, "download", side_effect=lambda url: json.dumps(pages[url]).encode()
            ),
            patch.object(setup, "installed_version", return_value=None),
            patch.object(setup, "selected_hosts", return_value=()),
        ):
            status, text = self.main("--command", "check", "--output", "json")
        self.assertEqual(status, 0)
        latest = {entry["tool"]: entry["latest"] for entry in json.loads(text)["tools"]}
        self.assertEqual(
            latest,
            {
                "serena": "1.1.1",
                "ast-grep": "2.2.2",
                "gitnexus": "3.3.3",
                "cq": "5.5.5",
                "example": "4.4.4",
            },
        )


class TaskfileQuotingTests(unittest.TestCase):
    """`tools:run` hands TOOL to the shell, so it must arrive as one argument."""

    def tools_run_command(self) -> str:
        text = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")
        block = re.search(r"^  tools:run:\n(.*?)(?=^  \S)", text, re.S | re.M)
        assert block is not None
        command = re.search(r"^    cmd: '(.*)'$", block.group(1), re.M)
        assert command is not None
        return command.group(1).replace("''", "'")

    def test_the_tool_variable_is_shell_quoted(self) -> None:
        self.assertIn("--tool {{shellQuote .TOOL}}", self.tools_run_command())
        self.assertNotIn("{{.TOOL}}", self.tools_run_command())

    def pinned_task(self) -> str | None:
        found = shutil.which("task")
        if found:
            return found
        candidates = sorted((ROOT / ".tools/mise/data/installs/task").glob("*/task"))
        return str(candidates[-1]) if candidates else None

    def test_shell_metacharacters_in_tool_arrive_as_one_argument(self) -> None:
        task = self.pinned_task()
        if task is None:
            self.skipTest("the pinned Task is not installed")
        command = self.tools_run_command().replace(
            "{{.PYTHON}} scripts/manage_agent_tools.py", "printf '[%s]'"
        )
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Taskfile.yml").write_text(
                f"version: '3'\ntasks:\n  tools:run:\n    cmd: |\n      {command}\n",
                encoding="utf-8",
            )
            for payload in ("x; echo INJECTED", "serena --command configure", "$(echo INJECTED)"):
                with self.subTest(payload=payload):
                    result = subprocess.run(
                        [task, "--dir", folder, "tools:run", f"TOOL={payload}", "--", "a"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, f"[--command][run][--tool][{payload}][--][a]")


if __name__ == "__main__":
    unittest.main()
