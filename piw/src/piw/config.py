"""Strict TOML configuration loading and rendering."""

import os
import re
import tomllib
from pathlib import Path
from typing import Final, cast

from piw.errors import ExitCode, PiwError
from piw.models import (
    AppConfig,
    PiConfig,
    SandboxConfig,
    SandboxSecretConfig,
    TemplateConfig,
    ThinkingLevel,
)

CONFIG_VERSION: Final = 1
_ROOT_KEYS: Final = frozenset({"config_version", "sandbox", "pi", "template"})
_SANDBOX_KEYS: Final = frozenset(
    {
        "profile",
        "read_only_refs",
        "cpus",
        "memory",
        "timeout_seconds",
        "secrets",
    }
)
_SECRET_KEYS: Final = frozenset({"source_env", "sandbox_env", "hosts", "placeholder", "required"})
_PI_KEYS: Final = frozenset(
    {
        "package",
        "model",
        "thinking",
        "extensions",
        "models_file",
        "settings_file",
        "mcp_file",
        "skill_paths",
    }
)
_TEMPLATE_KEYS: Final = frozenset({"prefix", "node_version"})
_TEMPLATE_PREFIX_RE: Final = re.compile(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*")
_NODE_VERSION_RE: Final = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
_ENV_NAME_RE: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


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
    """Build a configuration error with piw's standard exit code and kind."""

    return PiwError(message, code=ExitCode.CONFIG, kind="invalid_config")


def _table(parent: dict[str, object], key: str) -> dict[str, object]:
    """Read a TOML child table, treating an omitted table as empty."""

    value = parent.get(key, {})
    if not isinstance(value, dict):
        raise _config_error(f"{key!r} must be a TOML table")
    return cast("dict[str, object]", value)


def _reject_unknown(table: dict[str, object], allowed: frozenset[str], label: str) -> None:
    """Reject misspelled or unsupported keys in a configuration table."""

    unknown = sorted(set(table) - allowed)
    if unknown:
        joined = ", ".join(unknown)
        raise _config_error(f"unknown {label} configuration field(s): {joined}")


def _optional_string(table: dict[str, object], key: str) -> str | None:
    """Read an optional non-empty string from a configuration table."""

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
    """Read a non-empty string, using the supplied default when absent."""

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
    """Read an integer that meets the field's minimum value."""

    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _config_error(f"{key!r} must be an integer greater than or equal to {minimum}")
    return value


def _boolean(table: dict[str, object], key: str, default: bool) -> bool:
    """Read a boolean, using the supplied default when absent."""

    value = table.get(key, default)
    if not isinstance(value, bool):
        raise _config_error(f"{key!r} must be a boolean")
    return value


def _string_tuple(table: dict[str, object], key: str) -> tuple[str, ...]:
    """Read a duplicate-free TOML string array as a tuple."""

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
    """Expand environment and user markers in a configured path."""

    return Path(os.path.expandvars(value)).expanduser().resolve(strict=False)


def _path_tuple(table: dict[str, object], key: str) -> tuple[Path, ...]:
    """Read a configured string array and resolve each entry as a path."""

    return tuple(_path(item) for item in _string_tuple(table, key))


def _optional_path(table: dict[str, object], key: str) -> Path | None:
    """Read and resolve an optional configured path."""

    value = _optional_string(table, key)
    return _path(value) if value is not None else None


def _sandbox_secret(value: object, index: int) -> SandboxSecretConfig:
    """Validate one sandbox secret declaration from the TOML array."""

    label = f"sandbox.secrets[{index}]"
    if not isinstance(value, dict):
        raise _config_error(f"{label} must be a TOML table")

    declaration = cast("dict[str, object]", value)
    _reject_unknown(declaration, _SECRET_KEYS, label)

    source_env = _string(declaration, "source_env", "")
    sandbox_env = _string(declaration, "sandbox_env", "")
    if not _ENV_NAME_RE.fullmatch(source_env):
        raise _config_error(f"'{label}.source_env' must be a valid environment name")
    if not _ENV_NAME_RE.fullmatch(sandbox_env):
        raise _config_error(f"'{label}.sandbox_env' must be a valid environment name")

    hosts = _string_tuple(declaration, "hosts")
    if not hosts:
        raise _config_error(f"'{label}.hosts' must contain at least one host")
    if any(
        "://" in host or "/" in host or any(character.isspace() for character in host)
        for host in hosts
    ):
        raise _config_error(
            f"'{label}.hosts' entries must be host patterns without schemes or paths"
        )

    placeholder = _string(declaration, "placeholder", "piw-{rand}")
    if placeholder.count("{rand}") != 1 or any(character.isspace() for character in placeholder):
        raise _config_error(
            f"'{label}.placeholder' must contain exactly one '{{rand}}' and no whitespace"
        )

    return SandboxSecretConfig(
        source_env=source_env,
        sandbox_env=sandbox_env,
        hosts=hosts,
        placeholder=placeholder,
        required=_boolean(declaration, "required", True),
    )


def _sandbox_secrets(table: dict[str, object]) -> tuple[SandboxSecretConfig, ...]:
    """Validate sandbox secret declarations and return their typed form."""

    value = table.get("secrets", [])
    if not isinstance(value, list):
        raise _config_error("'sandbox.secrets' must be an array of TOML tables")

    declarations = tuple(
        _sandbox_secret(item, index) for index, item in enumerate(cast("list[object]", value))
    )
    sandbox_envs = [declaration.sandbox_env for declaration in declarations]
    if len(sandbox_envs) != len(set(sandbox_envs)):
        raise _config_error("'sandbox.secrets' must not contain duplicate sandbox_env values")

    return declarations


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
        cpus=_integer(sandbox_table, "cpus", 0, minimum=0),
        memory=_optional_string(sandbox_table, "memory"),
        timeout_seconds=_integer(sandbox_table, "timeout_seconds", 600, minimum=1),
        secrets=_sandbox_secrets(sandbox_table),
    )
    pi = PiConfig(
        package=_string(pi_table, "package", PiConfig().package),
        model=_optional_string(pi_table, "model"),
        thinking=thinking,
        extensions=_string_tuple(pi_table, "extensions"),
        models_file=_optional_path(pi_table, "models_file"),
        settings_file=_optional_path(pi_table, "settings_file"),
        mcp_file=_optional_path(pi_table, "mcp_file"),
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
            "cpus": config.sandbox.cpus,
            "memory": config.sandbox.memory,
            "timeout_seconds": config.sandbox.timeout_seconds,
            "secrets": [
                {
                    "source_env": declaration.source_env,
                    "sandbox_env": declaration.sandbox_env,
                    "hosts": list(declaration.hosts),
                    "placeholder": declaration.placeholder,
                    "required": declaration.required,
                }
                for declaration in config.sandbox.secrets
            ],
        },
        "pi": {
            "package": config.pi.package,
            "model": config.pi.model,
            "thinking": config.pi.thinking.value,
            "extensions": list(config.pi.extensions),
            "models_file": str(config.pi.models_file) if config.pi.models_file else None,
            "settings_file": str(config.pi.settings_file) if config.pi.settings_file else None,
            "mcp_file": str(config.pi.mcp_file) if config.pi.mcp_file else None,
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
cpus = 0
# memory = "8g"
timeout_seconds = 600

# Synchronize a host environment variable into Docker Sandboxes without
# putting its value in this file. Add one [[sandbox.secrets]] table per value.
# [[sandbox.secrets]]
# source_env = "EXAMPLE_API_KEY"
# sandbox_env = "EXAMPLE_API_KEY"
# hosts = ["api.example.com"]
# placeholder = "example-{rand}"
# required = true

[pi]
package = "@earendil-works/pi-coding-agent@0.84.0"
# model = "provider/model"
thinking = "high"
extensions = []
# models_file = "~/.pi/agent/models.json"
# settings_file = "~/.pi/agent/settings.json"
# mcp_file = "~/.pi/agent/mcp.json"
skill_paths = []

[template]
prefix = "piw-pi"
node_version = "v22.19.0"
"""
