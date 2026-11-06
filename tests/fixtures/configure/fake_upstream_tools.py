"""Stand-ins for the upstream installers and version probes that setup runs.

The end-to-end configure test (tests/test_configure_end_to_end.py) puts small
wrapper scripts where the real tools would be, and each wrapper runs this file:

    python fake_upstream_tools.py <tool> <path of the wrapper> <arguments...>

The tools are serena, serena-hooks, serena-python (Serena's environment
Python), cq, ast-grep and gitnexus. Each one changes files under $HOME the way
the real tool does when setup runs it, and prints the version the manifest
pins. A command this file does not know exits with status 2, so a new call
from setup shows up as a test failure instead of being ignored.

LLMS_FAKE_MANIFEST names the agent-dependencies.json whose pins are reported.
LLMS_FAKE_SERENA_SETUP=fail makes `serena setup` fail the way a missing client does.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import tomlkit

HOME = Path.home()
OPENCODE_DIR = HOME / ".config/opencode"
SERENA_TEMPLATE = Path(__file__).with_name("serena_config_template.yml")
CQ_INSTALL_HOSTS = {"claude", "codex", "opencode", "pi"}
GITNEXUS_SETUP_HOSTS = {"claude", "codex", "opencode"}
SERENA_CLIENTS = {"codex", "claude-code"}
CQ_BLOCK = re.compile(r"<!-- cq:start -->.*?<!-- cq:end -->\n?", re.DOTALL)


def pinned(name: str) -> dict[str, Any]:
    manifest = json.loads(Path(os.environ["LLMS_FAKE_MANIFEST"]).read_text(encoding="utf-8"))
    return manifest["tools"][name]


def write_text(path: Path, text: str) -> None:
    """Write a file; a new one is mode 0644 whatever the umask, an old one keeps its mode."""
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if not existed:
        path.chmod(0o644)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2) + "\n")


def set_server(host: str, name: str, command: list[str]) -> None:
    """Replace one MCP server entry in the host's config, as upstream installers do."""
    if host == "codex":
        path = HOME / ".codex/config.toml"
        document: Any = tomlkit.parse(path.read_text(encoding="utf-8") if path.exists() else "")
        servers = document.setdefault("mcp_servers", tomlkit.table())
        entry = tomlkit.table()
        entry["command"] = command[0]
        entry["args"] = command[1:]
        servers[name] = entry
        write_text(path, tomlkit.dumps(document))
    elif host == "opencode":
        # With no opencode.json yet, upstream writes one that holds only servers.
        path = OPENCODE_DIR / "opencode.json"
        data = read_json(path) or {"$schema": "https://opencode.ai/config.json"}
        data.setdefault("mcp", {})[name] = {"type": "local", "command": command}
        write_json(path, data)
    else:
        path = HOME / ".claude.json"
        data = read_json(path)
        data.setdefault("mcpServers", {})[name] = {
            "type": "stdio",
            "command": command[0],
            "args": command[1:],
        }
        write_json(path, data)


def add_gitnexus_hooks(host: str) -> None:
    """Install the hook script and append shell-form hooks upstream does not find yet.

    Upstream recognizes only a shell-form command that names the hook script,
    so a hook that setup rewrote to the exec form is registered a second time.
    """
    directory = HOME / (".codex" if host == "codex" else ".claude")
    script = directory / "hooks/gitnexus/gitnexus-hook.cjs"
    write_text(script, "// Stand-in for the upstream GitNexus hook.\n")
    path = directory / ("hooks.json" if host == "codex" else "settings.json")
    data = read_json(path)
    events = data.setdefault("hooks", {})
    for event, matcher in (("PreToolUse", "Grep|Glob|Bash"), ("PostToolUse", "Bash")):
        groups = events.setdefault(event, [])
        known = any(
            str(script) in hook.get("command", "")
            for group in groups
            for hook in group.get("hooks", [])
        )
        if not known:
            groups.append(
                {
                    "matcher": matcher,
                    "hooks": [
                        {
                            "type": "command",
                            "timeout": 10,
                            "statusMessage": "Checking GitNexus index freshness...",
                            "command": f'node "{script}"',
                        }
                    ],
                }
            )
    write_json(path, data)


def add_cq_instructions(host: str, binary: str) -> None:
    """Write or refresh the cq block in the host's instructions file."""
    path = {
        "codex": HOME / ".codex/AGENTS.md",
        "opencode": OPENCODE_DIR / "AGENTS.md",
        "pi": HOME / ".pi/agent/AGENTS.md",
    }[host]
    block = (
        "<!-- cq:start -->\n## cq\n\n"
        "Ask cq before you start and share what you learn.\n"
        f"The cq binary is: `{binary}`.\n"
        "<!-- cq:end -->\n"
    )
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if CQ_BLOCK.search(old):
        text = CQ_BLOCK.sub(lambda _: block, old)
    else:
        text = old.rstrip("\n") + "\n\n" + block if old else block
    write_text(path, text)


def serena(wrapper: str, args: list[str]) -> int:
    if args == ["--version"]:
        print(f"serena {pinned('serena')['version']}")
    elif len(args) == 2 and args[0] == "setup" and args[1] in SERENA_CLIENTS:
        if os.environ.get("LLMS_FAKE_SERENA_SETUP") == "fail":
            print("serena: client not found or not functional")
            return 1
        client = "codex" if args[1] == "codex" else "claude"
        set_server(client, "serena", [wrapper, "start-mcp-server", "--context", args[1]])
        print(f"serena registered with {args[1]}")
    else:
        return 2
    return 0


def serena_hooks(args: list[str]) -> int:
    if args[:1] in (["activate"], ["remind"], ["cleanup"]):
        return 0
    return 2


def cq(wrapper: str, args: list[str]) -> int:
    if args == ["--version"]:
        print(f"cq version {pinned('cq')['version']}")
    elif len(args) == 3 and args[:2] == ["install", "--target"] and args[2] in CQ_INSTALL_HOSTS:
        host = args[2]
        # Claude gets cq as a plugin, which this stand-in leaves to the Claude CLI.
        if host != "claude":
            add_cq_instructions(host, wrapper)
        if host != "pi":
            set_server(host, "cq", [wrapper, "mcp"])
        print(f"cq installed for {host}")
    else:
        return 2
    return 0


def ast_grep(args: list[str]) -> int:
    if args == ["--version"]:
        print(f"ast-grep {pinned('ast-grep')['version']}")
        return 0
    return 2


def gitnexus(args: list[str]) -> int:
    if args == ["--version"]:
        print(pinned("gitnexus")["version"])
    elif len(args) == 3 and args[:2] == ["setup", "-c"] and args[2] in GITNEXUS_SETUP_HOSTS:
        host = args[2]
        # OpenCode is handled by the Node entry (fake_gitnexus_cli.js), which edits an
        # existing config in place. Upstream writes nothing here when none exists.
        if host != "opencode":
            set_server(host, "gitnexus", ["npx", "-y", "gitnexus@latest", "mcp"])
            add_gitnexus_hooks(host)
        print(f"gitnexus set up for {host}")
    else:
        return 2
    return 0


def parse_yaml_value(text: str) -> Any:
    if text in {"true", "false"}:
        return text == "true"
    return text


def render_serena_config(settings_json: str, config_path: str) -> int:
    """Answer render_serena_config.py's call: current values, new text, old digest."""
    defaults = json.loads(settings_json)
    path = Path(config_path)
    original = (path if path.is_file() else SERENA_TEMPLATE).read_text(encoding="utf-8")
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest() if path.is_file() else ""
    lines = original.splitlines()
    values: dict[str, Any] = {}
    for line in lines:
        key, separator, value = line.partition(": ")
        if separator and not line.startswith("#"):
            values[key] = parse_yaml_value(value)
    current = {key: values.get(key) for key in defaults}
    text = original
    if current != defaults:
        for key, value in defaults.items():
            rendered = f"{key}: {str(value).lower() if isinstance(value, bool) else value}"
            if key in values:
                lines = [rendered if line.startswith(key + ": ") else line for line in lines]
            else:
                lines.append(rendered)
        text = "\n".join(lines) + "\n"
    print(
        json.dumps(
            {
                "config": str(path),
                "current": current,
                "settings": defaults,
                "text": text,
                "original_digest": digest,
            }
        )
    )
    return 0


def serena_python(args: list[str]) -> int:
    """Answer the two kinds of call setup makes: a `-c` version probe or the config renderer."""
    if args[:1] == ["-c"]:
        # One probe prints Serena's own version; the other prints a JSON map of package versions.
        if "json" in args[1]:
            print(json.dumps(pinned("serena").get("dependency_overrides", {})))
        else:
            print(pinned("serena")["version"])
        return 0
    if len(args) == 3 and args[0].endswith("render_serena_config.py"):
        return render_serena_config(args[1], args[2])
    return 2


def main(argv: list[str]) -> int:
    tool, wrapper, args = argv[0], argv[1], argv[2:]
    if tool == "serena":
        status = serena(wrapper, args)
    elif tool == "serena-hooks":
        status = serena_hooks(args)
    elif tool == "serena-python":
        status = serena_python(args)
    elif tool == "cq":
        status = cq(wrapper, args)
    elif tool == "ast-grep":
        status = ast_grep(args)
    elif tool == "gitnexus":
        status = gitnexus(args)
    else:
        status = 2
    if status == 2:
        print(f"fake {tool}: unexpected arguments {args}", file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
