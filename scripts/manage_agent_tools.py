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
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools" / "agent-tools"
HOSTS = ("codex", "claude", "pi", "opencode")
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
        GITNEXUS_STORAGE_ROOT=str(TOOLS / "gitnexus-indexes"),
        CQ_ADDR="",
    )
    env.pop("GITNEXUS_STORAGE_PATH", None)
    paths = [str(TOOLS / "bin")]
    receipt = TOOLS / "runtime.json"
    runtime = (
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
    entries = paths + inherited.split(os.pathsep)
    seen: set[str] = set()
    stable_paths = []
    for entry in entries:
        key = os.path.normcase(os.path.normpath(entry))
        if entry and key not in seen:
            stable_paths.append(entry)
            seen.add(key)
    env["PATH"] = os.pathsep.join(stable_paths)
    return env


def run(
    args: list[str],
    *,
    timeout: int = 600,
    cwd: Path | None = None,
    input_text: str | None = None,
) -> str:
    result = subprocess.run(
        args,
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
        raise RuntimeError("Node is missing. Run bootstrap deps:install first.")
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
        output = run(tool_command(name) + ["--version"], timeout=30)
        match = re.search(r"\d+\.\d+\.\d+", output)
        return match.group() if match else None
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError):
        return None


def serena_dependency_versions() -> dict[str, str]:
    packages = manifest()["tools"].get("serena", {}).get("dependency_overrides", {})
    if not packages:
        return {}
    python = (
        TOOLS
        / "uv/serena-agent"
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
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
    request = urllib.request.Request(url, headers={"User-Agent": "llms-bootstrap"})
    with urllib.request.urlopen(request, timeout=60) as response:
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
            files = [
                member for member in archive.namelist() if Path(member).name == name
            ]
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
            assert stream is not None
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
            specs[name]["package"]: specs[name]["version"]
            for name in ("ast-grep", "gitnexus")
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
    if (
        lock.get("packages", {}).get("", {}).get("dependencies")
        != npm_package()["dependencies"]
    ):
        raise RuntimeError(
            "npm lock does not match the declared tool pins; run task tools:lock"
        )
    update_file(TOOLS / "npm/package.json", json.dumps(npm_package(), indent=2) + "\n")
    update_file(TOOLS / "npm/package-lock.json", source.read_text(encoding="utf-8"))
    run(
        npm_command()
        + ["ci", "--prefix", str(TOOLS / "npm"), "--no-audit", "--no-fund"],
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
            npm_command()
            + [
                "install",
                "--package-lock-only",
                "--ignore-scripts",
                "--prefix",
                str(path),
                "--no-audit",
                "--no-fund",
            ]
        )
        action = update_file(
            destination, (path / "package-lock.json").read_text(encoding="utf-8")
        )
    return {"lockfile": str(destination), "action": action}


def install() -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is missing. Run bootstrap deps:install first.")
    TOOLS.mkdir(parents=True, exist_ok=True)
    runtime = {name: shutil.which(name) for name in ("node", "uv", "task")}
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
                and serena_dependency_versions() != spec.get("dependency_overrides", {})
            )
            or (name in {"ast-grep", "gitnexus"} and not npm_lock_current())
        )
        if needs_install:
            if name == "serena":
                uv = shutil.which("uv")
                if not uv:
                    raise RuntimeError(
                        "uv is missing. Run bootstrap deps:install first."
                    )
                command = [
                    uv,
                    "tool",
                    "install",
                    "--python",
                    spec["python"],
                    "--force",
                    f"{spec['package']}=={expected}",
                ]
                overrides = spec.get("dependency_overrides", {})
                if overrides:
                    path = TOOLS / "serena-overrides.txt"
                    update_file(
                        path,
                        "".join(
                            f"{package}=={version}\n"
                            for package, version in overrides.items()
                        ),
                    )
                    command.extend(["--overrides", str(path)])
                run(command)
            elif name == "cq":
                install_cq(spec)
            else:
                install_npm_tools()
                npm_reinstalled = True
        actual = installed_version(name)
        if actual != expected:
            raise RuntimeError(
                f"{name}: expected {expected}, installed version is {actual!r}"
            )
        if name == "serena" and serena_dependency_versions() != spec.get(
            "dependency_overrides", {}
        ):
            raise RuntimeError(
                "Serena's reviewed security dependency overrides were not installed"
            )
        results.append(
            {
                "tool": name,
                "version": actual,
                "action": "installed"
                if needs_install
                or (name in {"ast-grep", "gitnexus"} and npm_reinstalled)
                else "unchanged",
                "command": tool_command(name),
            }
        )
    return {"tools": results}


def private_permissions(path: Path, *, copy_from: Path | None = None) -> None:
    if os.name == "nt":
        powershell = (
            Path(os.environ.get("SystemRoot", "C:/Windows"))
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
        path.chmod(stat.S_IMODE(copy_from.stat().st_mode))
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def update_file(
    path: Path,
    text: str,
    *,
    dry_run: bool = False,
    expected_digest: str | None = None,
) -> str:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    digest = hashlib.sha256(old.encode("utf-8")).hexdigest() if old is not None else ""
    if expected_digest is not None and digest != expected_digest:
        raise RuntimeError(f"Configuration changed during rendering: {path}")
    if old == text:
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
    with os.fdopen(
        os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
    ) as output:
        output.write(path.read_bytes())


def merge_json(
    path: Path, servers: dict[str, Any], host: str, *, dry_run: bool = False
) -> str:
    if (
        dry_run
        and path.suffix == ".jsonc"
        and not (TOOLS / "npm/package.json").is_file()
    ):
        return "would merge JSONC after tools:install; source validation pending"
    data = read_host_json(path) if path.exists() else {}
    if host == "opencode":
        # OpenCode 2 uses mcp.servers; keep v1 when an installed host requires it.
        binary = shutil.which("opencode")
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
    else:
        for name, server in servers.items():
            existing = data.setdefault("mcpServers", {}).setdefault(name, {})
            for key in REMOTE_SERVER_FIELDS:
                existing.pop(key, None)
            environment = {**existing.get("env", {}), **server.get("env", {})}
            existing.update(server, env=environment, type="stdio")
    text = (
        jsonc_document(path, data)["text"]
        if path.suffix == ".jsonc"
        else json.dumps(data, indent=2) + "\n"
    )
    return update_file(path, text, dry_run=dry_run)


def merge_codex(path: Path, servers: dict[str, Any], *, dry_run: bool = False) -> str:
    import tomlkit

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
    if (
        "max_concurrent_threads_per_session" not in agents
        and "max_threads" not in agents
    ):
        agents["max_concurrent_threads_per_session"] = 3
    result = tomlkit.dumps(document)
    tomllib.loads(result)
    return update_file(path, result, dry_run=dry_run)


def serena_home() -> Path:
    selected = os.environ.get("SERENA_HOME", "").strip()
    return Path(selected or Path.home() / ".serena").resolve()


def serena_configuration(*, apply: bool = False, dry_run: bool = False) -> dict[str, Any]:
    settings = manifest()["tools"]["serena"]["config"]
    python = TOOLS / "uv/serena-agent" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
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
        result["action"] = update_file(
            path, text, dry_run=dry_run, expected_digest=original_digest
        )
        result["configured"] = result["configured"] or not dry_run
    return result


def servers() -> dict[str, Any]:
    environment = tool_env()
    launch_env = {
        key: environment[key]
        for key in ("PATH", "UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR")
    }
    configured = {
        "serena": {
            "command": tool_command("serena")[0],
            "args": [
                "start-mcp-server",
                "--project-from-cwd",
                "--context",
                "codex",
                "--open-web-dashboard",
                "false",
            ],
            "env": {**launch_env, "SERENA_HOME": str(serena_home())},
            "startup_timeout_sec": 60,
        },
        "gitnexus": {
            "command": node_command(),
            "args": [str(ROOT / "scripts/run_gitnexus.mjs")]
            + tool_command("gitnexus")[1:]
            + ["mcp"],
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


def selected_hosts(target: str) -> tuple[str, ...]:
    return HOSTS if target == "all" else (target,)


def host_config(host: str) -> Path:
    home = Path.home()
    if host == "codex":
        return Path(os.environ.get("CODEX_HOME", str(home / ".codex"))) / "config.toml"
    if host == "opencode":
        directory = home / ".config/opencode"
        return next(
            (
                directory / name
                for name in ("opencode.jsonc", "opencode.json", "config.json")
                if (directory / name).is_file()
            ),
            directory / "opencode.json",
        )
    return (
        home
        / {
            "claude": ".claude.json",
            "pi": ".pi/agent/AGENTS.md",
            "opencode": ".config/opencode/opencode.json",
        }[host]
    )


def standard_codex_profile() -> bool:
    return host_config("codex").parent.resolve() == (Path.home() / ".codex").resolve()


def require_standard_profiles(target: str) -> None:
    if "codex" in selected_hosts(target) and not standard_codex_profile():
        raise RuntimeError(
            "Managed agent setup supports the standard ~/.codex profile; clear a custom CODEX_HOME before configuration. Skills-only installation supports custom destinations."
        )
    for host in selected_hosts(target):
        path = host_config(host)
        if host == "pi" or not path.is_file():
            continue
        if host == "codex":
            entry = tomllib.loads(path.read_text(encoding="utf-8")).get(
                "mcp_servers", {}
            ).get("serena", {})
        else:
            if path.suffix == ".jsonc" and not (TOOLS / "npm/package.json").is_file():
                continue  # Preview reports that JSONC validation awaits installation.
            data = read_host_json(path)
            container = (
                data.get("mcp", {})
                if host == "opencode"
                else data.get("mcpServers", {})
            )
            entry = container.get("servers", container).get("serena", {})
        environment = entry.get("environment" if host == "opencode" else "env", {})
        override = environment.get("SERENA_HOME", "").strip()
        if override and (
            not Path(override).is_absolute()
            or Path(override).resolve() != serena_home()
        ):
            raise RuntimeError(
                f"{host} has a different Serena home. Set SERENA_HOME to its existing "
                "absolute home before configuring, or deliberately remove that host override."
            )


def jsonc_document(path: Path, desired: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"text": path.read_text(encoding="utf-8-sig")}
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


def read_host_json(path: Path) -> dict[str, Any]:
    return (
        jsonc_document(path)["data"]
        if path.suffix == ".jsonc"
        else json.loads(path.read_text(encoding="utf-8-sig"))
    )


def existing_server(host: str, name: str) -> bool:
    path = host_config(host)
    if not path.exists():
        return False
    if host == "codex":
        return name in tomllib.loads(path.read_text(encoding="utf-8")).get(
            "mcp_servers", {}
        )
    return name in json.loads(path.read_text(encoding="utf-8-sig")).get(
        "mcpServers", {}
    )


def required_tool_paths() -> set[str]:
    receipt = TOOLS / "runtime.json"
    runtime = (
        json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
    )
    paths = [
        TOOLS / "bin",
        *(Path(value).parent for value in runtime.values() if value),
    ]
    return {os.path.normcase(os.path.normpath(str(path))) for path in paths}


def host_servers(host: str) -> dict[str, Any]:
    selected = servers()
    if host == "claude" and claude_plugin_enabled():
        selected.pop("cq", None)
    if host != "codex":
        for server in selected.values():
            server.pop("startup_timeout_sec", None)
        arguments = selected["serena"]["args"]
        arguments[arguments.index("--context") + 1] = (
            "claude-code" if host == "claude" else "ide"
        )
    return selected


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
    paths = tool_env()["PATH"].split(os.pathsep) + environment.get("PATH", "").split(
        os.pathsep
    )
    seen: set[str] = set()
    stable = []
    for entry in paths:
        key = os.path.normcase(os.path.normpath(entry))
        if entry and key not in seen:
            stable.append(entry)
            seen.add(key)
    environment.update(PATH=os.pathsep.join(stable), CQ_ADDR="")
    return update_file(path, json.dumps(settings, indent=2) + "\n", dry_run=dry_run)


def configure_pi(*, dry_run: bool = False) -> str:
    settings_path = Path.home() / ".pi/agent/settings.json"
    settings = (
        json.loads(settings_path.read_text(encoding="utf-8"))
        if settings_path.exists()
        else {}
    )
    prefix = settings.get("shellCommandPrefix", "").rstrip()
    local_prefix = "export CQ_ADDR='';"
    if not prefix.endswith(local_prefix):
        settings["shellCommandPrefix"] = (
            prefix + (" " if prefix.endswith(";") else "; ") if prefix else ""
        ) + local_prefix
    return update_file(
        settings_path, json.dumps(settings, indent=2) + "\n", dry_run=dry_run
    )


def preview(target: str) -> dict[str, Any]:
    require_standard_profiles(target)
    planned = []
    for host in selected_hosts(target):
        path = host_config(host)
        expected = host_servers(host)
        if host == "codex":
            action = merge_codex(path, expected, dry_run=True)
        elif host == "pi":
            action = configure_pi(dry_run=True)
        else:
            action = merge_json(path, expected, host, dry_run=True)
        environment_action = (
            configure_claude_environment(dry_run=True) if host == "claude" else None
        )
        planned.append(
            {
                "host": host,
                "config": str(path),
                "action": action,
                "managed_servers": list(expected) if host != "pi" else [],
                "environment_action": environment_action,
                "upstream_setup": "would run supported upstream installers; native plugin changes are host-dependent",
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
    assert spec is not None and spec.loader is not None
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    source = ROOT / "skills"
    dependencies = installer.dependency_manifest(source)
    validation = installer.validate_source(source, manifest=dependencies)
    sources = {name: source / name for name in installer.MANAGED_SKILLS}
    sources.update(
        {
            name: installer.external_cache() / name
            for name in installer.external_specs(dependencies)
        }
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
        roots = (
            [Path.home() / ".agents/skills", Path.home() / ".codex/skills"]
            if host == "codex"
            else [path]
        )
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
                f"{host} missing or changed installed skills: {', '.join(missing)}"
            )
        if conflicts:
            problems.append(
                f"{host} conflicting discovery copies: {', '.join(sorted(set(conflicts)))}"
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
    directory = Path.home() / (".codex" if host == "codex" else ".claude")
    return directory / (
        "hooks.json" if host == "codex" else "settings.json"
    ), directory / "hooks/gitnexus/gitnexus-hook.cjs"


def gitnexus_hook_launch(host: str) -> dict[str, Any]:
    _, hook = gitnexus_hook_paths(host)
    arguments = [
        Path(node_command()).as_posix(),
        (ROOT / "scripts/run_gitnexus_hook.mjs").as_posix(),
        (TOOLS / "gitnexus-indexes").as_posix(),
        hook.as_posix(),
        Path(tool_command("gitnexus")[1]).as_posix(),
    ]
    if host == "claude":
        return {"command": arguments[0], "args": arguments[1:]}
    script = "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in arguments)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    powershell = (
        Path(os.environ.get("SystemRoot", "C:/Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    ).as_posix()
    return {
        "command": shlex.join(arguments),
        "commandWindows": f"{powershell} -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded}",
    }


def gitnexus_owned_hooks(data: dict[str, Any], host: str) -> list[dict[str, Any]]:
    _, hook = gitnexus_hook_paths(host)
    owned = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            command = value.get("command", "")
            arguments = value.get("args", [])
            references = (
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
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(data.get("hooks", {}))
    return owned


def configure_gitnexus_hooks(host: str) -> None:
    if host not in {"codex", "claude"}:
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
                    if matcher in seen:
                        continue
                    seen.add(matcher)
                retained.append(hook)
            group["hooks"] = retained
        data["hooks"][event] = [group for group in groups if group.get("hooks")]
    update_file(path, json.dumps(data, indent=2) + "\n")


def configure(target: str) -> dict[str, Any]:
    require_standard_profiles(target)
    results = []
    missing = [
        name
        for name, spec in manifest()["tools"].items()
        if installed_version(name) != spec["version"]
    ]
    if missing:
        raise RuntimeError("Install pinned tools first: " + ", ".join(missing))
    serena = serena_configuration(apply=True)
    home = Path.home()
    for host in selected_hosts(target):
        upstream = []
        limitations = []
        paths = [host_config(host)]
        if host == "claude":
            paths.append(home / ".claude/settings.json")
        elif host == "codex":
            paths.append(host_config(host).parent / "AGENTS.md")
            paths.append(gitnexus_hook_paths(host)[0])
        elif host == "pi":
            paths.append(home / ".pi/agent/settings.json")
        else:
            paths.append(home / ".config/opencode/AGENTS.md")
        for path in paths:
            backup_configuration(path)
        # Register an absent server through upstream; preserve existing entries.
        client = "claude-code" if host == "claude" else host
        if host == "claude":
            configure_claude_environment()
        if (
            host == "codex" or (host == "claude" and shutil.which("claude"))
        ) and not existing_server(host, "serena"):
            try:
                upstream.append(
                    run(tool_command("serena") + ["setup", client], timeout=90)
                )
            except RuntimeError as error:
                if "not found or not functional" not in str(error):
                    raise
                limitations.append(
                    "Serena client setup unavailable; using documented manual MCP configuration"
                )
        if host != "pi" and manifest()["tools"]["gitnexus"].get(
            "integration_enabled", True
        ):
            config_paths = {host_config(host)}
            if host == "codex":
                config_paths.add(home / ".codex/config.toml")
            elif host == "opencode":
                config_paths.update(
                    home / ".config/opencode" / name
                    for name in ("opencode.json", "opencode.jsonc", "config.json")
                )
            originals = {
                path: path.read_text(encoding="utf-8")
                for path in config_paths
                if path.is_file()
            }
            for path in config_paths - set(paths):
                backup_configuration(path)
            try:
                upstream.append(
                    run(
                        tool_command("gitnexus")
                        + ["setup", "-c", "claude" if host == "claude" else host],
                        timeout=90,
                    )
                )
            finally:
                # Native setup owns bundled skills/hooks but replaces MCP entries.
                # Restore caller configuration before our preserving local merge.
                for path, original in originals.items():
                    update_file(path, original)
            configure_gitnexus_hooks(host)
        # Use cq's maintained skill/instruction installer. Claude's plugin route
        # needs Claude CLI; other hosts can be configured without their binaries.
        if host != "claude" or shutil.which("claude"):
            cq_config_path = host_config(host)
            cq_original_config = (
                cq_config_path.read_text(encoding="utf-8")
                if host == "codex" and cq_config_path.is_file()
                else None
            )
            try:
                upstream.append(
                    run(tool_command("cq") + ["install", "--target", host], timeout=90)
                )
            finally:
                # Restore only cq's entry so other settings edited during native
                # setup survive. The managed merge below applies local defaults.
                if cq_original_config is not None:
                    import tomlkit

                    current = cq_config_path.read_text(encoding="utf-8")
                    document = tomlkit.parse(current)
                    previous = tomlkit.parse(cq_original_config).get("mcp_servers", {})
                    configured = document.setdefault("mcp_servers", tomlkit.table())
                    if "cq" in previous:
                        configured["cq"] = previous["cq"]
                    else:
                        configured.pop("cq", None)
                    update_file(
                        cq_config_path,
                        tomlkit.dumps(document),
                        expected_digest=hashlib.sha256(current.encode("utf-8")).hexdigest(),
                    )
        else:
            limitations.append(
                "cq's Claude plugin installation requires Claude CLI; rerun agents:configure after installing that client"
            )
        selected = host_servers(host)
        if host == "codex":
            path = host_config(host)
            action = merge_codex(path, selected)
        elif host == "pi":
            # Pi uses cq's CLI mapping, not an invented MCP adapter.
            path = home / ".pi/agent/AGENTS.md"
            action = "configured CLI mapping"
            configure_pi()
        else:
            path = host_config(host)
            if host == "claude" and claude_plugin_enabled() and path.exists():
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                manual = data.get("mcpServers", {}).get("cq", {})
                if manual.get("command") == tool_command("cq")[0]:
                    settings_path = home / ".claude/settings.json"
                    settings = json.loads(settings_path.read_text(encoding="utf-8"))
                    environment = settings.setdefault("env", {})
                    for key, value in manual.get("env", {}).items():
                        if key not in {"PATH", "CQ_ADDR"}:
                            environment.setdefault(key, value)
                    update_file(settings_path, json.dumps(settings, indent=2) + "\n")
                    del data["mcpServers"]["cq"]
                    update_file(path, json.dumps(data, indent=2) + "\n")
                elif manual:
                    raise RuntimeError(
                        "An existing unmanaged Claude cq server conflicts with the cq plugin; preserve its settings and resolve that entry before configuring"
                    )
            action = merge_json(path, selected, host)
        results.append(
            {
                "host": host,
                "config": str(path),
                "action": action,
                "client_available": bool(shutil.which(host)),
                "upstream_installers": bool(upstream),
                "limitations": limitations,
                "note": "MCP servers configured; client connection and hook trust require verification"
                if host != "pi"
                else "cq CLI mapping; other CLIs available through Task",
            }
        )
    return {
        "serena": serena,
        "hosts": results,
        "disabled_integrations": [
            name
            for name, spec in manifest()["tools"].items()
            if spec.get("integration_enabled") is False
        ],
    }


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
        f"{t['tool']} version mismatch"
        for t in tools
        if t["installed"] != t["expected"]
    ]
    if serena_dependency_versions() != manifest()["tools"].get("serena", {}).get(
        "dependency_overrides", {}
    ):
        problems.append(
            "Serena security dependency versions do not match the reviewed overrides"
        )
    hosts = []
    for host in selected_hosts(target):
        home = Path.home()
        path = host_config(host)
        configured = path.is_file()
        container = {}
        if configured and host == "codex":
            container = tomllib.loads(path.read_text(encoding="utf-8")).get(
                "mcp_servers", {}
            )
        elif configured and host in {"claude", "opencode"}:
            data = read_host_json(path)
            container = (
                data.get("mcpServers", {}) if host == "claude" else data.get("mcp", {})
            )
            container = container.get("servers", container)
        if configured and host != "pi":
            expected = host_servers(host)
            for name, wanted in expected.items():
                actual = container.get(name, {})
                if any(key in actual for key in REMOTE_SERVER_FIELDS):
                    configured = False
                if (host == "opencode" and actual.get("type") != "local") or (
                    host != "opencode" and actual.get("type") not in {None, "stdio"}
                ):
                    configured = False
                command = actual.get("command")
                wanted_command = (
                    [wanted["command"], *wanted["args"]]
                    if host == "opencode"
                    else wanted["command"]
                )
                if (
                    command != wanted_command
                    or actual.get("enabled") is False
                    or actual.get("disabled") is True
                ):
                    configured = False
                if host != "opencode" and actual.get("args") != wanted["args"]:
                    configured = False
                environment = actual.get(
                    "environment" if host == "opencode" else "env", {}
                )
                if any(
                    environment.get(key) != value
                    for key, value in wanted.get("env", {}).items()
                    if key != "PATH"
                ):
                    configured = False
                actual_paths = {
                    os.path.normcase(os.path.normpath(value))
                    for value in environment.get("PATH", "").split(os.pathsep)
                    if value
                }
                if not required_tool_paths().issubset(actual_paths):
                    configured = False
            if (
                "gitnexus" in expected
                and host in {"codex", "claude"}
                and (host != "codex" or standard_codex_profile())
            ):
                hooks_path, hook_script = gitnexus_hook_paths(host)
                hook_data = (
                    json.loads(hooks_path.read_text(encoding="utf-8-sig"))
                    if hooks_path.is_file()
                    else {}
                )
                owned = gitnexus_owned_hooks(hook_data, host)
                if (
                    not hook_script.is_file()
                    or not owned
                    or any(
                        any(
                            hook.get(key) != value
                            for key, value in gitnexus_hook_launch(host).items()
                        )
                        for hook in owned
                    )
                ):
                    configured = False
            if host == "claude" and claude_plugin_enabled():
                settings = json.loads(
                    (home / ".claude/settings.json").read_text(encoding="utf-8")
                )
                if "cq" in container or settings.get("env", {}).get("CQ_ADDR") != "":
                    configured = False
        elif configured:
            text = path.read_text(encoding="utf-8")
            settings_path = home / ".pi/agent/settings.json"
            settings = (
                json.loads(settings_path.read_text(encoding="utf-8"))
                if settings_path.exists()
                else {}
            )
            cq_block = re.search(r"<!-- cq:start -->(.*?)<!-- cq:end -->", text, re.S)
            configured = bool(
                cq_block
                and f"The cq binary is: `{tool_command('cq')[0]}`." in cq_block.group(1)
            ) and settings.get("shellCommandPrefix", "").rstrip().endswith(
                "export CQ_ADDR='';"
            )
        if host == "codex" and not standard_codex_profile():
            configured = False
            problems.append(
                "Managed Codex integrations require the standard ~/.codex profile"
            )
        if not configured:
            problems.append(f"{host} integration not configured")
        hosts.append(
            {
                "host": host,
                "configured": configured,
                "client_available": bool(shutil.which(host)),
                "connection_verified": False,
            }
        )
    skills = skill_health(target)
    problems.extend(skills["problems"])
    serena = serena_configuration()
    if not serena["configured"]:
        problems.append("Serena dashboard preferences do not match managed settings")
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
        "note": "Configuration checks do not establish live host connections or trusted hooks.",
    }


def emit(result: dict[str, Any], output: str) -> None:
    if output == "json":
        print(json.dumps(result, indent=2))
        return
    if result.get("error"):
        print(f"{result['command']}: {result['error']}")
        return
    if result.get("lockfile"):
        print(f"npm lock: {result['action']}; {result['lockfile']}")
    if result.get("serena"):
        serena = result["serena"]
        print(
            "Serena preferences: "
            + serena.get("action", f"configured={serena['configured']}")
        )
    for tool in result.get("tools", []):
        selected = tool.get("version", tool.get("pinned", tool.get("expected")))
        observed = tool.get("installed", tool.get("version"))
        update = f"; available {tool['latest']}" if "latest" in tool else ""
        print(f"{tool['tool']}: selected {selected}; installed {observed}{update}")
    for host in result.get("hosts", []):
        if isinstance(host, str):
            print(f"host: {host}")
        else:
            state = host.get("action", f"configured={host.get('configured')}")
            print(f"{host['host']}: {state}")
            for limitation in host.get("limitations", []):
                print(f"  {limitation}")
    for host in result.get("skills", {}).get("hosts", []):
        print(
            f"{host['host']} skills: {host['expected_count']} expected; digest_verified={host['digest_verified']}"
        )
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
    parser.add_argument("--target", choices=("all", *HOSTS), default="all")
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
                raise RuntimeError(
                    f"{args.tool} is installed but disabled pending license suitability; see {spec.get('license_url')}"
                )
            if installed_version(args.tool) != spec["version"]:
                raise RuntimeError(f"Install the pinned {args.tool} first")
            arguments = (
                args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
            )
            cwd = Path(os.environ.get("LLMS_CALLER_CWD", str(Path.cwd())))
            return subprocess.run(
                tool_command(args.tool) + arguments, cwd=cwd, env=tool_env()
            ).returncode
        if args.command == "install":
            result = install()
        elif args.command == "lock":
            result = lock_npm_tools()
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
                            if release["tag_name"].startswith("cli/v")
                            and not release["prerelease"]
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
