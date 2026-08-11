"""Strict TOML configuration loading and rendering."""

import os
import re
import tomllib
from pathlib import Path
from typing import Final, cast

from piw.errors import ExitCode, PiwError
from piw.models import AppConfig, PiConfig, SandboxConfig, TemplateConfig, ThinkingLevel

CONFIG_VERSION: Final = 1
_ROOT_KEYS: Final = frozenset({"config_version", "sandbox", "pi", "template"})
_SANDBOX_KEYS: Final = frozenset(
    {
        "profile",
        "read_only_refs",
        "mcp_servers",
        "mcp_gateway_url",
        "cpus",
        "memory",
        "timeout_seconds",
    }
)
_PI_KEYS: Final = frozenset(
    {
        "package",
        "model",
        "thinking",
        "extensions",
        "models_file",
        "settings_file",
        "skill_paths",
    }
)
_TEMPLATE_KEYS: Final = frozenset({"prefix", "node_version"})
_TEMPLATE_PREFIX_RE: Final = re.compile(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*")
_NODE_VERSION_RE: Final = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")


def config_home() -> Path:
    """Return piw's XDG configuration directory."""

    root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return root.expanduser() / "piw"


def state_home() -> Path:
    """Return piw's XDG state directory."""

    root = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    return root.expanduser() / "piw"


def cache_home() -> Path:
    """Return piw's XDG cache directory."""

    root = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return root.expanduser() / "piw"


def default_config_path() -> Path:
    """Return the default user configuration file."""

    return config_home() / "config.toml"


def _config_error(message: str) -> PiwError:
    return PiwError(message, code=ExitCode.CONFIG, kind="invalid_config")


def _table(parent: dict[str, object], key: str) -> dict[str, object]:
    value = parent.get(key, {})
    if not isinstance(value, dict):
        raise _config_error(f"{key!r} must be a TOML table")
    return cast("dict[str, object]", value)


def _reject_unknown(table: dict[str, object], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        joined = ", ".join(unknown)
        raise _config_error(f"unknown {label} configuration field(s): {joined}")


def _optional_string(table: dict[str, object], key: str) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _config_error(f"{key!r} must be a non-empty string when provided")
    return value.strip()


def _string(
    table: dict[str, object],
    key: str,
    default: str,
) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise _config_error(f"{key!r} must be a non-empty string")
    return value.strip()


def _integer(
    table: dict[str, object],
    key: str,
    default: int,
    *,
    minimum: int,
) -> int:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _config_error(f"{key!r} must be an integer greater than or equal to {minimum}")
    return value


def _string_tuple(table: dict[str, object], key: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list):
        raise _config_error(f"{key!r} must be an array of strings")
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise _config_error(f"{key!r} must be an array of strings")
    strings = cast("list[str]", items)
    cleaned = tuple(item.strip() for item in strings if item.strip())
    if len(cleaned) != len(set(cleaned)):
        raise _config_error(f"{key!r} must not contain duplicate values")
    return cleaned


def _path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser().resolve(strict=False)


def _path_tuple(table: dict[str, object], key: str) -> tuple[Path, ...]:
    return tuple(_path(item) for item in _string_tuple(table, key))


def _optional_path(table: dict[str, object], key: str) -> Path | None:
    value = _optional_string(table, key)
    return _path(value) if value is not None else None


def parse_config(value: object) -> AppConfig:
    """Parse a decoded TOML object into a strongly typed configuration."""

    if not isinstance(value, dict):
        raise _config_error("configuration root must be a TOML table")
    root = cast("dict[str, object]", value)
    _reject_unknown(root, _ROOT_KEYS, "root")

    version = root.get("config_version", CONFIG_VERSION)
    if isinstance(version, bool) or not isinstance(version, int):
        raise _config_error("'config_version' must be an integer")
    if version != CONFIG_VERSION:
        raise _config_error(
            f"unsupported config_version {version}; this piw release supports {CONFIG_VERSION}"
        )

    sandbox_table = _table(root, "sandbox")
    pi_table = _table(root, "pi")
    template_table = _table(root, "template")
    _reject_unknown(sandbox_table, _SANDBOX_KEYS, "sandbox")
    _reject_unknown(pi_table, _PI_KEYS, "pi")
    _reject_unknown(template_table, _TEMPLATE_KEYS, "template")

    thinking_value = _string(pi_table, "thinking", ThinkingLevel.HIGH.value)
    try:
        thinking = ThinkingLevel(thinking_value)
    except ValueError as error:
        choices = ", ".join(level.value for level in ThinkingLevel)
        raise _config_error(f"'thinking' must be one of: {choices}") from error

    sandbox = SandboxConfig(
        profile=_optional_string(sandbox_table, "profile"),
        read_only_refs=_path_tuple(sandbox_table, "read_only_refs"),
        mcp_servers=_string_tuple(sandbox_table, "mcp_servers"),
        mcp_gateway_url=_string(
            sandbox_table,
            "mcp_gateway_url",
            SandboxConfig().mcp_gateway_url,
        ),
        cpus=_integer(sandbox_table, "cpus", 0, minimum=0),
        memory=_optional_string(sandbox_table, "memory"),
        timeout_seconds=_integer(sandbox_table, "timeout_seconds", 600, minimum=1),
    )
    pi = PiConfig(
        package=_string(pi_table, "package", PiConfig().package),
        model=_optional_string(pi_table, "model"),
        thinking=thinking,
        extensions=_string_tuple(pi_table, "extensions"),
        models_file=_optional_path(pi_table, "models_file"),
        settings_file=_optional_path(pi_table, "settings_file"),
        skill_paths=_path_tuple(pi_table, "skill_paths"),
    )
    template_prefix = _string(template_table, "prefix", TemplateConfig().prefix)
    if not _TEMPLATE_PREFIX_RE.fullmatch(template_prefix):
        raise _config_error(
            "'template.prefix' must be a lowercase container image name without separators "
            "at either end"
        )
    node_version = _string(template_table, "node_version", TemplateConfig().node_version)
    if not _NODE_VERSION_RE.fullmatch(node_version):
        raise _config_error("'node_version' must be an exact release such as v22.19.0")
    template = TemplateConfig(prefix=template_prefix, node_version=node_version)
    return AppConfig(config_version=version, sandbox=sandbox, pi=pi, template=template)


def load_config(path: Path | None = None) -> AppConfig:
    """Load a config file, returning neutral defaults when it does not exist."""

    config_path = (path or default_config_path()).expanduser()
    if not config_path.exists():
        return AppConfig()
    try:
        with config_path.open("rb") as handle:
            decoded = cast("object", tomllib.load(handle))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise _config_error(f"cannot read {config_path}: {error}") from error
    return parse_config(decoded)


def config_as_object(config: AppConfig) -> dict[str, object]:
    """Return the resolved config as a JSON-safe object."""

    return {
        "config_version": config.config_version,
        "sandbox": {
            "profile": config.sandbox.profile,
            "read_only_refs": [str(path) for path in config.sandbox.read_only_refs],
            "mcp_servers": list(config.sandbox.mcp_servers),
            "mcp_gateway_url": config.sandbox.mcp_gateway_url,
            "cpus": config.sandbox.cpus,
            "memory": config.sandbox.memory,
            "timeout_seconds": config.sandbox.timeout_seconds,
        },
        "pi": {
            "package": config.pi.package,
            "model": config.pi.model,
            "thinking": config.pi.thinking.value,
            "extensions": list(config.pi.extensions),
            "models_file": str(config.pi.models_file) if config.pi.models_file else None,
            "settings_file": str(config.pi.settings_file) if config.pi.settings_file else None,
            "skill_paths": [str(path) for path in config.pi.skill_paths],
        },
        "template": {
            "prefix": config.template.prefix,
            "node_version": config.template.node_version,
        },
    }


def default_config_text() -> str:
    """Render a neutral, documented starter configuration."""

    return """# piw configuration (schema version 1)
# Provider, company, and workstation-specific settings belong only in this file.
config_version = 1

[sandbox]
# profile = "developer"
read_only_refs = []
mcp_servers = []
mcp_gateway_url = "http://mcp-gateway.docker.internal/mcp"
cpus = 0
# memory = "8g"
timeout_seconds = 600

[pi]
package = "@earendil-works/pi-coding-agent@0.84.0"
# model = "provider/model"
thinking = "high"
extensions = []
# models_file = "~/.pi/agent/models.json"
# settings_file = "~/.pi/agent/settings.json"
skill_paths = []

[template]
prefix = "piw-pi"
node_version = "v22.19.0"
"""
