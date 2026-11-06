"""Tools are described by `agent-dependencies.json`: a fifth tool needs only a manifest entry.

The tests import the setup script and patch only what reaches outside a temporary folder:
the manifest path, the repository and tools folders, `run` and `download`.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from collections.abc import Iterator
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
TOOL_NAMES = "serena, ast-grep, gitnexus, cq"


def real_spec(name: str) -> dict[str, Any]:
    return deepcopy(REAL_MANIFEST["tools"][name])


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


NEW_NPM_TOOL = {
    "package": "example-cli",
    "version": "2.0.0",
    "installer": "npm",
    "bin": "example",
    "runs_with": "node",
    "entry": "bin/example.js",
    "source": "https://example.invalid/example-cli",
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
        pinned = {name: entry["version"] for name, entry in setup.manifest()["tools"].items()}
        installs: list[str] = []

        def fake_install(*_: Any) -> None:
            installs.append("npm")
            versions.update({name: pinned[name] for name in versions})

        installed_types: set[str] = set()
        with (
            patch.object(setup, "installed_version", side_effect=versions.__getitem__),
            patch.object(setup.NpmInstaller, "install", side_effect=fake_install),
            patch.object(setup.NpmInstaller, "is_stale", return_value=False),
            patch.object(setup, "tool_command", return_value=["x"]),
        ):
            results = [
                setup.install_tool(name, setup.manifest()["tools"][name], installed_types)
                for name in versions
            ]
        self.assertEqual(installs, ["npm"])
        self.assertEqual([result["action"] for result in results], ["installed"] * 3)


class ManifestValidationTests(TempManifestCase):
    def check_message(self, expected: str) -> None:
        with self.assertRaises(setup.ManifestError) as caught:
            setup.manifest()
        self.assertEqual(str(caught.exception), f"agent-dependencies.json {expected}")

    def test_an_unknown_installer_names_the_tool_and_the_field(self) -> None:
        self.with_field("gitnexus", "installer", "pip")
        self.check_message("tools.gitnexus.installer must be one of uv, npm, github-release")

    def test_a_missing_installer_is_the_same_error(self) -> None:
        self.with_field("cq", "installer", None)
        self.check_message("tools.cq.installer must be one of uv, npm, github-release")

    def test_a_missing_bin(self) -> None:
        self.with_field("ast-grep", "bin", None)
        self.check_message("tools.ast-grep.bin must be a non-empty string")

    def test_extra_bins_must_be_a_list_of_names(self) -> None:
        self.with_field("serena", "extra_bins", "serena-hooks")
        self.check_message("tools.serena.extra_bins must be a list of non-empty strings")

    def test_an_npm_tool_needs_runs_with(self) -> None:
        self.with_field("gitnexus", "runs_with", None)
        self.check_message("tools.gitnexus.runs_with must be one of native, node")

    def test_a_node_tool_needs_an_entry(self) -> None:
        self.with_field("gitnexus", "entry", None)
        self.check_message("tools.gitnexus.entry must be a non-empty string when runs_with is node")

    def test_runs_with_is_only_for_npm(self) -> None:
        self.with_field("cq", "runs_with", "native")
        self.check_message("tools.cq.runs_with is only for tools whose installer is npm")

    def test_a_uv_tool_needs_a_python_version(self) -> None:
        self.with_field("serena", "python", None)
        self.check_message("tools.serena.python must be a non-empty string when installer is uv")

    def test_every_command_stops_before_any_download_or_install(self) -> None:
        self.with_field("gitnexus", "installer", "pip")
        for command in ("install", "configure", "doctor", "run"):
            with (
                self.subTest(command=command),
                patch.object(setup, "download") as download,
                patch.object(setup, "run") as run,
                patch.object(setup.subprocess, "run") as subprocess_run,
            ):
                arguments = ["--command", command, *(["--tool", "serena"] * (command == "run"))]
                status, text = self.main(*arguments)
                self.assertEqual(status, 1)
                self.assertIn(
                    "agent-dependencies.json tools.gitnexus.installer must be one of "
                    "uv, npm, github-release",
                    text,
                )
                for fake in (download, run, subprocess_run):
                    fake.assert_not_called()

    def test_the_error_names_the_task_the_user_ran(self) -> None:
        self.with_field("gitnexus", "installer", "pip")
        _, text = self.main("--command", "install")
        self.assertEqual(
            text,
            "tools:install: agent-dependencies.json tools.gitnexus.installer must be one of "
            "uv, npm, github-release\n",
        )

    def test_an_unknown_tool_lists_the_valid_names(self) -> None:
        status, text = self.main("--command", "run", "--tool", "nope", "--", "--version")
        self.assertEqual(status, 1)
        self.assertEqual(text, f"tools:run: unknown tool 'nope'; choose one of {TOOL_NAMES}\n")


class UvInstallerTests(TempManifestCase):
    def test_install_command(self) -> None:
        serena = real_spec("serena")
        (self.root / "agent-tools/serena-constraints.txt").write_text("a==1\n", encoding="utf-8")
        calls: list[list[str]] = []
        with (
            patch.object(setup.shutil, "which", return_value="/bin/uv"),
            patch.object(setup, "run", side_effect=lambda command, **_: calls.append(command)),
        ):
            setup.INSTALLERS["uv"].install("serena", serena)
        self.assertEqual(
            calls,
            [
                [
                    "/bin/uv",
                    "tool",
                    "install",
                    "--python",
                    "3.13",
                    "--force",
                    "serena-agent==1.7.0",
                    "--overrides",
                    str(self.tools / "serena-overrides.txt"),
                    "--constraints",
                    str(self.root / "agent-tools/serena-constraints.txt"),
                ]
            ],
        )
        self.assertEqual((self.tools / "serena-constraints.txt").read_text(), "a==1\n")
        overrides = (self.tools / "serena-overrides.txt").read_text(encoding="utf-8")
        self.assertIn("urllib3==2.8.0\n", overrides)

    def test_install_without_a_constraints_file_adds_no_constraints(self) -> None:
        calls: list[list[str]] = []
        with (
            patch.object(setup.shutil, "which", return_value="/bin/uv"),
            patch.object(setup, "run", side_effect=lambda command, **_: calls.append(command)),
        ):
            setup.INSTALLERS["uv"].install("serena", real_spec("serena"))
        self.assertNotIn("--constraints", calls[0])

    def test_install_needs_uv(self) -> None:
        with (
            patch.object(setup.shutil, "which", return_value=None),
            self.assertRaisesRegex(RuntimeError, "uv is missing"),
        ):
            setup.INSTALLERS["uv"].install("serena", real_spec("serena"))

    def test_command_is_the_bin_in_the_tools_folder(self) -> None:
        with patch.object(setup.os, "name", "posix"):
            command = setup.INSTALLERS["uv"].command("serena", real_spec("serena"))
        self.assertEqual(command, [str(self.tools / "bin/serena")])

    def test_version_comes_from_the_package_metadata_in_its_environment(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: Any) -> str:
            calls.append(command)
            return "1.7.0"

        with (
            patch.object(setup.os, "name", "posix"),
            patch.object(setup, "run", side_effect=fake_run),
        ):
            version = setup.INSTALLERS["uv"].installed_version("serena", real_spec("serena"))
        self.assertEqual(version, "1.7.0")
        self.assertEqual(calls[0][0], str(self.tools / "uv/serena-agent/bin/python"))
        self.assertEqual(
            calls[0][1:],
            ["-c", "import importlib.metadata; print(importlib.metadata.version('serena-agent'))"],
        )

    def test_latest_version_comes_from_pypi(self) -> None:
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return json.dumps({"info": {"version": "1.8.0"}}).encode()

        with patch.object(setup, "download", side_effect=fake_download):
            latest = setup.INSTALLERS["uv"].latest_version("serena", real_spec("serena"))
        self.assertEqual((latest, urls), ("1.8.0", ["https://pypi.org/pypi/serena-agent/json"]))

    def test_stale_when_the_constraints_file_differs(self) -> None:
        serena = real_spec("serena")
        (self.root / "agent-tools/serena-constraints.txt").write_text("a==1\n", encoding="utf-8")
        with patch.object(setup, "override_versions", return_value=serena["dependency_overrides"]):
            self.assertTrue(setup.INSTALLERS["uv"].is_stale("serena", serena))
            (self.tools / "serena-constraints.txt").write_text("a==1\n", encoding="utf-8")
            self.assertFalse(setup.INSTALLERS["uv"].is_stale("serena", serena))

    def test_stale_when_an_override_is_not_installed(self) -> None:
        with patch.object(setup, "override_versions", return_value={}):
            self.assertTrue(setup.INSTALLERS["uv"].is_stale("serena", real_spec("serena")))
            with self.assertRaisesRegex(RuntimeError, "Serena's reviewed security"):
                setup.INSTALLERS["uv"].check_installed("serena", real_spec("serena"))


class NpmInstallerTests(TempManifestCase):
    def test_install_runs_npm_ci_on_the_committed_lock(self) -> None:
        dependencies = setup.npm_package()["dependencies"]
        lock = {"packages": {"": {"dependencies": dependencies}}}
        (self.root / "agent-tools/package-lock.json").write_text(json.dumps(lock))
        calls: list[list[str]] = []
        with (
            patch.object(setup, "npm_command", return_value=["/node", "/npm-cli.js"]),
            patch.object(setup, "run", side_effect=lambda command, **_: calls.append(command)),
        ):
            setup.INSTALLERS["npm"].install("gitnexus", real_spec("gitnexus"))
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
        (self.root / "agent-tools/package-lock.json").write_text(
            json.dumps({"packages": {"": {"dependencies": {}}}})
        )
        with self.assertRaisesRegex(RuntimeError, "npm lock does not match"):
            setup.INSTALLERS["npm"].install("gitnexus", real_spec("gitnexus"))

    def test_version_comes_from_dash_dash_version(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: Any) -> str:
            calls.append(command)
            return "ast-grep 0.50.0"

        with (
            patch.object(setup.os, "name", "posix"),
            patch.object(setup, "run", side_effect=fake_run),
        ):
            version = setup.INSTALLERS["npm"].installed_version("ast-grep", real_spec("ast-grep"))
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
            latest = setup.INSTALLERS["npm"].latest_version("ast-grep", real_spec("ast-grep"))
        self.assertEqual(
            (latest, urls), ("0.51.0", ["https://registry.npmjs.org/@ast-grep/cli/latest"])
        )


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

    def test_install_downloads_checks_and_writes_the_executable(self) -> None:
        payload = self.archive("cq_Linux_x86_64/cq", b"#!/bin/sh\n")
        cq = real_spec("cq")
        cq["checksums"]["cq_Linux_x86_64.tar.gz"] = hashlib.sha256(payload).hexdigest()
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return payload

        with self.linux_x86_64(), patch.object(setup, "download", side_effect=fake_download):
            setup.INSTALLERS["github-release"].install("cq", cq)
        self.assertEqual(urls, [f"{cq['release']}/cq_Linux_x86_64.tar.gz"])
        installed = self.tools / "bin/cq"
        self.assertEqual(installed.read_bytes(), b"#!/bin/sh\n")
        self.assertTrue(installed.stat().st_mode & 0o100)

    def test_install_refuses_a_download_that_does_not_match_its_checksum(self) -> None:
        cq = real_spec("cq")
        with (
            self.linux_x86_64(),
            patch.object(setup, "download", return_value=b"tampered"),
            self.assertRaisesRegex(RuntimeError, "cq release checksum mismatch"),
        ):
            setup.INSTALLERS["github-release"].install("cq", cq)
        self.assertFalse((self.tools / "bin/cq").exists())

    def test_install_needs_exactly_one_executable_in_the_archive(self) -> None:
        payload = self.archive("README", b"text")
        cq = real_spec("cq")
        cq["checksums"]["cq_Linux_x86_64.tar.gz"] = hashlib.sha256(payload).hexdigest()
        with (
            self.linux_x86_64(),
            patch.object(setup, "download", return_value=payload),
            self.assertRaisesRegex(RuntimeError, "must contain exactly one executable"),
        ):
            setup.INSTALLERS["github-release"].install("cq", cq)

    def test_version_comes_from_dash_dash_version(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: Any) -> str:
            calls.append(command)
            return "cq version 0.18.0"

        with (
            patch.object(setup.os, "name", "posix"),
            patch.object(setup, "run", side_effect=fake_run),
        ):
            version = setup.INSTALLERS["github-release"].installed_version("cq", real_spec("cq"))
        self.assertEqual(version, "0.18.0")
        self.assertEqual(calls, [[str(self.tools / "bin/cq"), "--version"]])

    def test_latest_version_is_the_newest_stable_release_with_the_pinned_tag_style(self) -> None:
        releases = [
            {"tag_name": "cli/v0.20.0-rc1", "prerelease": True},
            {"tag_name": "plugin/v9.0.0", "prerelease": False},
            {"tag_name": "cli/v0.19.0", "prerelease": False},
            {"tag_name": "cli/v0.18.0", "prerelease": False},
        ]
        urls: list[str] = []

        def fake_download(url: str) -> bytes:
            urls.append(url)
            return json.dumps(releases).encode()

        with patch.object(setup, "download", side_effect=fake_download):
            latest = setup.INSTALLERS["github-release"].latest_version("cq", real_spec("cq"))
        self.assertEqual(latest, "0.19.0")
        self.assertEqual(urls, ["https://api.github.com/repos/mozilla-ai/cq/releases?per_page=30"])


if __name__ == "__main__":
    unittest.main()
