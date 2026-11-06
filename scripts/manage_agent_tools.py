#!/usr/bin/env python3
"""Install pinned agent tools and configure their user-level integrations."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import tomllib
import urllib.parse
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]


TOOLS = ROOT / ".tools" / "agent-tools"


BACKUP_RUNS_KEPT = 60


JSONC_PENDING = "would merge JSONC after tools:install; source validation pending"


MANAGED_SETTINGS_ERROR = "requires remote managed settings"


REMOTE_SERVER_FIELDS = (
    "url",
    "headers",
    "headersHelper",
    "http_headers",
    "env_http_headers",
    "bearer_token_env_var",
    "oauth",
)


MANIFEST = ROOT / "agent-dependencies.json"

# A tool entry in the manifest (agent-dependencies.json), checked by `manifest()`.
ToolSpec = dict[str, Any]

INSTALLER_TYPES = ("uv", "npm", "github-release")
NPM_RUNNERS = ("native", "node")


class ManifestError(ValueError):
    """An entry in agent-dependencies.json is invalid; the message names the entry and field."""


def manifest_error(name: str, field: str, rule: str) -> ManifestError:
    return ManifestError(f"agent-dependencies.json tools.{name}.{field} {rule}")


def is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def check_npm_fields(name: str, spec: ToolSpec) -> None:
    if spec["installer"] != "npm":
        for field in ("runs_with", "entry"):
            if field in spec:
                raise manifest_error(name, field, "is only for tools whose installer is npm")
        return
    if spec.get("runs_with") not in NPM_RUNNERS:
        raise manifest_error(name, "runs_with", "must be one of " + ", ".join(NPM_RUNNERS))
    if spec["runs_with"] == "node" and not is_text(spec.get("entry")):
        raise manifest_error(name, "entry", "must be a non-empty string when runs_with is node")


def check_tool_entry(name: str, entry: object) -> None:
    if not isinstance(entry, dict):
        raise ManifestError(f"agent-dependencies.json tools.{name} must be an object")
    spec = cast("ToolSpec", entry)
    if spec.get("installer") not in INSTALLER_TYPES:
        raise manifest_error(name, "installer", "must be one of " + ", ".join(INSTALLER_TYPES))
    if not is_text(spec.get("bin")):
        raise manifest_error(name, "bin", "must be a non-empty string")
    extra = spec.get("extra_bins", [])
    if not isinstance(extra, list) or not all(
        is_text(item) for item in cast("list[object]", extra)
    ):
        raise manifest_error(name, "extra_bins", "must be a list of non-empty strings")
    if spec["installer"] == "uv" and not is_text(spec.get("python")):
        raise manifest_error(name, "python", "must be a non-empty string when installer is uv")
    check_npm_fields(name, spec)


def manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported agent-dependencies.json schema")
    tools = data.get("tools")
    if not isinstance(tools, dict):
        raise ManifestError("agent-dependencies.json tools must be an object")
    for name, entry in cast("dict[str, object]", tools).items():
        check_tool_entry(name, entry)
    return data


def tool_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        UV_TOOL_DIR=str(TOOLS / "uv"),
        UV_TOOL_BIN_DIR=str(TOOLS / "bin"),
        UV_PYTHON_INSTALL_DIR=str(ROOT / ".tools" / "python"),
        UV_CACHE_DIR=str(ROOT / ".tools" / "uv-cache"),
        npm_config_cache=str(TOOLS / "npm-cache"),
        # The committed lock must resolve from the public registry only.
        npm_config_userconfig=os.devnull,
        npm_config_registry="https://registry.npmjs.org/",
        GITNEXUS_STORAGE_ROOT=str(TOOLS / "gitnexus-indexes"),
        CQ_ADDR="",
        # Embeddings are off, so skip onnxruntime's unverified CUDA download,
        # and keep npm installs from sending Scarf install telemetry.
        ONNXRUNTIME_NODE_INSTALL="skip",
        SCARF_ANALYTICS="false",
    )
    env.pop("GITNEXUS_STORAGE_PATH", None)
    paths = [str(TOOLS / "bin")]
    receipt = TOOLS / "runtime.json"
    runtime: dict[str, Any] = (
        json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
    )
    for name in ("node", "uv", "task"):
        executable = runtime.get(name) or shutil.which(name)
        if executable:
            paths.append(str(Path(executable).parent))
    if os.name == "nt":
        paths.append(str(Path(env.get("SystemRoot", "C:/Windows")) / "System32"))
    if not shutil.which("dotnet"):
        bases = [
            Path.home() / "AppData/Local/mise/installs/dotnet",
            Path.home() / ".local/share/mise/installs/dotnet",
        ]
        candidates = sorted(
            (
                p
                for base in bases
                for p in base.glob("*/dotnet*")
                if p.is_file() and p.name in {"dotnet", "dotnet.exe"}
            ),
            reverse=True,
        )
        if candidates:
            paths.append(str(candidates[0].parent))
    # uv's isolated interpreter prepends a temporary Scripts/bin directory.
    # Host configuration must not retain that short-lived invocation path.
    inherited = env.get("LLMS_ORIGINAL_PATH", env.get("PATH", ""))
    env["PATH"] = os.pathsep.join(stable_paths(paths + inherited.split(os.pathsep)))
    return env


def stable_paths(entries: list[str]) -> list[str]:
    """Keep absolute, existing, non-temporary directories once each, in order."""
    temporary_roots = [
        os.path.normcase(os.path.realpath(root))
        for root in (tempfile.gettempdir(), Path.home() / ".codex/tmp")
    ]
    seen: set[str] = set()
    kept: list[str] = []
    for entry in entries:
        key = os.path.normcase(os.path.normpath(entry))
        real = os.path.normcase(os.path.realpath(entry)) if entry else ""
        if (
            not entry
            or key in seen
            or not os.path.isabs(entry)
            or not os.path.isdir(entry)
            or any(real == root or real.startswith(root + os.sep) for root in temporary_roots)
        ):
            continue
        kept.append(entry)
        seen.add(key)
    return kept


def run(
    args: list[str],
    *,
    timeout: int = 600,
    cwd: Path | None = None,
    input_text: str | None = None,
) -> str:
    result = subprocess.run(  # noqa: S603 - args are fixed tool commands built by this script
        args,
        check=False,
        cwd=cwd,
        env=tool_env(),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(
            f"{Path(args[0]).name} exited {result.returncode}: {result.stdout[-5000:]}"
        )
    return result.stdout.strip()


def node_command() -> str:
    receipt = TOOLS / "runtime.json"
    if receipt.is_file():
        recorded = json.loads(receipt.read_text(encoding="utf-8")).get("node")
        if recorded and Path(recorded).is_file():
            return recorded
    command = shutil.which("node")
    if not command:
        raise RuntimeError("Node is missing. Run ./bootstrap.sh deps:install first.")
    return command


def npm_command() -> list[str]:
    node = Path(node_command())
    candidates = [
        node.parent / "node_modules/npm/bin/npm-cli.js",
        node.parent.parent / "lib/node_modules/npm/bin/npm-cli.js",
    ]
    for path in candidates:
        if path.is_file():
            return [str(node), str(path)]
    raise RuntimeError("The selected Node installation does not contain npm.")


# ---- Tools: each manifest entry names its installer, and that installer's handler
# builds the install command, the command that runs the tool, and both version lookups.


class Installer(ABC):
    """What differs between the ways a tool can be installed."""

    # One install covers every tool of this type, so one run installs them all.
    shared_install = False

    @abstractmethod
    def command(self, name: str, spec: ToolSpec) -> list[str]:
        """Return the command that runs the tool."""

    @abstractmethod
    def install(self, name: str, spec: ToolSpec) -> None:
        """Install the pinned version."""

    @abstractmethod
    def latest_version(self, name: str, spec: ToolSpec) -> str:
        """Look up the newest published version (network)."""

    def installed_version(self, name: str, spec: ToolSpec) -> str | None:
        """Ask the tool for its version; None when the output has no version."""
        output = run([*self.command(name, spec), "--version"], timeout=30)
        match = re.search(r"\d+\.\d+\.\d+", output)
        return match.group() if match else None

    def is_stale(self, name: str, spec: ToolSpec) -> bool:
        """Tell whether the right version is installed but something it depends on is not."""
        return False

    def check_installed(self, name: str, spec: ToolSpec) -> None:  # noqa: B027 - most installers check nothing
        """Raise when an install left something other than the pins in place."""


def bin_path(binary: str) -> Path:
    return TOOLS / "bin" / (binary + (".exe" if os.name == "nt" else ""))


def uv_python(spec: ToolSpec) -> Path:
    """Return the Python of the tool's own environment, which `uv tool install` makes."""
    return (
        TOOLS / "uv" / spec["package"] / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )


def required_uv() -> str:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is missing. Run ./bootstrap.sh deps:install first.")
    return uv


def constraints_source(name: str) -> Path:
    """Return the committed constraints file that `tools:lock` writes for a uv tool."""
    return ROOT / f"agent-tools/{name}-constraints.txt"


def overrides_file(name: str, spec: ToolSpec) -> Path:
    path = TOOLS / f"{name}-overrides.txt"
    update_file(
        path,
        "".join(
            f"{package}=={version}\n"
            for package, version in spec.get("dependency_overrides", {}).items()
        ),
    )
    return path


def constraints_current(name: str) -> bool:
    installed = TOOLS / f"{name}-constraints.txt"
    source = constraints_source(name)
    return not source.is_file() or (
        installed.is_file() and installed.read_bytes() == source.read_bytes()
    )


def override_versions(spec: ToolSpec) -> dict[str, str]:
    """Read the versions of the `dependency_overrides` packages now installed."""
    packages = spec.get("dependency_overrides", {})
    if not packages:
        return {}
    code = (
        "import importlib.metadata as m, json; print(json.dumps({p:m.version(p) for p in "
        + repr(list(packages))
        + "}))"
    )
    try:
        return json.loads(run([str(uv_python(spec)), "-c", code], timeout=20))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return {}


def overrides_installed(spec: ToolSpec) -> bool:
    return override_versions(spec) == spec.get("dependency_overrides", {})


class UvInstaller(Installer):
    """A Python package installed into its own environment with `uv tool install`."""

    def command(self, name: str, spec: ToolSpec) -> list[str]:
        return [str(bin_path(spec["bin"]))]

    def installed_version(self, name: str, spec: ToolSpec) -> str | None:
        return run(
            [
                str(uv_python(spec)),
                "-c",
                "import importlib.metadata; "
                f"print(importlib.metadata.version('{spec['package']}'))",
            ],
            timeout=20,
        )

    def is_stale(self, name: str, spec: ToolSpec) -> bool:
        return not overrides_installed(spec) or not constraints_current(name)

    def check_installed(self, name: str, spec: ToolSpec) -> None:
        if not overrides_installed(spec):
            raise RuntimeError(
                f"{name.capitalize()}'s reviewed security dependency overrides were not installed"
            )

    def install(self, name: str, spec: ToolSpec) -> None:
        command = [
            required_uv(),
            "tool",
            "install",
            "--python",
            spec["python"],
            "--force",
            f"{spec['package']}=={spec['version']}",
            "--overrides",
            str(overrides_file(name, spec)),
        ]
        source = constraints_source(name)
        if source.is_file():
            command.extend(["--constraints", str(source)])
        run(command)
        if source.is_file():
            update_file(TOOLS / f"{name}-constraints.txt", source.read_text(encoding="utf-8"))

    def latest_version(self, name: str, spec: ToolSpec) -> str:
        return json.loads(download(f"https://pypi.org/pypi/{spec['package']}/json"))["info"][
            "version"
        ]


def lock_uv_tool(name: str, spec: ToolSpec) -> dict[str, Any]:
    """Resolve a uv tool's whole dependency tree once, for every platform."""
    uv = required_uv()
    source = constraints_source(name)
    with tempfile.TemporaryDirectory(prefix=f"llms-{name}-lock-") as workspace:
        output = Path(workspace) / "constraints.txt"
        run(
            [
                uv,
                "pip",
                "compile",
                "-",
                "--universal",
                "--python-version",
                spec["python"],
                "--overrides",
                str(overrides_file(name, spec)),
                "--no-header",
                "--no-annotate",
                "--output-file",
                str(output),
            ],
            input_text=f"{spec['package']}=={spec['version']}\n",
        )
        action = update_file(source, output.read_text(encoding="utf-8"))
    return {"lockfile": str(source), "action": action}


def tools_with(installer: str) -> dict[str, ToolSpec]:
    return {
        name: spec for name, spec in manifest()["tools"].items() if spec["installer"] == installer
    }


def npm_package() -> dict[str, Any]:
    return {
        "name": "llms-agent-tools",
        "version": "0.0.0",
        "private": True,
        "dependencies": {spec["package"]: spec["version"] for spec in tools_with("npm").values()},
    }


def npm_lock_current() -> bool:
    source = ROOT / "agent-tools/package-lock.json"
    installed = TOOLS / "npm/package-lock.json"
    package = TOOLS / "npm/package.json"
    return (
        source.is_file()
        and installed.is_file()
        and package.is_file()
        and source.read_bytes() == installed.read_bytes()
        and json.loads(package.read_text(encoding="utf-8")) == npm_package()
    )


def install_npm_tools() -> None:
    source = ROOT / "agent-tools/package-lock.json"
    lock = json.loads(source.read_text(encoding="utf-8"))
    if lock.get("packages", {}).get("", {}).get("dependencies") != npm_package()["dependencies"]:
        raise RuntimeError("npm lock does not match the declared tool pins; run task tools:lock")
    update_file(TOOLS / "npm/package.json", json.dumps(npm_package(), indent=2) + "\n")
    update_file(TOOLS / "npm/package-lock.json", source.read_text(encoding="utf-8"))
    run(
        [*npm_command(), "ci", "--prefix", str(TOOLS / "npm"), "--no-audit", "--no-fund"],
        timeout=1200,
    )


def lock_npm_tools() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="llms-npm-lock-") as workspace:
        path = Path(workspace)
        (path / "package.json").write_text(json.dumps(npm_package()), encoding="utf-8")
        destination = ROOT / "agent-tools/package-lock.json"
        if destination.exists():
            shutil.copyfile(destination, path / "package-lock.json")
        run(
            [
                *npm_command(),
                "install",
                "--package-lock-only",
                "--ignore-scripts",
                "--prefix",
                str(path),
                "--no-audit",
                "--no-fund",
            ]
        )
        action = update_file(destination, (path / "package-lock.json").read_text(encoding="utf-8"))
    return {"lockfile": str(destination), "action": action}


class NpmInstaller(Installer):
    """A package in the shared npm folder, installed all at once from the committed lock."""

    shared_install = True

    def command(self, name: str, spec: ToolSpec) -> list[str]:
        package_root = TOOLS / "npm/node_modules" / spec["package"]
        metadata_path = package_root / "package.json"
        if metadata_path.is_file():
            bins = json.loads(metadata_path.read_text(encoding="utf-8"))["bin"]
            entry = bins if isinstance(bins, str) else bins[spec["bin"]]
        else:
            # The manifest's entry point lets a fresh-machine preview describe absent tools.
            entry = spec["entry"] if spec["runs_with"] == "node" else spec["bin"]
        path = package_root / entry
        if spec["runs_with"] == "native":
            return [str(path.with_suffix(".exe") if os.name == "nt" else path)]
        return [node_command(), str(path)]

    def is_stale(self, name: str, spec: ToolSpec) -> bool:
        return not npm_lock_current()

    def install(self, name: str, spec: ToolSpec) -> None:
        install_npm_tools()

    def latest_version(self, name: str, spec: ToolSpec) -> str:
        return json.loads(download(f"https://registry.npmjs.org/{spec['package']}/latest"))[
            "version"
        ]


RELEASE_SYSTEMS = {"Windows": "Windows", "Linux": "Linux", "Darwin": "Darwin"}
RELEASE_MACHINES = {
    "amd64": "x86_64",
    "x86_64": "x86_64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


def release_executable(payload: bytes, system: str, binary: str, name: str) -> bytes:
    """Return the one executable inside a release archive (.zip on Windows, .tar.gz elsewhere)."""
    if system == "Windows":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files = [member for member in archive.namelist() if Path(member).name == binary]
            if len(files) != 1:
                raise RuntimeError(f"{name} archive must contain exactly one executable")
            return archive.read(files[0])
    with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
        members = [
            member
            for member in tar.getmembers()
            if member.isfile() and Path(member.name).name == binary
        ]
        if len(members) != 1:
            raise RuntimeError(f"{name} archive must contain exactly one executable")
        stream = tar.extractfile(members[0])
        if stream is None:
            raise RuntimeError(f"{name} archive executable could not be read")
        return stream.read()


class GithubReleaseInstaller(Installer):
    """A release archive downloaded from GitHub and checked against the manifest's SHA-256."""

    def command(self, name: str, spec: ToolSpec) -> list[str]:
        return [str(bin_path(spec["bin"]))]

    def install(self, name: str, spec: ToolSpec) -> None:
        system = RELEASE_SYSTEMS[platform.system()]
        machine = RELEASE_MACHINES[platform.machine().lower()]
        asset = f"{spec['bin']}_{system}_{machine}.{'zip' if system == 'Windows' else 'tar.gz'}"
        payload = download(f"{spec['release']}/{asset}")
        if hashlib.sha256(payload).hexdigest() != spec["checksums"][asset]:
            raise RuntimeError(f"{name} release checksum mismatch: {asset}")
        binary = spec["bin"] + (".exe" if system == "Windows" else "")
        executable = release_executable(payload, system, binary, name)
        destination = TOOLS / "bin" / binary
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged = destination.with_suffix(".new")
        staged.write_bytes(executable)
        staged.chmod(0o755)
        staged.replace(destination)

    def latest_version(self, name: str, spec: ToolSpec) -> str:
        """Find the newest stable release, whose tag is the pinned tag with its version swapped."""
        source: str = spec["source"]
        repository = urllib.parse.urlparse(source).path.strip("/")
        tag = spec["release"].split("/download/", 1)[1]
        prefix = tag.removesuffix(spec["version"])
        releases = json.loads(
            download(f"https://api.github.com/repos/{repository}/releases?per_page=30")
        )
        return next(
            release["tag_name"].removeprefix(prefix)
            for release in releases
            if release["tag_name"].startswith(prefix) and not release["prerelease"]
        )


INSTALLERS: dict[str, Installer] = {
    "uv": UvInstaller(),
    "npm": NpmInstaller(),
    "github-release": GithubReleaseInstaller(),
}


def installer_for(name: str) -> tuple[ToolSpec, Installer]:
    spec = manifest()["tools"][name]
    return spec, INSTALLERS[spec["installer"]]


def tool_command(name: str) -> list[str]:
    spec, installer = installer_for(name)
    return installer.command(name, spec)


def installed_version(name: str) -> str | None:
    try:
        spec, installer = installer_for(name)
        return installer.installed_version(name, spec)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError):
        return None


def latest_version(name: str) -> str:
    spec, installer = installer_for(name)
    return installer.latest_version(name, spec)


def download(url: str) -> bytes:
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError(f"refusing to download a non-https URL: {url}")
    request = urllib.request.Request(  # noqa: S310 - https is checked above
        url, headers={"User-Agent": "llms-bootstrap"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - https is checked above
        return response.read()


def record_runtime() -> None:
    """Write the runtime receipt: where Node, uv and the real Task are."""
    if not shutil.which("node"):
        raise RuntimeError("Node is missing. Run ./bootstrap.sh deps:install first.")
    TOOLS.mkdir(parents=True, exist_ok=True)
    runtime = {name: shutil.which(name) for name in ("node", "uv", "task")}
    # .tools/bin/task forwards to this repo's bootstrap; agents get the real Task.
    wrappers = ROOT / ".tools/bin"
    if runtime["task"] and Path(runtime["task"]).parent == wrappers:
        mise = wrappers / ("mise.exe" if os.name == "nt" else "mise")
        runtime["task"] = run([str(mise), "which", "task"], timeout=30)
    update_file(TOOLS / "runtime.json", json.dumps(runtime, indent=2) + "\n")


def install_tool(name: str, spec: ToolSpec, installed_types: set[str]) -> dict[str, Any]:
    """Install one tool if its version or its dependencies are not the pinned ones."""
    installer = INSTALLERS[spec["installer"]]
    expected = spec["version"]
    needs_install = installed_version(name) != expected or installer.is_stale(name, spec)
    if needs_install:
        installer.install(name, spec)
        installed_types.add(spec["installer"])
    actual = installed_version(name)
    if actual != expected:
        raise RuntimeError(f"{name}: expected {expected}, installed version is {actual!r}")
    installer.check_installed(name, spec)
    covered = installer.shared_install and spec["installer"] in installed_types
    return {
        "tool": name,
        "version": actual,
        "action": "installed" if needs_install or covered else "unchanged",
        "command": tool_command(name),
    }


def install() -> dict[str, Any]:
    record_runtime()
    installed_types: set[str] = set()
    return {
        "tools": [
            install_tool(name, spec, installed_types) for name, spec in manifest()["tools"].items()
        ]
    }


def private_permissions(path: Path, *, copy_from: Path | None = None) -> None:
    if os.name == "nt":
        powershell = (
            Path(os.environ.get("SystemRoot", "C:/Windows"))  # noqa: SIM112 - Windows spells this variable SystemRoot
            / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        command = [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/set_private_permissions.ps1"),
            "-Path",
            str(path),
        ]
        if copy_from is not None:
            command.extend(["-CopyFrom", str(copy_from)])
        run(command, timeout=20)
    elif copy_from is not None:
        # Keep the owner's choice, but never let others rewrite agent config.
        path.chmod(stat.S_IMODE(copy_from.stat().st_mode) & ~0o022)
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def update_file(
    path: Path,
    text: str,
    *,
    dry_run: bool = False,
    expected_digest: str | None = None,
) -> str:
    # Write through a symlink (e.g. a dotfiles checkout) instead of replacing it.
    path = path.resolve() if path.is_symlink() else path
    old = path.read_text(encoding="utf-8") if path.exists() else None
    digest = hashlib.sha256(old.encode("utf-8")).hexdigest() if old is not None else ""
    if expected_digest is not None and digest != expected_digest:
        raise RuntimeError(f"Configuration changed during rendering: {path}")
    if old == text:
        if not dry_run and os.name != "nt" and path.stat().st_mode & 0o022:
            private_permissions(path, copy_from=path)
        return "unchanged"
    if dry_run:
        return "would update" if old is not None else "would create"
    if old is not None:
        backup_configuration(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".llms-", dir=path.parent)
    staged = Path(name)
    try:
        # Restrict a new Windows file before writing, even in a shared folder.
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            private_permissions(staged)
            output.write(text)
        if path.exists():
            private_permissions(staged, copy_from=path)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != old:
            raise RuntimeError(f"Configuration changed during update: {path}")
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
    return "updated" if old is not None else "created"


def backup_configuration(path: Path) -> None:
    if not path.is_file():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns()}"
    backup = TOOLS / "config-backups" / stamp / path.name
    backup.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    for directory in (backup.parent, backup.parent.parent):
        private_permissions(directory)
    with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
        output.write(path.read_bytes())
    # Backups can hold credentials; keep enough to undo recent runs, no more.
    stamps = sorted(backup.parent.parent.iterdir(), reverse=True)
    for stale in stamps[BACKUP_RUNS_KEPT:]:
        shutil.rmtree(stale, ignore_errors=True)


def jsonc_pending(path: Path) -> bool:
    """Tell whether the file is JSONC and the pinned JSONC parser is not installed yet."""
    return path.suffix == ".jsonc" and not (TOOLS / "npm/package.json").is_file()


def write_json_config(path: Path, data: dict[str, Any], *, dry_run: bool) -> str:
    text = (
        jsonc_document(path, data)["text"]
        if path.suffix == ".jsonc"
        else json.dumps(data, indent=2) + "\n"
    )
    return update_file(path, text, dry_run=dry_run)


def serena_home() -> Path:
    selected = os.environ.get("SERENA_HOME", "").strip()
    return Path(selected or Path.home() / ".serena").resolve()


def serena_configuration(*, apply: bool = False, dry_run: bool = False) -> dict[str, Any]:
    serena = manifest()["tools"]["serena"]
    settings = serena["config"]
    python = uv_python(serena)
    if not python.is_file():
        return {
            "action": "requires tools:install",
            "configured": False,
            "settings": settings,
        }
    result = json.loads(
        run(
            [
                str(python),
                str(ROOT / "scripts/render_serena_config.py"),
                json.dumps(settings),
                str(serena_home() / "serena_config.yml"),
            ],
            timeout=30,
        )
    )
    text = result.pop("text")
    original_digest = result.pop("original_digest")
    path = Path(result["config"])
    result["configured"] = path.is_file() and result["current"] == settings
    if apply:
        result["action"] = update_file(path, text, dry_run=dry_run, expected_digest=original_digest)
        result["configured"] = result["configured"] or not dry_run
    return result


def servers() -> dict[str, Any]:
    environment = tool_env()
    launch_env = {
        key: environment[key] for key in ("PATH", "UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR")
    }
    configured = {
        "serena": {
            "command": tool_command("serena")[0],
            "args": [
                "start-mcp-server",
                "--project-from-cwd",
                "--context",
                "",  # host_servers sets the host's own value
                "--open-web-dashboard",
                "false",
            ],
            "env": {**launch_env, "SERENA_HOME": str(serena_home())},
            "startup_timeout_sec": 60,
        },
        "gitnexus": {
            "command": node_command(),
            "args": [
                str(ROOT / "scripts/run_gitnexus.mjs"),
                *tool_command("gitnexus")[1:],
                "mcp",
            ],
            "env": {
                **launch_env,
                "GITNEXUS_STORAGE_ROOT": environment["GITNEXUS_STORAGE_ROOT"],
            },
        },
        "cq": {
            "command": tool_command("cq")[0],
            "args": ["mcp"],
            "env": {**launch_env, "CQ_ADDR": ""},
        },
    }
    if not manifest()["tools"]["gitnexus"].get("integration_enabled", True):
        del configured["gitnexus"]
    return configured


class ConfigWriter(Protocol):
    def __call__(
        self, adapter: HostAdapter, servers: dict[str, Any], /, *, dry_run: bool = False
    ) -> str: ...


class EnvironmentStep(Protocol):
    def __call__(self, *, dry_run: bool = False) -> str: ...


class StandardProfile(NamedTuple):
    """A host whose profile folder an environment variable can move."""

    is_standard: Callable[[], bool]
    startup_error: str  # uses {directory}
    doctor_problem: str  # uses {directory}


def no_servers(adapter: HostAdapter, path: Path) -> dict[str, Any]:
    return {}


class HostAdapter(NamedTuple):
    """Everything setup needs to know about one host.

    `configure`, `preview`, `host_problems` and the helpers under them take host
    details only from here. To add a host, define one adapter and add it to
    `ADAPTERS`. Functions held in a field take the adapter as their first
    argument, so they read the adapter's own settings (paths aside).
    `scripts/install_skills.py` keeps its own host list; `doctor` skips the
    skills check for a host it does not know and says so.
    """

    name: str  # also the host's command-line client and cq's `--target`
    # The file setup reports and checks: the MCP servers file, or for Pi its instructions file.
    config_path: Callable[[], Path]
    # Write the managed servers to the config file; return the action taken.
    write_config: ConfigWriter
    # Name each way the host's setup differs from what `configure` writes.
    check_config: Callable[[HostAdapter, Path], list[str]]
    serena_client: str  # `serena setup <client>` and `serena-hooks --client=<client>`
    gitnexus_client: str  # `gitnexus setup -c <client>`
    serena_context: str  # Serena's `--context` for this host
    # Files other than the config and hooks files that configure backs up first.
    backup_paths: Callable[[], list[Path]] = list
    # Other files an upstream installer might write this host's servers to.
    extra_server_files: Callable[[], set[Path]] = set
    # Folders that can also hold this host's skills; empty: only the installer's folder.
    skill_roots: Callable[[], list[Path]] = list
    manages_servers: bool = True  # False: no MCP servers, only a CLI mapping
    servers_key: str = "mcpServers"  # the config section that holds the servers
    env_key: str = "env"  # a server's environment, under that name
    command_is_list: bool = False  # server command and args are one list
    read_servers: Callable[[HostAdapter, Path], dict[str, Any]] = no_servers
    keeps_startup_timeout: bool = False
    dropped_servers: Callable[[], tuple[str, ...]] = tuple
    hooks_file: str | None = None  # under the home folder; None: no hooks file
    hook_exec_form: bool = False  # hooks hold `command` and `args`, not one command line
    serena_hooks: tuple[tuple[str, str, str], ...] = ()  # (event, matcher, action)
    runs_serena_setup: bool = False
    # Set: serena and cq setup need the host's own client; this is the limitation to report.
    client_required_limitation: str | None = None
    # Set: a "requires remote managed settings" failure is reported, not raised; uses {error}.
    managed_settings_limitation: str | None = None
    profile: StandardProfile | None = None
    environment_step: EnvironmentStep | None = None
    migrate_config: Callable[[HostAdapter, list[str]], None] | None = None
    note: str = "MCP servers configured; client connection and hook trust require verification"

    def server_files(self) -> set[Path]:
        return {self.config_path(), *self.extra_server_files()}


def adapter_for(host: str) -> HostAdapter:
    try:
        return ADAPTERS[host]
    except KeyError:
        raise ValueError(f"Unknown host: {host}") from None


def selected_hosts(target: str) -> tuple[str, ...]:
    return tuple(ADAPTERS) if target == "all" else (target,)


def host_servers(adapter: HostAdapter) -> dict[str, Any]:
    selected = servers()
    for name in adapter.dropped_servers():
        selected.pop(name, None)
    if not adapter.keeps_startup_timeout:
        for server in selected.values():
            server.pop("startup_timeout_sec", None)
    arguments = selected["serena"]["args"]
    arguments[arguments.index("--context") + 1] = adapter.serena_context
    return selected


def managed_servers(adapter: HostAdapter) -> dict[str, Any]:
    return host_servers(adapter) if adapter.manages_servers else {}


def existing_server(adapter: HostAdapter, name: str) -> bool:
    path = adapter.config_path()
    return path.exists() and name in adapter.read_servers(adapter, path)


def hook_files(adapter: HostAdapter) -> tuple[Path, Path]:
    """Return the host's hooks file and the folder-relative GitNexus hook script."""
    if adapter.hooks_file is None:
        raise ValueError(f"{adapter.name} has no hooks file")
    hooks = Path.home() / adapter.hooks_file
    return hooks, hooks.parent / "hooks/gitnexus/gitnexus-hook.cjs"


# PowerShell treats all of these as a single quote inside a '...' string.
# Keep in step with quotePowerShell in quote_powershell.mjs.
POWERSHELL_SINGLE_QUOTES = re.compile("['\u2018\u2019\u201a\u201b]")


def powershell_quote(value: str) -> str:
    """Return value as one PowerShell single-quoted string, doubling every quote character."""
    return "'" + POWERSHELL_SINGLE_QUOTES.sub(lambda match: match.group() * 2, value) + "'"


def gitnexus_hook_launch(adapter: HostAdapter) -> dict[str, Any]:
    _, hook = hook_files(adapter)
    arguments = [
        Path(node_command()).as_posix(),
        (ROOT / "scripts/run_gitnexus_hook.mjs").as_posix(),
        (TOOLS / "gitnexus-indexes").as_posix(),
        hook.as_posix(),
        Path(tool_command("gitnexus")[1]).as_posix(),
    ]
    if adapter.hook_exec_form:
        return {"command": arguments[0], "args": arguments[1:]}
    script = "& " + " ".join(powershell_quote(arg) for arg in arguments)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    powershell = (
        Path(os.environ.get("SystemRoot", "C:/Windows"))  # noqa: SIM112 - Windows spells this variable SystemRoot
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    ).as_posix()
    return {
        "command": shlex.join(arguments),
        "commandWindows": (
            f"{powershell} -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded}"
        ),
    }


def gitnexus_owned_hooks(data: dict[str, Any], adapter: HostAdapter) -> list[dict[str, Any]]:
    _, hook = hook_files(adapter)
    owned: list[dict[str, Any]] = []

    def collect(item: object) -> None:
        if isinstance(item, dict):
            value = cast("dict[str, Any]", item)
            command = value.get("command", "")
            arguments = value.get("args", [])
            references: list[Any] = (
                [command, *arguments] if isinstance(arguments, list) else [command]
            )
            if any(
                isinstance(part, str)
                and any(
                    needle in part.replace("\\", "/")
                    for needle in (hook.as_posix(), shlex.quote(hook.as_posix()))
                )
                for part in references
            ):
                owned.append(value)
            for child in value.values():
                collect(child)
        elif isinstance(item, list):
            for child in cast("list[object]", item):
                collect(child)

    collect(data.get("hooks", {}))
    return owned


def configure_gitnexus_hooks(adapter: HostAdapter) -> None:
    if adapter.hooks_file is None:
        return
    path, _ = hook_files(adapter)
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    for hook in gitnexus_owned_hooks(data, adapter):
        for key in ("command", "args", "commandWindows"):
            hook.pop(key, None)
        hook.update(gitnexus_hook_launch(adapter))
    # Upstream recognizes shell-form commands only; Claude exec form would
    # otherwise accumulate a second registration on every native setup pass.
    owned = {id(hook) for hook in gitnexus_owned_hooks(data, adapter)}
    for event, groups in data.get("hooks", {}).items():
        seen: set[str] = set()
        for group in groups:
            retained: list[dict[str, Any]] = []
            for hook in group.get("hooks", []):
                matcher = group.get("matcher", "")
                if id(hook) in owned:
                    # The search augment reopens the graph database on every
                    # Grep/Glob/Bash call (~0.9 s, ~700 MB); agents can query
                    # the GitNexus MCP server instead. Keep the stale-index check.
                    if event == "PreToolUse" or matcher in seen:
                        continue
                    seen.add(matcher)
                retained.append(hook)
            group["hooks"] = retained
        data["hooks"][event] = [group for group in groups if group.get("hooks")]
    update_file(path, json.dumps(data, indent=2) + "\n")


def serena_hooks_binary() -> str:
    """Return the hook executable Serena installs: the first of its `extra_bins`."""
    extra = manifest()["tools"].get("serena", {}).get("extra_bins", [])
    return extra[0] if extra else "serena-hooks"


def serena_hook(adapter: HostAdapter, action: str) -> dict[str, Any]:
    binary = str(bin_path(serena_hooks_binary()))
    arguments = [action, "--client=" + adapter.serena_client]
    hook: dict[str, Any] = {"type": "command", "timeout": 3 if action == "cleanup" else 5}
    if adapter.hook_exec_form:
        hook.update(command=binary, args=arguments)
    else:
        join = subprocess.list2cmdline if os.name == "nt" else shlex.join
        hook["command"] = join([binary, *arguments])
    return hook


def configure_serena_hooks(adapter: HostAdapter, *, dry_run: bool = False) -> str:
    """Remind agents to use Serena; without hooks they rarely load its tools."""
    if not adapter.serena_hooks:
        return "not applicable"
    path, _ = hook_files(adapter)
    data: dict[str, Any] = (
        json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
    )
    hooks = data.setdefault("hooks", {})
    for event in list(hooks):
        for group in hooks[event]:
            group["hooks"] = [
                hook
                for hook in group.get("hooks", [])
                if "serena-hooks" not in " ".join([hook.get("command", ""), *hook.get("args", [])])
            ]
        hooks[event] = [group for group in hooks[event] if group.get("hooks")]
        if not hooks[event]:
            del hooks[event]
    for event, matcher, action in adapter.serena_hooks:
        group: dict[str, Any] = {"hooks": [serena_hook(adapter, action)]}
        if matcher:
            group = {"matcher": matcher, **group}
        hooks.setdefault(event, []).append(group)
    return update_file(path, json.dumps(data, indent=2) + "\n", dry_run=dry_run)


def server_command_problems(
    adapter: HostAdapter, path: Path, name: str, wanted: dict[str, Any], actual: dict[str, Any]
) -> list[str]:
    """Report how a server entry's connection, command or on/off state differs from the plan."""
    reasons: list[str] = []
    if any(key in actual for key in REMOTE_SERVER_FIELDS):
        reasons.append(f"{name} server in {path} has remote connection fields")
    if (adapter.command_is_list and actual.get("type") != "local") or (
        not adapter.command_is_list and actual.get("type") not in {None, "stdio"}
    ):
        reasons.append(f"{name} server in {path} is not a local command")
    wanted_command = (
        [wanted["command"], *wanted["args"]] if adapter.command_is_list else wanted["command"]
    )
    if actual.get("command") != wanted_command or (
        not adapter.command_is_list and actual.get("args") != wanted["args"]
    ):
        reasons.append(f"{name} server in {path} runs a different command")
    if actual.get("enabled") is False or actual.get("disabled") is True:
        reasons.append(f"{name} server in {path} is turned off")
    return reasons


def server_environment_problems(
    adapter: HostAdapter, path: Path, name: str, wanted: dict[str, Any], actual: dict[str, Any]
) -> list[str]:
    """Report how a server entry's environment values or PATH differ from the plan."""
    reasons: list[str] = []
    environment = actual.get(adapter.env_key, {})
    if any(
        environment.get(key) != value
        for key, value in wanted.get("env", {}).items()
        if key != "PATH"
    ):
        reasons.append(f"{name} server in {path} has different environment values")
    actual_paths = {
        os.path.normcase(os.path.normpath(value))
        for value in environment.get("PATH", "").split(os.pathsep)
        if value
    }
    if not required_tool_paths().issubset(actual_paths):
        reasons.append(f"{name} server PATH in {path} lacks the pinned tool folders")
    return reasons


def gitnexus_hook_problems(adapter: HostAdapter) -> list[str]:
    hooks_path, hook_script = hook_files(adapter)
    hook_data: dict[str, Any] = (
        json.loads(hooks_path.read_text(encoding="utf-8-sig")) if hooks_path.is_file() else {}
    )
    owned = gitnexus_owned_hooks(hook_data, adapter)
    launch = gitnexus_hook_launch(adapter)
    if (
        not hook_script.is_file()
        or not owned
        or any(any(hook.get(k) != v for k, v in launch.items()) for hook in owned)
    ):
        return [f"GitNexus hooks in {hooks_path} are missing or stale"]
    return []


def server_problems(adapter: HostAdapter, path: Path) -> list[str]:
    reasons: list[str] = []
    container = adapter.read_servers(adapter, path)
    expected = host_servers(adapter)
    for name, wanted in expected.items():
        actual = container.get(name)
        if actual is None:
            reasons.append(f"{name} server missing from {path}")
            continue
        reasons.extend(server_command_problems(adapter, path, name, wanted, actual))
        reasons.extend(server_environment_problems(adapter, path, name, wanted, actual))
    if adapter.serena_hooks and configure_serena_hooks(adapter, dry_run=True) != "unchanged":
        reasons.append(f"Serena hooks in {hook_files(adapter)[0]} are missing or stale")
    if "gitnexus" in expected and adapter.hooks_file is not None:
        reasons.extend(gitnexus_hook_problems(adapter))
    return reasons


# ---- Codex: TOML `mcp_servers` in ~/.codex/config.toml


def codex_config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"


def standard_codex_profile() -> bool:
    return codex_config_path().parent.resolve() == (Path.home() / ".codex").resolve()


def codex_backup_paths() -> list[Path]:
    return [codex_config_path().parent / "AGENTS.md"]


def codex_skill_roots() -> list[Path]:
    return [Path.home() / ".agents/skills", Path.home() / ".codex/skills"]


def read_codex_servers(adapter: HostAdapter, path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8")).get(adapter.servers_key, {})


def merge_codex(adapter: HostAdapter, servers: dict[str, Any], *, dry_run: bool = False) -> str:
    import tomlkit  # noqa: PLC0415 - only Codex files need tomlkit, so import it when used

    path = adapter.config_path()
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    document = tomlkit.parse(text)
    configured = document.setdefault(adapter.servers_key, tomlkit.table())
    for name, server in servers.items():
        existing = configured.setdefault(name, tomlkit.table())
        for key in (*REMOTE_SERVER_FIELDS, "type"):
            existing.pop(key, None)
        for key, value in server.items():
            if key == "env":
                existing.setdefault(adapter.env_key, tomlkit.table()).update(value)
            else:
                existing[key] = value
    agents = document.setdefault("agents", tomlkit.table())
    if "max_concurrent_threads_per_session" not in agents and "max_threads" not in agents:
        agents["max_concurrent_threads_per_session"] = 3
    result = tomlkit.dumps(document)
    tomllib.loads(result)
    return update_file(path, result, dry_run=dry_run)


CODEX = HostAdapter(
    name="codex",
    config_path=codex_config_path,
    write_config=merge_codex,
    check_config=server_problems,
    serena_client="codex",
    gitnexus_client="codex",
    serena_context="codex",
    backup_paths=codex_backup_paths,
    skill_roots=codex_skill_roots,
    servers_key="mcp_servers",
    read_servers=read_codex_servers,
    keeps_startup_timeout=True,
    hooks_file=".codex/hooks.json",
    serena_hooks=(
        ("SessionStart", "startup|resume", "activate"),
        ("PreToolUse", "Bash", "remind"),
        ("SessionEnd", "", "cleanup"),
    ),
    runs_serena_setup=True,
    profile=StandardProfile(
        is_standard=standard_codex_profile,
        startup_error=(
            "CODEX_HOME is set to {directory}; agents:configure supports only "
            "the default ~/.codex. Unset CODEX_HOME and rerun, or use skills:install, "
            "which supports a custom CODEX_HOME."
        ),
        doctor_problem="CODEX_HOME is {directory}; agents:configure supports only ~/.codex",
    ),
)


# ---- Claude: JSON `mcpServers` in ~/.claude.json, hooks and env in ~/.claude/settings.json


CLAUDE_SETTINGS_FILE = ".claude/settings.json"  # under the home folder


def claude_settings_path() -> Path:
    return Path.home() / CLAUDE_SETTINGS_FILE


def claude_plugin_enabled() -> bool:
    path = claude_settings_path()
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return any(
        value is True and name.split("@", 1)[0] == "cq"
        for name, value in settings.get("enabledPlugins", {}).items()
    )


def configure_claude_environment(*, dry_run: bool = False) -> str:
    path = claude_settings_path()
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    environment = settings.setdefault("env", {})
    # Rebuild rather than extend the previous value, so stale entries drop out.
    environment.update(PATH=tool_env()["PATH"], CQ_ADDR="")
    return update_file(path, json.dumps(settings, indent=2) + "\n", dry_run=dry_run)


def claude_config_path() -> Path:
    return Path.home() / ".claude.json"


def read_claude_servers(adapter: HostAdapter, path: Path) -> dict[str, Any]:
    return read_host_json(path).get(adapter.servers_key, {})


def merge_mcp_servers_json(
    adapter: HostAdapter, servers: dict[str, Any], *, dry_run: bool = False
) -> str:
    """Write stdio servers as command, args and environment."""
    path = adapter.config_path()
    if dry_run and jsonc_pending(path):
        return JSONC_PENDING
    data = read_host_json(path) if path.exists() else {}
    for name, server in servers.items():
        existing = data.setdefault(adapter.servers_key, {}).setdefault(name, {})
        for key in REMOTE_SERVER_FIELDS:
            existing.pop(key, None)
        environment = {**existing.get(adapter.env_key, {}), **server.get("env", {})}
        entry = {adapter.env_key if key == "env" else key: value for key, value in server.items()}
        entry[adapter.env_key] = environment
        existing.update(entry, type="stdio")
    return write_json_config(path, data, dry_run=dry_run)


def claude_dropped_servers() -> tuple[str, ...]:
    return ("cq",) if claude_plugin_enabled() else ()


def migrate_claude_cq_entry(adapter: HostAdapter, limitations: list[str]) -> None:
    """Move this script's old cq server entry into Claude's settings for the cq plugin."""
    path = adapter.config_path()
    if not (claude_plugin_enabled() and path.exists()):
        return
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    manual = data.get(adapter.servers_key, {}).get("cq", {})
    if manual.get("command") == tool_command("cq")[0]:
        settings_path = claude_settings_path()
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        environment = settings.setdefault("env", {})
        # Global env reaches every Claude process; move only the
        # values this script wrote, and report anything else.
        for key, value in manual.get(adapter.env_key, {}).items():
            if key in {"UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR"}:
                environment.setdefault(key, value)
            elif key not in {"PATH", "CQ_ADDR"}:
                limitations.append(
                    f"dropped {key} from the old cq server entry; set it again where cq needs it"
                )
        update_file(settings_path, json.dumps(settings, indent=2) + "\n")
        del data[adapter.servers_key]["cq"]
        update_file(path, json.dumps(data, indent=2) + "\n")
    elif manual:
        raise RuntimeError(
            "An existing unmanaged Claude cq server conflicts with the cq plugin; "
            "preserve its settings and resolve that entry before configuring"
        )


def claude_problems(adapter: HostAdapter, path: Path) -> list[str]:
    reasons = server_problems(adapter, path)
    if claude_plugin_enabled():
        settings = json.loads(claude_settings_path().read_text(encoding="utf-8"))
        if "cq" in adapter.read_servers(adapter, path):
            reasons.append(f"an old cq server entry in {path} duplicates the cq plugin")
        if settings.get("env", {}).get("CQ_ADDR") != "":
            reasons.append(
                "CQ_ADDR in ~/.claude/settings.json is not empty, so cq may sync remotely"
            )
    return reasons


CLAUDE = HostAdapter(
    name="claude",
    config_path=claude_config_path,
    write_config=merge_mcp_servers_json,
    check_config=claude_problems,
    serena_client="claude-code",
    gitnexus_client="claude",
    serena_context="claude-code",
    read_servers=read_claude_servers,
    dropped_servers=claude_dropped_servers,
    hooks_file=CLAUDE_SETTINGS_FILE,
    hook_exec_form=True,
    serena_hooks=(
        ("SessionStart", "startup|resume|clear|compact", "activate"),
        ("PreToolUse", "", "remind"),
        ("SessionEnd", "", "cleanup"),
    ),
    runs_serena_setup=True,
    client_required_limitation=(
        "cq's Claude plugin installation requires Claude CLI; "
        "rerun agents:configure after installing that client"
    ),
    managed_settings_limitation=(
        "cq plugin setup unavailable; rerun agents:configure after claude auth login: {error}"
    ),
    environment_step=configure_claude_environment,
    migrate_config=migrate_claude_cq_entry,
)


# ---- Pi: no MCP servers; cq's CLI mapping in ~/.pi/agent/AGENTS.md and settings.json


def pi_settings_path() -> Path:
    return Path.home() / ".pi/agent/settings.json"


def pi_config_path() -> Path:
    return Path.home() / ".pi/agent/AGENTS.md"


def configure_pi(*, dry_run: bool = False) -> str:
    settings_path = pi_settings_path()
    settings: dict[str, Any] = (
        json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    )
    prefix = settings.get("shellCommandPrefix", "").rstrip()
    local_prefix = "export CQ_ADDR='';"
    if not prefix.endswith(local_prefix):
        settings["shellCommandPrefix"] = (
            prefix + (" " if prefix.endswith(";") else "; ") if prefix else ""
        ) + local_prefix
    return update_file(settings_path, json.dumps(settings, indent=2) + "\n", dry_run=dry_run)


def write_pi_mapping(
    _adapter: HostAdapter, _servers: dict[str, Any], *, dry_run: bool = False
) -> str:
    """Write cq's CLI mapping, not an invented MCP adapter; Pi takes no servers."""
    action = configure_pi(dry_run=dry_run)
    return action if dry_run else "configured CLI mapping"


def pi_problems(adapter: HostAdapter, path: Path) -> list[str]:
    reasons: list[str] = []
    text = path.read_text(encoding="utf-8")
    settings_path = pi_settings_path()
    settings: dict[str, Any] = (
        json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    )
    cq_block = re.search(r"<!-- cq:start -->(.*?)<!-- cq:end -->", text, re.S)
    if not (cq_block and f"The cq binary is: `{tool_command('cq')[0]}`." in cq_block.group(1)):
        reasons.append(f"cq instructions in {path} are missing or point elsewhere")
    if not settings.get("shellCommandPrefix", "").rstrip().endswith("export CQ_ADDR='';"):
        reasons.append(f"{settings_path} does not keep cq local (CQ_ADDR)")
    return reasons


PI = HostAdapter(
    name="pi",
    config_path=pi_config_path,
    write_config=write_pi_mapping,
    check_config=pi_problems,
    serena_client="pi",
    gitnexus_client="pi",
    serena_context="ide",
    backup_paths=lambda: [pi_settings_path()],
    manages_servers=False,
    note="cq CLI mapping; other CLIs available through Task",
)


# ---- OpenCode: JSON or JSONC `mcp` (v1) or `mcp.servers` (v2) under ~/.config/opencode

# The files OpenCode reads, in the order it prefers them.
OPENCODE_FILES = ("opencode.jsonc", "opencode.json", "config.json")


def opencode_directory() -> Path:
    return Path.home() / ".config/opencode"


def opencode_config_path() -> Path:
    directory = opencode_directory()
    return next(
        (directory / name for name in OPENCODE_FILES if (directory / name).is_file()),
        directory / OPENCODE_FILES[1],
    )


def opencode_server_files() -> set[Path]:
    return {opencode_directory() / name for name in OPENCODE_FILES}


def opencode_backup_paths() -> list[Path]:
    return [opencode_directory() / "AGENTS.md"]


def read_opencode_servers(adapter: HostAdapter, path: Path) -> dict[str, Any]:
    mcp = read_host_json(path).get(adapter.servers_key, {})
    return mcp.get("servers", mcp)


def merge_opencode_servers(
    adapter: HostAdapter, servers: dict[str, Any], *, dry_run: bool = False
) -> str:
    """Write local servers under `mcp` (v1) or `mcp.servers` (v2), whichever OpenCode reads."""
    path = adapter.config_path()
    if dry_run and jsonc_pending(path):
        return JSONC_PENDING
    data = read_host_json(path) if path.exists() else {}
    # OpenCode 2 uses mcp.servers; keep v1 when an installed host requires it.
    binary = shutil.which(adapter.name)
    version = run([binary, "--version"], timeout=15) if binary else "2"
    mcp: dict[str, Any] = data.setdefault(adapter.servers_key, {})
    if version.startswith("1."):
        container = mcp
    else:
        container = mcp.setdefault("servers", {})
        for name, entry in list(mcp.items()):
            if (
                name != "servers"
                and isinstance(entry, dict)
                and cast("dict[str, Any]", entry).get("type") in {"local", "remote"}
            ):
                if name not in container:
                    container[name] = entry
                del mcp[name]
    for name, server in servers.items():
        existing = container.setdefault(name, {})
        for key in REMOTE_SERVER_FIELDS:
            existing.pop(key, None)
        environment = {**existing.get(adapter.env_key, {}), **server.get("env", {})}
        existing.update(
            {
                "type": "local",
                "command": [server["command"], *server["args"]],
                adapter.env_key: environment,
            }
        )
    return write_json_config(path, data, dry_run=dry_run)


OPENCODE = HostAdapter(
    name="opencode",
    config_path=opencode_config_path,
    write_config=merge_opencode_servers,
    check_config=server_problems,
    serena_client="opencode",
    gitnexus_client="opencode",
    serena_context="ide",
    backup_paths=opencode_backup_paths,
    extra_server_files=opencode_server_files,
    servers_key="mcp",
    env_key="environment",
    command_is_list=True,
    read_servers=read_opencode_servers,
)

# The host list: its order is the order setup configures hosts in.
ADAPTERS: dict[str, HostAdapter] = {
    adapter.name: adapter for adapter in (CODEX, CLAUDE, PI, OPENCODE)
}


def require_standard_profiles(target: str) -> None:
    adapters = [adapter_for(host) for host in selected_hosts(target)]
    for adapter in adapters:
        profile = adapter.profile
        if profile and not profile.is_standard():
            raise RuntimeError(profile.startup_error.format(directory=adapter.config_path().parent))
    for adapter in adapters:
        path = adapter.config_path()
        if not adapter.manages_servers or not path.is_file():
            continue
        if jsonc_pending(path):
            continue  # Preview reports that JSONC validation awaits installation.
        entry = adapter.read_servers(adapter, path).get("serena", {})
        environment = entry.get(adapter.env_key, {})
        override = environment.get("SERENA_HOME", "").strip()
        if override and (
            not Path(override).is_absolute() or Path(override).resolve() != serena_home()
        ):
            raise RuntimeError(
                f"{adapter.name} has a different Serena home. Set SERENA_HOME to its existing "
                "absolute home before configuring, or deliberately remove that host override."
            )


def jsonc_document(
    path: Path, desired: dict[str, Any] | None = None, *, text: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": path.read_text(encoding="utf-8-sig") if text is None else text
    }
    if desired is not None:
        payload["desired"] = desired
    return json.loads(
        run(
            [
                node_command(),
                str(ROOT / "scripts/update_jsonc.mjs"),
                str(TOOLS / "npm/package.json"),
            ],
            input_text=json.dumps(payload),
        )
    )


def read_host_json(path: Path, text: str | None = None) -> dict[str, Any]:
    if path.suffix == ".jsonc":
        return jsonc_document(path, text=text)["data"]
    return json.loads(path.read_text(encoding="utf-8-sig") if text is None else text)


def snapshot_configs(paths: set[Path]) -> dict[Path, str | None]:
    return {path: path.read_text(encoding="utf-8") if path.is_file() else None for path in paths}


def restore_servers(snapshot: dict[Path, str | None], adapter: HostAdapter) -> None:
    """Undo an upstream installer's MCP server edits, keeping all other changes.

    Upstream installers replace server entries this script manages, and some
    write a config file the host does not read. Only the server section is put
    back, onto the current file, so edits made meanwhile by a running host
    survive. A file the installer created that holds nothing else is removed.
    The host's adapter names the server section.
    """
    import tomlkit  # noqa: PLC0415 - only Codex files need tomlkit, so import it when used

    for path, original in snapshot.items():
        if not path.is_file():
            continue
        current = path.read_text(encoding="utf-8")
        if current == original:
            continue
        digest = hashlib.sha256(current.encode("utf-8")).hexdigest()
        key = adapter.servers_key
        document: Any
        previous: Any
        remaining: set[str]
        if path.suffix == ".toml":
            document = tomlkit.parse(current)
            previous = tomlkit.parse(original or "")
            if key in previous:
                document[key] = previous[key]
            else:
                document.pop(key, None)
            remaining = set(document)
            text = tomlkit.dumps(document)
        else:
            document = read_host_json(path, current)
            previous = read_host_json(path, original) if original else {}
            if key in previous:
                document[key] = previous[key]
            else:
                document.pop(key, None)
            remaining = set(document)
            text = (
                jsonc_document(path, document)["text"]
                if path.suffix == ".jsonc"
                else json.dumps(document, indent=2) + "\n"
            )
        if original is None and remaining <= {"$schema"}:
            backup_configuration(path)
            path.unlink()
        else:
            update_file(path, text, expected_digest=digest)


def required_tool_paths() -> set[str]:
    receipt = TOOLS / "runtime.json"
    runtime: dict[str, Any] = (
        json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
    )
    paths = [
        TOOLS / "bin",
        *(Path(value).parent for value in runtime.values() if value),
    ]
    return {os.path.normcase(os.path.normpath(str(path))) for path in paths}


def preview(target: str) -> dict[str, Any]:
    require_standard_profiles(target)
    planned: list[dict[str, Any]] = []
    for host in selected_hosts(target):
        adapter = adapter_for(host)
        path = adapter.config_path()
        expected = managed_servers(adapter)
        action = adapter.write_config(adapter, expected, dry_run=True)
        environment_action = (
            adapter.environment_step(dry_run=True) if adapter.environment_step else None
        )
        planned.append(
            {
                "host": host,
                "config": str(path),
                "action": action,
                "managed_servers": list(expected),
                "environment_action": environment_action,
                "serena_hooks": configure_serena_hooks(adapter, dry_run=True),
                "upstream_setup": (
                    "would run supported upstream installers; "
                    "native plugin changes are host-dependent"
                ),
            }
        )
    return {
        "serena": serena_configuration(apply=True, dry_run=True),
        "hosts": planned,
        "writes": False,
    }


def skill_health(target: str) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "llms_install_skills", ROOT / "scripts/install_skills.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("scripts/install_skills.py could not be loaded")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    source = ROOT / "skills"
    dependencies = installer.dependency_manifest(source)
    validation = installer.validate_source(source, manifest=dependencies)
    sources = {name: source / name for name in installer.MANAGED_SKILLS}
    sources.update(
        {name: installer.external_cache() / name for name in installer.external_specs(dependencies)}
    )
    known = installer.resolve_targets(installer.parse_args([]))
    wanted = selected_hosts(target)
    targets = {host: path for host, path in known.items() if host in wanted}
    skipped = [
        f"{host}: skills not checked; scripts/install_skills.py does not know this host"
        for host in wanted
        if host not in known
    ]
    problems = list(validation["errors"])
    hosts: list[dict[str, Any]] = []
    for host, path in targets.items():
        missing = [
            name
            for name, src in sources.items()
            if installer.digest_path(path / name) != installer.digest_path(src)
            or not (path / name / "SKILL.md").is_file()
        ]
        roots = adapter_for(host).skill_roots() or [path]
        conflicts = [
            name
            for name, src in sources.items()
            for root in roots
            if root != path
            and (root / name).is_dir()
            and installer.digest_path(root / name) != installer.digest_path(src)
        ]
        if missing:
            problems.append(
                f"{host}: skills missing or changed: {', '.join(missing)}; "
                f"run ./bootstrap.sh skills:install TARGET={host}"
            )
        if conflicts:
            problems.append(
                f"{host}: other copies of {', '.join(sorted(set(conflicts)))} differ from the "
                "installed skills and may load instead; remove them or rerun skills:install"
            )
        hosts.append(
            {
                "host": host,
                "directory": str(path),
                "expected_count": len(sources),
                "digest_verified": not missing,
                "conflicts": sorted(set(conflicts)),
                "runtime_discovery_verified": False,
            }
        )
    result = {"hosts": hosts, "source_valid": validation["valid"], "problems": problems}
    if skipped:
        result["skipped"] = skipped
    return result


def require_pinned_tools() -> None:
    missing = [
        name
        for name, spec in manifest()["tools"].items()
        if installed_version(name) != spec["version"]
    ]
    if missing:
        raise RuntimeError(
            "Pinned tools are missing: "
            + ", ".join(missing)
            + ". Run ./bootstrap.sh tools:install first."
        )


def run_with_server_restore(
    adapter: HostAdapter, command: list[str], server_paths: set[Path]
) -> str:
    """Run an upstream installer, then put back the MCP servers it rewrote."""
    snapshot = snapshot_configs(server_paths)
    try:
        return run(command, timeout=90)
    finally:
        restore_servers(snapshot, adapter)


def back_up_host_files(adapter: HostAdapter) -> list[Path]:
    paths = [adapter.config_path(), *adapter.backup_paths()]
    if adapter.hooks_file is not None:
        paths.append(hook_files(adapter)[0])
    for path in paths:
        backup_configuration(path)
    return paths


def register_serena(adapter: HostAdapter, upstream: list[str], limitations: list[str]) -> None:
    """Register an absent Serena server through upstream; preserve existing entries."""
    if not adapter.runs_serena_setup:
        return
    if adapter.client_required_limitation is not None and not shutil.which(adapter.name):
        return
    if existing_server(adapter, "serena"):
        return
    try:
        upstream.append(run([*tool_command("serena"), "setup", adapter.serena_client], timeout=90))
    except RuntimeError as error:
        if "not found or not functional" not in str(error) and not (
            adapter.managed_settings_limitation is not None and MANAGED_SETTINGS_ERROR in str(error)
        ):
            raise
        limitations.append(
            f"serena setup {adapter.serena_client} failed, so this script wrote Serena's MCP "
            f"entry itself: {error}"
        )


def back_up_server_files(adapter: HostAdapter, backed_up: list[Path]) -> set[Path]:
    # Upstream installers own their skills and hooks but rewrite MCP server
    # entries; the managed merge below writes those.
    server_paths = adapter.server_files()
    for path in server_paths - set(backed_up):
        backup_configuration(path)
    return server_paths


def set_up_gitnexus(adapter: HostAdapter, server_paths: set[Path], upstream: list[str]) -> None:
    if not (
        adapter.manages_servers and manifest()["tools"]["gitnexus"].get("integration_enabled", True)
    ):
        return
    upstream.append(
        run_with_server_restore(
            adapter,
            [*tool_command("gitnexus"), "setup", "-c", adapter.gitnexus_client],
            server_paths,
        )
    )
    configure_gitnexus_hooks(adapter)


def run_cq_install(
    adapter: HostAdapter, server_paths: set[Path], upstream: list[str], limitations: list[str]
) -> None:
    """Use cq's maintained skill/instruction installer.

    Claude's plugin route needs the Claude CLI; other hosts can be configured
    without their binaries.
    """
    if adapter.client_required_limitation is not None and not shutil.which(adapter.name):
        limitations.append(adapter.client_required_limitation)
        return
    try:
        upstream.append(
            run_with_server_restore(
                adapter,
                [*tool_command("cq"), "install", "--target", adapter.name],
                server_paths if adapter.manages_servers else set(),
            )
        )
    except RuntimeError as error:
        if adapter.managed_settings_limitation is None or MANAGED_SETTINGS_ERROR not in str(error):
            raise
        limitations.append(adapter.managed_settings_limitation.format(error=error))


def write_managed_config(adapter: HostAdapter, limitations: list[str]) -> tuple[Path, str]:
    selected = managed_servers(adapter)
    if adapter.migrate_config:
        adapter.migrate_config(adapter, limitations)
    return adapter.config_path(), adapter.write_config(adapter, selected)


def configure_host(adapter: HostAdapter) -> dict[str, Any]:
    upstream: list[str] = []
    limitations: list[str] = []
    backed_up = back_up_host_files(adapter)
    if adapter.environment_step:
        adapter.environment_step()
    register_serena(adapter, upstream, limitations)
    server_paths = back_up_server_files(adapter, backed_up)
    set_up_gitnexus(adapter, server_paths, upstream)
    run_cq_install(adapter, server_paths, upstream, limitations)
    hooks_action = configure_serena_hooks(adapter)
    path, action = write_managed_config(adapter, limitations)
    return {
        "host": adapter.name,
        "config": str(path),
        "action": action,
        "serena_hooks": hooks_action,
        "client_available": bool(shutil.which(adapter.name)),
        "upstream_installers": bool(upstream),
        "limitations": limitations,
        "note": adapter.note,
    }


def configure(target: str) -> dict[str, Any]:
    require_standard_profiles(target)
    require_pinned_tools()
    serena = serena_configuration(apply=True)
    results = [configure_host(adapter_for(host)) for host in selected_hosts(target)]
    return {
        "serena": serena,
        "hosts": results,
        "disabled_integrations": [
            name
            for name, spec in manifest()["tools"].items()
            if spec.get("integration_enabled") is False
        ],
    }


def host_problems(host: str) -> list[str]:
    """Name each way a host's managed configuration differs from what configure writes."""
    adapter = adapter_for(host)
    path = adapter.config_path()
    if adapter.profile and not adapter.profile.is_standard():
        return [adapter.profile.doctor_problem.format(directory=path.parent)]
    if not path.is_file():
        return [f"{path} not found"]
    return adapter.check_config(adapter, path)


def doctor(target: str) -> dict[str, Any]:
    tools = [
        {
            "tool": name,
            "expected": spec["version"],
            "installed": installed_version(name),
        }
        for name, spec in manifest()["tools"].items()
    ]
    problems = [
        f"{t['tool']}: installed {t['installed'] or 'none'}, expected {t['expected']}; "
        "run ./bootstrap.sh tools:install"
        for t in tools
        if t["installed"] != t["expected"]
    ]
    problems.extend(
        f"{name.capitalize()}'s pinned security patches (dependency_overrides in "
        "agent-dependencies.json) are not installed; run ./bootstrap.sh tools:install"
        for name, spec in manifest()["tools"].items()
        if spec.get("installer") == "uv" and not overrides_installed(spec)
    )
    hosts: list[dict[str, Any]] = []
    for host in selected_hosts(target):
        reasons = host_problems(host)
        problems.extend(
            f"{host}: {reason}; run ./bootstrap.sh agents:configure TARGET={host}"
            for reason in reasons
        )
        hosts.append(
            {
                "host": host,
                "configured": not reasons,
                "reasons": reasons,
                "client_available": bool(shutil.which(host)),
                "connection_verified": False,
            }
        )
    skills = skill_health(target)
    problems.extend(skills["problems"])
    serena = serena_configuration()
    if not serena["configured"]:
        problems.append(
            "Serena dashboard settings differ from agent-dependencies.json; "
            "run ./bootstrap.sh agents:configure"
        )
    return {
        "tools": tools,
        "serena": serena,
        "hosts": hosts,
        "skills": skills,
        "problems": problems,
        "healthy": not problems,
        "disabled_integrations": [
            name
            for name, spec in manifest()["tools"].items()
            if spec.get("integration_enabled") is False
        ],
        "note": "doctor only reads files. Restart each agent, approve new hooks if asked, "
        "and try a query to confirm the tools connect.",
    }


def print_hosts(result: dict[str, Any]) -> None:
    for host in result.get("hosts", []):
        if isinstance(host, str):
            print(f"host: {host}")
        else:
            state = host.get("action", "configured" if host.get("configured") else "NOT configured")
            print(f"{host['host']}: {state}")
            for limitation in host.get("limitations", []):
                print(f"  skipped (needs follow-up): {limitation}")
    for host in result.get("skills", {}).get("hosts", []):
        state = "all up to date" if host["digest_verified"] else "some missing or changed"
        print(f"{host['host']} skills: {host['expected_count']} expected, {state}")


def print_tools(result: dict[str, Any]) -> None:
    if result.get("serena"):
        serena = result["serena"]
        print("Serena preferences: " + serena.get("action", f"configured={serena['configured']}"))
    for tool in result.get("tools", []):
        selected = tool.get("version", tool.get("pinned", tool.get("expected")))
        observed = tool.get("installed", tool.get("version"))
        update = f"; available {tool['latest']}" if "latest" in tool else ""
        print(f"{tool['tool']}: selected {selected}; installed {observed}{update}")


def emit(result: dict[str, Any], output: str) -> None:
    if output == "json":
        print(json.dumps(result, indent=2))
        return
    if result.get("error"):
        print(f"{result['command']}: {result['error']}")
        return
    for lock in result.get("locks", []):
        print(f"lock: {lock['action']}; {lock['lockfile']}")
    print_tools(result)
    print_hosts(result)
    for problem in result.get("problems", []):
        print(f"problem: {problem}")
    if result.get("disabled_integrations"):
        print("Disabled integrations: " + ", ".join(result["disabled_integrations"]))
    if result.get("note"):
        print(result["note"])


COMMANDS = ("install", "configure", "doctor", "preview", "versions", "check", "run", "lock")

# The task that runs each command, for errors that name the task the user ran.
TASK_NAMES = {
    "install": "tools:install",
    "configure": "agents:configure",
    "doctor": "doctor",
    "preview": "install:dry-run",
    "versions": "deps:versions",
    "check": "deps:check",
    "run": "tools:run",
    "lock": "tools:lock",
}


class UnknownToolError(ValueError):
    """`--tool` names a tool that is not in agent-dependencies.json."""


def require_known_tool(name: str) -> None:
    tools = manifest()["tools"]
    if name not in tools:
        raise UnknownToolError(f"unknown tool '{name}'; choose one of {', '.join(tools)}")


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", choices=COMMANDS, required=True)
    parser.add_argument("--target", choices=("all", *ADAPTERS), default="all")
    parser.add_argument("--output", choices=("json", "text"), default="text")
    # The valid names come from agent-dependencies.json, so main() checks them.
    parser.add_argument("--tool")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == "run" and not args.tool:
        parser.error("--command run requires --tool")
    return args


def run_tool(name: str, extra_arguments: list[str]) -> int:
    """Run one pinned tool in the caller's directory and return its exit status."""
    spec = manifest()["tools"][name]
    if spec.get("integration_enabled") is False:
        raise RuntimeError(
            f"{name} is turned off "
            "(integration_enabled: false in agent-dependencies.json); "
            f"its license is at {spec.get('license_url')}"
        )
    if installed_version(name) != spec["version"]:
        raise RuntimeError(
            f"The pinned {name} is not installed. Run ./bootstrap.sh tools:install first."
        )
    arguments = extra_arguments[1:] if extra_arguments[:1] == ["--"] else extra_arguments
    cwd = Path(os.environ.get("LLMS_CALLER_CWD", str(Path.cwd())))
    return subprocess.run(  # noqa: S603 - runs the pinned tool the user asked for
        [*tool_command(name), *arguments], check=False, cwd=cwd, env=tool_env()
    ).returncode


def preview_result(target: str) -> dict[str, Any]:
    result = preview(target)
    result["tools"] = [
        {
            "tool": name,
            "pinned": spec["version"],
            "installed": installed_version(name),
            "integration_enabled": spec.get("integration_enabled", True),
        }
        for name, spec in manifest()["tools"].items()
    ]
    return result


def versions_result(target: str, *, latest: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tools": [
            {
                "tool": name,
                "pinned": spec["version"],
                "installed": installed_version(name),
                "source": spec["source"],
            }
            for name, spec in manifest()["tools"].items()
        ],
        "hosts": list(selected_hosts(target)),
        "writes": False,
    }
    if latest:
        for entry in result["tools"]:
            entry["latest"] = latest_version(entry["tool"])
    return result


def lock_result() -> dict[str, Any]:
    locks: list[dict[str, Any]] = []
    if tools_with("npm"):
        locks.append(lock_npm_tools())
    locks.extend(lock_uv_tool(name, spec) for name, spec in tools_with("uv").items())
    return {"locks": locks}


def command_result(args: argparse.Namespace) -> dict[str, Any]:
    """Run every command except `run` and return its result."""
    results: dict[str, Callable[[], dict[str, Any]]] = {
        "install": install,
        "lock": lock_result,
        "configure": lambda: configure(args.target),
        "doctor": lambda: doctor(args.target),
        "preview": lambda: preview_result(args.target),
        "versions": lambda: versions_result(args.target, latest=False),
        "check": lambda: versions_result(args.target, latest=True),
    }
    return results[args.command]()


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        # Check the manifest first, so a bad entry stops the command before any download.
        manifest()
        if args.tool:
            require_known_tool(args.tool)
        if args.command == "run":
            return run_tool(args.tool, args.arguments)
        result = command_result(args)
        result["command"] = args.command
        emit(result, args.output)
        return 1 if result.get("problems") else 0
    except (ManifestError, UnknownToolError) as error:
        emit({"command": TASK_NAMES[args.command], "error": str(error)}, args.output)
        return 1
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        emit({"command": args.command, "error": str(error)}, args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
