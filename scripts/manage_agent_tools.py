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
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

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


def manifest() -> dict[str, Any]:
    data = json.loads((ROOT / "agent-dependencies.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported agent-dependencies.json schema")
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
    runtime = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
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
    kept = []
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


def tool_command(name: str) -> list[str]:
    if name in {"serena", "cq"}:
        return [str(TOOLS / "bin" / (name + (".exe" if os.name == "nt" else "")))]
    package = "gitnexus" if name == "gitnexus" else "@ast-grep/cli"
    package_root = TOOLS / "npm/node_modules" / package
    metadata_path = package_root / "package.json"
    if metadata_path.is_file():
        bins = json.loads(metadata_path.read_text(encoding="utf-8"))["bin"]
        entry = (
            bins
            if isinstance(bins, str)
            else bins["gitnexus" if name == "gitnexus" else "ast-grep"]
        )
    else:
        # Known entry points let a fresh-machine preview describe absent tools.
        entry = "dist/cli/index.js" if name == "gitnexus" else "ast-grep"
    path = package_root / entry
    if name == "ast-grep" and os.name == "nt":
        path = path.with_suffix(".exe")
    return [str(path)] if name == "ast-grep" else [node_command(), str(path)]


def installed_version(name: str) -> str | None:
    try:
        if name == "serena":
            venv = TOOLS / "uv/serena-agent"
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            return run(
                [
                    str(python),
                    "-c",
                    "import importlib.metadata; print(importlib.metadata.version('serena-agent'))",
                ],
                timeout=20,
            )
        output = run([*tool_command(name), "--version"], timeout=30)
        match = re.search(r"\d+\.\d+\.\d+", output)
        return match.group() if match else None
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError):
        return None


def serena_dependency_versions() -> dict[str, str]:
    packages = manifest()["tools"].get("serena", {}).get("dependency_overrides", {})
    if not packages:
        return {}
    python = TOOLS / "uv/serena-agent" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    code = (
        "import importlib.metadata as m, json; print(json.dumps({p:m.version(p) for p in "
        + repr(list(packages))
        + "}))"
    )
    try:
        return json.loads(run([str(python), "-c", code], timeout=20))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return {}


def download(url: str) -> bytes:
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError(f"refusing to download a non-https URL: {url}")
    request = urllib.request.Request(  # noqa: S310 - https is checked above
        url, headers={"User-Agent": "llms-bootstrap"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - https is checked above
        return response.read()


def install_cq(spec: dict[str, Any]) -> None:
    systems = {"Windows": "Windows", "Linux": "Linux", "Darwin": "Darwin"}
    machines = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    system, machine = systems[platform.system()], machines[platform.machine().lower()]
    asset = f"cq_{system}_{machine}.{'zip' if system == 'Windows' else 'tar.gz'}"
    payload = download(f"{spec['release']}/{asset}")
    if hashlib.sha256(payload).hexdigest() != spec["checksums"][asset]:
        raise RuntimeError(f"cq release checksum mismatch: {asset}")
    name = "cq.exe" if system == "Windows" else "cq"
    if system == "Windows":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files = [member for member in archive.namelist() if Path(member).name == name]
            if len(files) != 1:
                raise RuntimeError("cq archive must contain exactly one executable")
            executable = archive.read(files[0])
    else:
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            files = [
                member
                for member in archive.getmembers()
                if member.isfile() and Path(member.name).name == name
            ]
            if len(files) != 1:
                raise RuntimeError("cq archive must contain exactly one executable")
            stream = archive.extractfile(files[0])
            if stream is None:
                raise RuntimeError("cq archive executable could not be read")
            executable = stream.read()
    destination = TOOLS / "bin" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_suffix(".new")
    staged.write_bytes(executable)
    staged.chmod(0o755)
    staged.replace(destination)


def npm_package() -> dict[str, Any]:
    specs = manifest()["tools"]
    return {
        "name": "llms-agent-tools",
        "version": "0.0.0",
        "private": True,
        "dependencies": {
            specs[name]["package"]: specs[name]["version"] for name in ("ast-grep", "gitnexus")
        },
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


SERENA_CONSTRAINTS = ROOT / "agent-tools/serena-constraints.txt"


def serena_overrides_file(spec: dict[str, Any]) -> Path:
    path = TOOLS / "serena-overrides.txt"
    update_file(
        path,
        "".join(
            f"{package}=={version}\n"
            for package, version in spec.get("dependency_overrides", {}).items()
        ),
    )
    return path


def lock_serena() -> dict[str, Any]:
    """Resolve Serena's whole dependency tree once, for every platform."""
    spec = manifest()["tools"]["serena"]
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is missing. Run ./bootstrap.sh deps:install first.")
    with tempfile.TemporaryDirectory(prefix="llms-serena-lock-") as workspace:
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
                str(serena_overrides_file(spec)),
                "--no-header",
                "--no-annotate",
                "--output-file",
                str(output),
            ],
            input_text=f"{spec['package']}=={spec['version']}\n",
        )
        action = update_file(SERENA_CONSTRAINTS, output.read_text(encoding="utf-8"))
    return {"lockfile": str(SERENA_CONSTRAINTS), "action": action}


def serena_constraints_current() -> bool:
    installed = TOOLS / "serena-constraints.txt"
    return not SERENA_CONSTRAINTS.is_file() or (
        installed.is_file() and installed.read_bytes() == SERENA_CONSTRAINTS.read_bytes()
    )


def install() -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is missing. Run ./bootstrap.sh deps:install first.")
    TOOLS.mkdir(parents=True, exist_ok=True)
    runtime = {name: shutil.which(name) for name in ("node", "uv", "task")}
    # .tools/bin/task forwards to this repo's bootstrap; agents get the real Task.
    wrappers = ROOT / ".tools/bin"
    if runtime["task"] and Path(runtime["task"]).parent == wrappers:
        mise = wrappers / ("mise.exe" if os.name == "nt" else "mise")
        runtime["task"] = run([str(mise), "which", "task"], timeout=30)
    update_file(TOOLS / "runtime.json", json.dumps(runtime, indent=2) + "\n")
    results = []
    npm_reinstalled = False
    for name, spec in manifest()["tools"].items():
        expected = spec["version"]
        before = installed_version(name)
        needs_install = (
            before != expected
            or (
                name == "serena"
                and (
                    serena_dependency_versions() != spec.get("dependency_overrides", {})
                    or not serena_constraints_current()
                )
            )
            or (name in {"ast-grep", "gitnexus"} and not npm_lock_current())
        )
        if needs_install:
            if name == "serena":
                uv = shutil.which("uv")
                if not uv:
                    raise RuntimeError("uv is missing. Run ./bootstrap.sh deps:install first.")
                command = [
                    uv,
                    "tool",
                    "install",
                    "--python",
                    spec["python"],
                    "--force",
                    f"{spec['package']}=={expected}",
                    "--overrides",
                    str(serena_overrides_file(spec)),
                ]
                if SERENA_CONSTRAINTS.is_file():
                    command.extend(["--constraints", str(SERENA_CONSTRAINTS)])
                run(command)
                if SERENA_CONSTRAINTS.is_file():
                    update_file(
                        TOOLS / "serena-constraints.txt",
                        SERENA_CONSTRAINTS.read_text(encoding="utf-8"),
                    )
            elif name == "cq":
                install_cq(spec)
            else:
                install_npm_tools()
                npm_reinstalled = True
        actual = installed_version(name)
        if actual != expected:
            raise RuntimeError(f"{name}: expected {expected}, installed version is {actual!r}")
        if name == "serena" and serena_dependency_versions() != spec.get(
            "dependency_overrides", {}
        ):
            raise RuntimeError("Serena's reviewed security dependency overrides were not installed")
        results.append(
            {
                "tool": name,
                "version": actual,
                "action": "installed"
                if needs_install or (name in {"ast-grep", "gitnexus"} and npm_reinstalled)
                else "unchanged",
                "command": tool_command(name),
            }
        )
    return {"tools": results}


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


def jsonc_pending(path: Path, dry_run: bool) -> bool:
    return dry_run and path.suffix == ".jsonc" and not (TOOLS / "npm/package.json").is_file()


def write_json_config(path: Path, data: dict[str, Any], *, dry_run: bool) -> str:
    text = (
        jsonc_document(path, data)["text"]
        if path.suffix == ".jsonc"
        else json.dumps(data, indent=2) + "\n"
    )
    return update_file(path, text, dry_run=dry_run)


def merge_mcp_servers_json(path: Path, servers: dict[str, Any], *, dry_run: bool = False) -> str:
    """Write stdio servers under `mcpServers`, with command, args and env."""
    if jsonc_pending(path, dry_run):
        return JSONC_PENDING
    data = read_host_json(path) if path.exists() else {}
    for name, server in servers.items():
        existing = data.setdefault("mcpServers", {}).setdefault(name, {})
        for key in REMOTE_SERVER_FIELDS:
            existing.pop(key, None)
        environment = {**existing.get("env", {}), **server.get("env", {})}
        existing.update(server, env=environment, type="stdio")
    return write_json_config(path, data, dry_run=dry_run)


def merge_opencode_servers(path: Path, servers: dict[str, Any], *, dry_run: bool = False) -> str:
    """Write local servers under `mcp` (v1) or `mcp.servers` (v2), whichever OpenCode reads."""
    if jsonc_pending(path, dry_run):
        return JSONC_PENDING
    data = read_host_json(path) if path.exists() else {}
    # OpenCode 2 uses mcp.servers; keep v1 when an installed host requires it.
    binary = shutil.which(OPENCODE.name)
    version = run([binary, "--version"], timeout=15) if binary else "2"
    mcp = data.setdefault("mcp", {})
    if version.startswith("1."):
        container = mcp
    else:
        container = mcp.setdefault("servers", {})
        for name, entry in list(mcp.items()):
            if (
                name != "servers"
                and isinstance(entry, dict)
                and entry.get("type") in {"local", "remote"}
            ):
                if name not in container:
                    container[name] = entry
                del mcp[name]
    for name, server in servers.items():
        existing = container.setdefault(name, {})
        for key in REMOTE_SERVER_FIELDS:
            existing.pop(key, None)
        environment = {**existing.get("environment", {}), **server.get("env", {})}
        existing.update(
            type="local",
            command=[server["command"], *server["args"]],
            environment=environment,
        )
    return write_json_config(path, data, dry_run=dry_run)


def merge_codex(path: Path, servers: dict[str, Any], *, dry_run: bool = False) -> str:
    import tomlkit  # noqa: PLC0415 - only Codex files need tomlkit, so import it when used

    text = path.read_text(encoding="utf-8") if path.exists() else ""
    document = tomlkit.parse(text)
    configured = document.setdefault("mcp_servers", tomlkit.table())
    for name, server in servers.items():
        existing = configured.setdefault(name, tomlkit.table())
        for key in (*REMOTE_SERVER_FIELDS, "type"):
            existing.pop(key, None)
        for key, value in server.items():
            if key == "env":
                existing.setdefault("env", tomlkit.table()).update(value)
            else:
                existing[key] = value
    agents = document.setdefault("agents", tomlkit.table())
    if "max_concurrent_threads_per_session" not in agents and "max_threads" not in agents:
        agents["max_concurrent_threads_per_session"] = 3
    result = tomlkit.dumps(document)
    tomllib.loads(result)
    return update_file(path, result, dry_run=dry_run)


def serena_home() -> Path:
    selected = os.environ.get("SERENA_HOME", "").strip()
    return Path(selected or Path.home() / ".serena").resolve()


def serena_configuration(*, apply: bool = False, dry_run: bool = False) -> dict[str, Any]:
    settings = manifest()["tools"]["serena"]["config"]
    python = TOOLS / "uv/serena-agent" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
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


def adapter_for(host: str) -> HostAdapter:
    try:
        return ADAPTERS[host]
    except KeyError:
        raise ValueError(f"Unknown host: {host}") from None


def adapter_for_file(path: Path) -> HostAdapter:
    """Find the adapter whose MCP server file has this name."""
    for adapter in ADAPTERS.values():
        if path.name in {file.name for file in adapter.server_files()}:
            return adapter
    raise ValueError(f"No host keeps its MCP servers in {path}")


def selected_hosts(target: str) -> tuple[str, ...]:
    return tuple(ADAPTERS) if target == "all" else (target,)


def host_config(host: str) -> Path:
    return adapter_for(host).config_path()


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
        if path.suffix == ".jsonc" and not (TOOLS / "npm/package.json").is_file():
            continue  # Preview reports that JSONC validation awaits installation.
        entry = adapter.read_servers(path).get("serena", {})
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


def restore_servers(snapshot: dict[Path, str | None], adapter: HostAdapter | None = None) -> None:
    """Undo an upstream installer's MCP server edits, keeping all other changes.

    Upstream installers replace server entries this script manages, and some
    write a config file the host does not read. Only the server section is put
    back, onto the current file, so edits made meanwhile by a running host
    survive. A file the installer created that holds nothing else is removed.
    The host's adapter names the server section; without one, the adapter that
    owns the file is used.
    """
    import tomlkit  # noqa: PLC0415 - only Codex files need tomlkit, so import it when used

    for path, original in snapshot.items():
        if not path.is_file():
            continue
        current = path.read_text(encoding="utf-8")
        if current == original:
            continue
        digest = hashlib.sha256(current.encode("utf-8")).hexdigest()
        key = (adapter or adapter_for_file(path)).servers_key
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


def existing_server(host: str, name: str) -> bool:
    adapter = adapter_for(host)
    path = adapter.config_path()
    return path.exists() and name in adapter.read_servers(path)


def required_tool_paths() -> set[str]:
    receipt = TOOLS / "runtime.json"
    runtime = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
    paths = [
        TOOLS / "bin",
        *(Path(value).parent for value in runtime.values() if value),
    ]
    return {os.path.normcase(os.path.normpath(str(path))) for path in paths}


def host_servers(host: str) -> dict[str, Any]:
    adapter = adapter_for(host)
    selected = servers()
    for name in adapter.dropped_servers():
        selected.pop(name, None)
    if not adapter.keeps_startup_timeout:
        for server in selected.values():
            server.pop("startup_timeout_sec", None)
    arguments = selected["serena"]["args"]
    arguments[arguments.index("--context") + 1] = adapter.serena_context
    return selected


def managed_servers(host: str) -> dict[str, Any]:
    return host_servers(host) if adapter_for(host).manages_servers else {}


def claude_plugin_enabled() -> bool:
    path = Path.home() / ".claude/settings.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return any(
        value is True and name.split("@", 1)[0] == "cq"
        for name, value in settings.get("enabledPlugins", {}).items()
    )


def configure_claude_environment(*, dry_run: bool = False) -> str:
    path = Path.home() / ".claude/settings.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    environment = settings.setdefault("env", {})
    # Rebuild rather than extend the previous value, so stale entries drop out.
    environment.update(PATH=tool_env()["PATH"], CQ_ADDR="")
    return update_file(path, json.dumps(settings, indent=2) + "\n", dry_run=dry_run)


def configure_pi(*, dry_run: bool = False) -> str:
    settings_path = Path.home() / ".pi/agent/settings.json"
    settings = (
        json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    )
    prefix = settings.get("shellCommandPrefix", "").rstrip()
    local_prefix = "export CQ_ADDR='';"
    if not prefix.endswith(local_prefix):
        settings["shellCommandPrefix"] = (
            prefix + (" " if prefix.endswith(";") else "; ") if prefix else ""
        ) + local_prefix
    return update_file(settings_path, json.dumps(settings, indent=2) + "\n", dry_run=dry_run)


def preview(target: str) -> dict[str, Any]:
    require_standard_profiles(target)
    planned = []
    for host in selected_hosts(target):
        adapter = adapter_for(host)
        path = adapter.config_path()
        expected = managed_servers(host)
        action = adapter.write_config(path, expected, dry_run=True)
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
                "serena_hooks": configure_serena_hooks(host, dry_run=True),
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
    targets = installer.selected_targets(
        installer.resolve_targets(installer.parse_args([])), target
    )
    problems = list(validation["errors"])
    hosts = []
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
    return {"hosts": hosts, "source_valid": validation["valid"], "problems": problems}


def gitnexus_hook_paths(host: str) -> tuple[Path, Path]:
    adapter = adapter_for(host)
    if adapter.hooks_dir is None:
        raise ValueError(f"{host} has no hooks folder")
    directory = Path.home() / adapter.hooks_dir
    return directory / adapter.hooks_file, directory / "hooks/gitnexus/gitnexus-hook.cjs"


def gitnexus_hook_launch(host: str) -> dict[str, Any]:
    _, hook = gitnexus_hook_paths(host)
    arguments = [
        Path(node_command()).as_posix(),
        (ROOT / "scripts/run_gitnexus_hook.mjs").as_posix(),
        (TOOLS / "gitnexus-indexes").as_posix(),
        hook.as_posix(),
        Path(tool_command("gitnexus")[1]).as_posix(),
    ]
    if adapter_for(host).hook_exec_form:
        return {"command": arguments[0], "args": arguments[1:]}
    script = "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in arguments)
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


def gitnexus_owned_hooks(data: dict[str, Any], host: str) -> list[dict[str, Any]]:
    _, hook = gitnexus_hook_paths(host)
    owned = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            command = value.get("command", "")
            arguments = value.get("args", [])
            references = [command, *arguments] if isinstance(arguments, list) else [command]
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
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(data.get("hooks", {}))
    return owned


def configure_gitnexus_hooks(host: str) -> None:
    if adapter_for(host).hooks_dir is None:
        return
    path, _ = gitnexus_hook_paths(host)
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    for hook in gitnexus_owned_hooks(data, host):
        for key in ("command", "args", "commandWindows"):
            hook.pop(key, None)
        hook.update(gitnexus_hook_launch(host))
    # Upstream recognizes shell-form commands only; Claude exec form would
    # otherwise accumulate a second registration on every native setup pass.
    owned = {id(hook) for hook in gitnexus_owned_hooks(data, host)}
    for event, groups in data.get("hooks", {}).items():
        seen: set[str] = set()
        for group in groups:
            retained = []
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


def serena_hook(host: str, action: str) -> dict[str, Any]:
    binary = str(TOOLS / "bin" / ("serena-hooks" + (".exe" if os.name == "nt" else "")))
    adapter = adapter_for(host)
    arguments = [action, "--client=" + adapter.serena_client]
    hook: dict[str, Any] = {"type": "command", "timeout": 3 if action == "cleanup" else 5}
    if adapter.hook_exec_form:
        hook.update(command=binary, args=arguments)
    else:
        join = subprocess.list2cmdline if os.name == "nt" else shlex.join
        hook["command"] = join([binary, *arguments])
    return hook


def configure_serena_hooks(host: str, *, dry_run: bool = False) -> str:
    """Remind agents to use Serena; without hooks they rarely load its tools."""
    adapter = adapter_for(host)
    if not adapter.serena_hooks:
        return "not applicable"
    path, _ = gitnexus_hook_paths(host)
    data = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
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
        group: dict[str, Any] = {"hooks": [serena_hook(host, action)]}
        if matcher:
            group = {"matcher": matcher, **group}
        hooks.setdefault(event, []).append(group)
    return update_file(path, json.dumps(data, indent=2) + "\n", dry_run=dry_run)


class StandardProfile(NamedTuple):
    """A host whose profile folder an environment variable can move."""

    is_standard: Callable[[], bool]
    startup_error: str  # uses {directory}
    doctor_problem: str  # uses {directory}


class HostAdapter(NamedTuple):
    """Everything setup needs to know about one host.

    `configure`, `preview`, `doctor` and the helpers under them take host
    details only from here. To add a host, define one adapter and add it to
    `ADAPTERS`.
    """

    name: str  # also the host's command-line client and cq's `--target`
    config_path: Callable[[], Path]  # the file that holds the managed servers
    # Write the managed servers to the config file; return the action taken.
    write_config: Callable[..., str]
    # Name each way the config differs from what `write_config` writes.
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
    read_servers: Callable[[Path], dict[str, Any]] = lambda path: {}
    keeps_startup_timeout: bool = False
    dropped_servers: Callable[[], tuple[str, ...]] = lambda: ()
    hooks_dir: str | None = None  # under the home folder; None: no hooks file
    hooks_file: str = ""
    hook_exec_form: bool = False  # hooks hold `command` and `args`, not one command line
    serena_hooks: tuple[tuple[str, str, str], ...] = ()  # (event, matcher, action)
    runs_serena_setup: bool = False
    needs_client_binary: bool = False  # serena and cq setup need the host's own client
    missing_client_limitation: str = ""
    tolerates_managed_settings_error: bool = False
    managed_settings_limitation: str = ""  # uses {error}
    profile: StandardProfile | None = None
    environment_step: Callable[..., str] | None = None
    migrate_config: Callable[[Path, list[str]], None] | None = None
    extra_problems: Callable[[Path, dict[str, Any]], list[str]] | None = None

    def server_files(self) -> set[Path]:
        return {self.config_path(), *self.extra_server_files()}


def codex_config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"


def standard_codex_profile() -> bool:
    return codex_config_path().parent.resolve() == (Path.home() / ".codex").resolve()


def codex_backup_paths() -> list[Path]:
    return [codex_config_path().parent / "AGENTS.md"]


def codex_skill_roots() -> list[Path]:
    return [Path.home() / ".agents/skills", Path.home() / ".codex/skills"]


def read_codex_servers(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8")).get("mcp_servers", {})


def claude_config_path() -> Path:
    return Path.home() / ".claude.json"


def read_claude_servers(path: Path) -> dict[str, Any]:
    return read_host_json(path).get("mcpServers", {})


def claude_dropped_servers() -> tuple[str, ...]:
    return ("cq",) if claude_plugin_enabled() else ()


def migrate_claude_cq_entry(path: Path, limitations: list[str]) -> None:
    """Move this script's old cq server entry into Claude's settings for the cq plugin."""
    if not (claude_plugin_enabled() and path.exists()):
        return
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    manual = data.get("mcpServers", {}).get("cq", {})
    if manual.get("command") == tool_command("cq")[0]:
        settings_path = Path.home() / ".claude/settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        environment = settings.setdefault("env", {})
        # Global env reaches every Claude process; move only the
        # values this script wrote, and report anything else.
        for key, value in manual.get("env", {}).items():
            if key in {"UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR"}:
                environment.setdefault(key, value)
            elif key not in {"PATH", "CQ_ADDR"}:
                limitations.append(
                    f"dropped {key} from the old cq server entry; set it again where cq needs it"
                )
        update_file(settings_path, json.dumps(settings, indent=2) + "\n")
        del data["mcpServers"]["cq"]
        update_file(path, json.dumps(data, indent=2) + "\n")
    elif manual:
        raise RuntimeError(
            "An existing unmanaged Claude cq server conflicts with the cq plugin; "
            "preserve its settings and resolve that entry before configuring"
        )


def claude_plugin_problems(path: Path, container: dict[str, Any]) -> list[str]:
    if not claude_plugin_enabled():
        return []
    reasons = []
    settings = json.loads((Path.home() / ".claude/settings.json").read_text(encoding="utf-8"))
    if "cq" in container:
        reasons.append(f"an old cq server entry in {path} duplicates the cq plugin")
    if settings.get("env", {}).get("CQ_ADDR") != "":
        reasons.append("CQ_ADDR in ~/.claude/settings.json is not empty, so cq may sync remotely")
    return reasons


def pi_config_path() -> Path:
    return Path.home() / ".pi/agent/AGENTS.md"


def pi_backup_paths() -> list[Path]:
    return [Path.home() / ".pi/agent/settings.json"]


def write_pi_mapping(path: Path, servers: dict[str, Any], *, dry_run: bool = False) -> str:
    """Pi uses cq's CLI mapping, not an invented MCP adapter."""
    action = configure_pi(dry_run=dry_run)
    return action if dry_run else "configured CLI mapping"


def pi_problems(adapter: HostAdapter, path: Path) -> list[str]:
    reasons: list[str] = []
    text = path.read_text(encoding="utf-8")
    settings_path = Path.home() / ".pi/agent/settings.json"
    settings = (
        json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    )
    cq_block = re.search(r"<!-- cq:start -->(.*?)<!-- cq:end -->", text, re.S)
    if not (cq_block and f"The cq binary is: `{tool_command('cq')[0]}`." in cq_block.group(1)):
        reasons.append(f"cq instructions in {path} are missing or point elsewhere")
    if not settings.get("shellCommandPrefix", "").rstrip().endswith("export CQ_ADDR='';"):
        reasons.append(f"{settings_path} does not keep cq local (CQ_ADDR)")
    return reasons


def opencode_files() -> set[Path]:
    directory = Path.home() / ".config/opencode"
    return {directory / name for name in ("opencode.json", "opencode.jsonc", "config.json")}


def opencode_config_path() -> Path:
    directory = Path.home() / ".config/opencode"
    return next(
        (
            directory / name
            for name in ("opencode.jsonc", "opencode.json", "config.json")
            if (directory / name).is_file()
        ),
        directory / "opencode.json",
    )


def opencode_backup_paths() -> list[Path]:
    return [Path.home() / ".config/opencode/AGENTS.md"]


def read_opencode_servers(path: Path) -> dict[str, Any]:
    mcp = read_host_json(path).get("mcp", {})
    return mcp.get("servers", mcp)


def server_problems(adapter: HostAdapter, path: Path) -> list[str]:
    reasons: list[str] = []
    container = adapter.read_servers(path)
    expected = host_servers(adapter.name)
    for name, wanted in expected.items():
        actual = container.get(name)
        if actual is None:
            reasons.append(f"{name} server missing from {path}")
            continue
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
    if adapter.serena_hooks and configure_serena_hooks(adapter.name, dry_run=True) != "unchanged":
        reasons.append(
            f"Serena hooks in {gitnexus_hook_paths(adapter.name)[0]} are missing or stale"
        )
    if "gitnexus" in expected and adapter.hooks_dir is not None:
        hooks_path, hook_script = gitnexus_hook_paths(adapter.name)
        hook_data = (
            json.loads(hooks_path.read_text(encoding="utf-8-sig")) if hooks_path.is_file() else {}
        )
        owned = gitnexus_owned_hooks(hook_data, adapter.name)
        launch = gitnexus_hook_launch(adapter.name)
        if (
            not hook_script.is_file()
            or not owned
            or any(any(hook.get(k) != v for k, v in launch.items()) for hook in owned)
        ):
            reasons.append(f"GitNexus hooks in {hooks_path} are missing or stale")
    if adapter.extra_problems:
        reasons.extend(adapter.extra_problems(path, container))
    return reasons


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
    hooks_dir=".codex",
    hooks_file="hooks.json",
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
CLAUDE = HostAdapter(
    name="claude",
    config_path=claude_config_path,
    write_config=merge_mcp_servers_json,
    check_config=server_problems,
    serena_client="claude-code",
    gitnexus_client="claude",
    serena_context="claude-code",
    read_servers=read_claude_servers,
    dropped_servers=claude_dropped_servers,
    hooks_dir=".claude",
    hooks_file="settings.json",
    hook_exec_form=True,
    serena_hooks=(
        ("SessionStart", "startup|resume|clear|compact", "activate"),
        ("PreToolUse", "", "remind"),
        ("SessionEnd", "", "cleanup"),
    ),
    runs_serena_setup=True,
    needs_client_binary=True,
    missing_client_limitation=(
        "cq's Claude plugin installation requires Claude CLI; "
        "rerun agents:configure after installing that client"
    ),
    tolerates_managed_settings_error=True,
    managed_settings_limitation=(
        "cq plugin setup unavailable; rerun agents:configure after claude auth login: {error}"
    ),
    environment_step=configure_claude_environment,
    migrate_config=migrate_claude_cq_entry,
    extra_problems=claude_plugin_problems,
)
PI = HostAdapter(
    name="pi",
    config_path=pi_config_path,
    write_config=write_pi_mapping,
    check_config=pi_problems,
    serena_client="pi",
    gitnexus_client="pi",
    serena_context="ide",
    backup_paths=pi_backup_paths,
    manages_servers=False,
)
OPENCODE = HostAdapter(
    name="opencode",
    config_path=opencode_config_path,
    write_config=merge_opencode_servers,
    check_config=server_problems,
    serena_client="opencode",
    gitnexus_client="opencode",
    serena_context="ide",
    backup_paths=opencode_backup_paths,
    extra_server_files=opencode_files,
    servers_key="mcp",
    env_key="environment",
    command_is_list=True,
    read_servers=read_opencode_servers,
)
# The host list: its order is the order setup configures hosts in.
ADAPTERS: dict[str, HostAdapter] = {
    adapter.name: adapter for adapter in (CODEX, CLAUDE, PI, OPENCODE)
}


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
    if adapter.hooks_dir is not None:
        paths.append(gitnexus_hook_paths(adapter.name)[0])
    for path in paths:
        backup_configuration(path)
    return paths


def register_serena(adapter: HostAdapter, upstream: list[str], limitations: list[str]) -> None:
    """Register an absent Serena server through upstream; preserve existing entries."""
    if not adapter.runs_serena_setup:
        return
    if adapter.needs_client_binary and not shutil.which(adapter.name):
        return
    if existing_server(adapter.name, "serena"):
        return
    try:
        upstream.append(run([*tool_command("serena"), "setup", adapter.serena_client], timeout=90))
    except RuntimeError as error:
        if "not found or not functional" not in str(error) and not (
            adapter.tolerates_managed_settings_error and MANAGED_SETTINGS_ERROR in str(error)
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
    configure_gitnexus_hooks(adapter.name)


def run_cq_install(
    adapter: HostAdapter, server_paths: set[Path], upstream: list[str], limitations: list[str]
) -> None:
    """Use cq's maintained skill/instruction installer.

    Claude's plugin route needs the Claude CLI; other hosts can be configured
    without their binaries.
    """
    if adapter.needs_client_binary and not shutil.which(adapter.name):
        limitations.append(adapter.missing_client_limitation)
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
        if not (adapter.tolerates_managed_settings_error and MANAGED_SETTINGS_ERROR in str(error)):
            raise
        limitations.append(adapter.managed_settings_limitation.format(error=error))


def write_managed_config(adapter: HostAdapter, limitations: list[str]) -> tuple[Path, str]:
    selected = managed_servers(adapter.name)
    path = adapter.config_path()
    if adapter.migrate_config:
        adapter.migrate_config(path, limitations)
    return path, adapter.write_config(path, selected)


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
    hooks_action = configure_serena_hooks(adapter.name)
    path, action = write_managed_config(adapter, limitations)
    return {
        "host": adapter.name,
        "config": str(path),
        "action": action,
        "serena_hooks": hooks_action,
        "client_available": bool(shutil.which(adapter.name)),
        "upstream_installers": bool(upstream),
        "limitations": limitations,
        "note": (
            "MCP servers configured; client connection and hook trust require verification"
            if adapter.manages_servers
            else "cq CLI mapping; other CLIs available through Task"
        ),
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
    if serena_dependency_versions() != manifest()["tools"].get("serena", {}).get(
        "dependency_overrides", {}
    ):
        problems.append(
            "Serena's pinned security patches (dependency_overrides in "
            "agent-dependencies.json) are not installed; run ./bootstrap.sh tools:install"
        )
    hosts = []
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


def emit(result: dict[str, Any], output: str) -> None:
    if output == "json":
        print(json.dumps(result, indent=2))
        return
    if result.get("error"):
        print(f"{result['command']}: {result['error']}")
        return
    for lock in result.get("locks", []):
        print(f"lock: {lock['action']}; {lock['lockfile']}")
    if result.get("serena"):
        serena = result["serena"]
        print("Serena preferences: " + serena.get("action", f"configured={serena['configured']}"))
    for tool in result.get("tools", []):
        selected = tool.get("version", tool.get("pinned", tool.get("expected")))
        observed = tool.get("installed", tool.get("version"))
        update = f"; available {tool['latest']}" if "latest" in tool else ""
        print(f"{tool['tool']}: selected {selected}; installed {observed}{update}")
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
    for problem in result.get("problems", []):
        print(f"problem: {problem}")
    if result.get("disabled_integrations"):
        print("Disabled integrations: " + ", ".join(result["disabled_integrations"]))
    if result.get("note"):
        print(result["note"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--command",
        choices=(
            "install",
            "configure",
            "doctor",
            "preview",
            "versions",
            "check",
            "run",
            "lock",
        ),
        required=True,
    )
    parser.add_argument("--target", choices=("all", *ADAPTERS), default="all")
    parser.add_argument("--output", choices=("json", "text"), default="text")
    parser.add_argument("--tool", choices=("serena", "ast-grep", "gitnexus", "cq"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            if not args.tool:
                parser.error("--command run requires --tool")
            spec = manifest()["tools"][args.tool]
            if spec.get("integration_enabled") is False:
                raise RuntimeError(  # noqa: TRY301 - the except below prints it as the command's error
                    f"{args.tool} is turned off "
                    "(integration_enabled: false in agent-dependencies.json); "
                    f"its license is at {spec.get('license_url')}"
                )
            if installed_version(args.tool) != spec["version"]:
                raise RuntimeError(  # noqa: TRY301 - the except below prints it as the command's error
                    f"The pinned {args.tool} is not installed. "
                    "Run ./bootstrap.sh tools:install first."
                )
            arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
            cwd = Path(os.environ.get("LLMS_CALLER_CWD", str(Path.cwd())))
            return subprocess.run(  # noqa: S603 - runs the pinned tool the user asked for
                [*tool_command(args.tool), *arguments], check=False, cwd=cwd, env=tool_env()
            ).returncode
        result: dict[str, Any]
        if args.command == "install":
            result = install()
        elif args.command == "lock":
            result = {"locks": [lock_npm_tools(), lock_serena()]}
        elif args.command == "configure":
            result = configure(args.target)
        elif args.command == "doctor":
            result = doctor(args.target)
        elif args.command == "preview":
            result = preview(args.target)
            result["tools"] = [
                {
                    "tool": name,
                    "pinned": spec["version"],
                    "installed": installed_version(name),
                    "integration_enabled": spec.get("integration_enabled", True),
                }
                for name, spec in manifest()["tools"].items()
            ]
        else:
            result = {
                "tools": [
                    {
                        "tool": name,
                        "pinned": spec["version"],
                        "installed": installed_version(name),
                        "source": spec["source"],
                    }
                    for name, spec in manifest()["tools"].items()
                ],
                "hosts": list(selected_hosts(args.target)),
                "writes": False,
            }
            if args.command == "check":
                for entry in result["tools"]:
                    name = entry["tool"]
                    if name == "serena":
                        entry["latest"] = json.loads(
                            download("https://pypi.org/pypi/serena-agent/json")
                        )["info"]["version"]
                    elif name in {"ast-grep", "gitnexus"}:
                        entry["latest"] = json.loads(
                            download(
                                "https://registry.npmjs.org/"
                                + manifest()["tools"][name]["package"]
                                + "/latest"
                            )
                        )["version"]
                    else:
                        releases = json.loads(
                            download(
                                "https://api.github.com/repos/mozilla-ai/cq/releases?per_page=30"
                            )
                        )
                        entry["latest"] = next(
                            release["tag_name"].removeprefix("cli/v")
                            for release in releases
                            if release["tag_name"].startswith("cli/v") and not release["prerelease"]
                        )
        result["command"] = args.command
        emit(result, args.output)
        return 1 if result.get("problems") else 0
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
