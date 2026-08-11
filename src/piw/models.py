"""Typed domain models shared by piw subsystems."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Self, cast


class OutputFormat(StrEnum):
    """Supported command output formats."""

    TEXT = "text"
    JSON = "json"


class ThinkingLevel(StrEnum):
    """Thinking levels accepted by Pi."""

    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class TaskPhase(StrEnum):
    """Locally observed task lifecycle phases."""

    RUNNING = "running"
    STOPPED = "stopped"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Docker Sandbox defaults."""

    profile: str | None = None
    read_only_refs: tuple[Path, ...] = ()
    mcp_servers: tuple[str, ...] = ()
    mcp_gateway_url: str = "http://mcp-gateway.docker.internal/mcp"
    cpus: int = 0
    memory: str | None = None
    timeout_seconds: int = 600


@dataclass(frozen=True, slots=True)
class PiConfig:
    """Pi runtime defaults."""

    package: str = "@earendil-works/pi-coding-agent@0.84.0"
    model: str | None = None
    thinking: ThinkingLevel = ThinkingLevel.HIGH
    extensions: tuple[str, ...] = ()
    models_file: Path | None = None
    settings_file: Path | None = None
    skill_paths: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class TemplateConfig:
    """Reusable template defaults."""

    prefix: str = "piw-pi"
    node_version: str = "v22.19.0"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Fully parsed piw configuration."""

    config_version: int = 1
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    pi: PiConfig = field(default_factory=PiConfig)
    template: TemplateConfig = field(default_factory=TemplateConfig)


@dataclass(frozen=True, slots=True)
class EffectiveTaskConfig:
    """Resolved settings used to create or resume one task."""

    repo: Path
    base_ref: str
    branch: str
    read_only_refs: tuple[Path, ...]
    skill_paths: tuple[Path, ...]
    model: str | None
    thinking: ThinkingLevel
    mcp_servers: tuple[str, ...]
    profile: str | None
    extensions: tuple[str, ...]
    models_file: Path | None
    settings_file: Path | None
    cpus: int
    memory: str | None
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """Non-secret task metadata persisted on the host."""

    schema_version: int
    task: str
    sandbox: str
    repo: str
    branch: str
    base_commit: str
    template: str
    model: str | None
    thinking: str
    mcp_servers: tuple[str, ...]
    read_only_refs: tuple[str, ...]
    skill_paths: tuple[str, ...]
    profile: str | None
    created_at: str
    last_used_at: str
    session_started: bool = False

    def to_json_object(self) -> dict[str, object]:
        """Return a JSON-safe representation."""

        return asdict(self)

    @classmethod
    def from_json_object(cls, value: object) -> Self:
        """Validate and decode a task record from JSON."""

        if not isinstance(value, dict):
            raise TypeError("task state must be a JSON object")
        mapping = cast("dict[object, object]", value)
        if not all(isinstance(key, str) for key in mapping):
            raise TypeError("task state field names must be strings")
        fields = cast("dict[str, object]", mapping)

        def required_string(key: str) -> str:
            item = fields.get(key)
            if not isinstance(item, str):
                raise TypeError(f"task state field {key!r} has the wrong type")
            return item

        schema_version = fields.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise TypeError("task state field 'schema_version' has the wrong type")
        session_started = fields.get("session_started", False)
        if not isinstance(session_started, bool):
            raise TypeError("task state field 'session_started' has the wrong type")

        def optional_string(key: str) -> str | None:
            item = fields.get(key)
            if item is not None and not isinstance(item, str):
                raise TypeError(f"task state field {key!r} has the wrong type")
            return item

        def string_tuple(key: str) -> tuple[str, ...]:
            item = fields.get(key, [])
            if not isinstance(item, list):
                raise TypeError(f"task state field {key!r} has the wrong type")
            values = cast("list[object]", item)
            if not all(isinstance(part, str) for part in values):
                raise TypeError(f"task state field {key!r} has the wrong type")
            return tuple(cast("list[str]", values))

        thinking = required_string("thinking")
        try:
            ThinkingLevel(thinking)
        except ValueError as error:
            raise TypeError("task state field 'thinking' has an unsupported value") from error

        return cls(
            schema_version=schema_version,
            task=required_string("task"),
            sandbox=required_string("sandbox"),
            repo=required_string("repo"),
            branch=required_string("branch"),
            base_commit=required_string("base_commit"),
            template=required_string("template"),
            model=optional_string("model"),
            thinking=thinking,
            mcp_servers=string_tuple("mcp_servers"),
            read_only_refs=string_tuple("read_only_refs"),
            skill_paths=string_tuple("skill_paths"),
            profile=optional_string("profile"),
            created_at=required_string("created_at"),
            last_used_at=required_string("last_used_at"),
            session_started=session_started,
        )


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured subprocess result."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One prerequisite check."""

    name: str
    status: str
    message: str
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class OutputEnvelope:
    """Stable JSON envelope emitted by every command."""

    schema_version: int
    command: str
    ok: bool
    data: object
    warnings: tuple[str, ...] = ()
    error: dict[str, object] | None = None

    def to_json_object(self) -> dict[str, object]:
        """Return a JSON-safe dictionary."""

        return asdict(self)
