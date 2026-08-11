"""Typed domain models shared by piw subsystems."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final, Self, cast

_SHA256_HEX_LENGTH: Final = 64
_CURRENT_SESSION_SCHEMA: Final = 2


class OutputFormat(StrEnum):
    """Supported command output formats."""

    TEXT = "text"
    JSON = "json"
    YAML = "yaml"


class HostChangesPolicy(StrEnum):
    """How branch creation handles uncommitted host repository changes."""

    FAIL = "fail"
    IGNORE = "ignore"
    CARRY = "carry"


class BranchMode(StrEnum):
    """Whether a branch session creates or adopts its Git branch."""

    NEW = "new"
    EXISTING = "existing"


class AttachMode(StrEnum):
    """How Pi chooses a conversation when attaching to a sandbox."""

    CONTINUE = "continue"
    NEW = "new"
    SELECT = "select"


class ThinkingLevel(StrEnum):
    """Thinking levels accepted by Pi."""

    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class SandboxPhase(StrEnum):
    """Locally observed sandbox lifecycle phases."""

    RUNNING = "running"
    STOPPED = "stopped"
    MISSING = "missing"
    UNKNOWN = "unknown"


class SessionKind(StrEnum):
    """Workspace types managed by piw."""

    BRANCH = "branch"
    CHAT = "chat"


@dataclass(frozen=True, slots=True)
class SandboxSecretConfig:
    """One host environment variable synchronized into Docker Sandboxes."""

    source_env: str
    sandbox_env: str
    hosts: tuple[str, ...]
    placeholder: str = "piw-{rand}"
    required: bool = True


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Docker Sandbox defaults."""

    profile: str | None = None
    read_only_refs: tuple[Path, ...] = ()
    cpus: int = 0
    memory: str | None = None
    timeout_seconds: int = 600
    secrets: tuple[SandboxSecretConfig, ...] = ()


@dataclass(frozen=True, slots=True)
class PiConfig:
    """Pi runtime defaults."""

    package: str = "@earendil-works/pi-coding-agent@0.84.0"
    model: str | None = None
    thinking: ThinkingLevel = ThinkingLevel.HIGH
    extensions: tuple[str, ...] = ()
    models_file: Path | None = None
    settings_file: Path | None = None
    mcp_file: Path | None = None
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
class EffectiveSessionConfig:
    """Resolved Pi and sandbox settings shared by branch and chat sessions."""

    read_only_refs: tuple[Path, ...]
    skill_paths: tuple[Path, ...]
    model: str | None
    thinking: ThinkingLevel
    profile: str | None
    extensions: tuple[str, ...]
    models_file: Path | None
    settings_file: Path | None
    mcp_file: Path | None
    cpus: int
    memory: str | None
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class EffectiveBranchConfig(EffectiveSessionConfig):
    """Resolved Git settings used to create one branch session."""

    repo: Path
    mode: BranchMode
    base_ref: str
    base_commit: str | None
    branch: str
    source_ref: str | None
    upstream: str | None
    upstream_ref: str | None


@dataclass(frozen=True, slots=True)
class _SessionCommon:
    """Validated fields shared by current and legacy session records."""

    sandbox: str
    template: str
    model: str | None
    thinking: str
    read_only_refs: tuple[str, ...]
    skill_paths: tuple[str, ...]
    profile: str | None
    created_at: str
    last_used_at: str
    session_started: bool


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Non-secret metadata for one persistent branch or chat session."""

    schema_version: int
    name: str
    kind: SessionKind
    sandbox: str
    workspace: str
    branch: str | None
    base_commit: str | None
    template: str
    model: str | None
    thinking: str
    read_only_refs: tuple[str, ...]
    skill_paths: tuple[str, ...]
    profile: str | None
    created_at: str
    last_used_at: str
    session_started: bool = False

    def to_json_object(self) -> dict[str, object]:
        """Return the current JSON-safe state representation."""

        value = asdict(self)
        value["kind"] = self.kind.value
        return value

    @staticmethod
    def _fields(value: object) -> dict[str, object]:
        """Require a session-state object with string field names."""

        if not isinstance(value, dict):
            raise TypeError("session state must be a JSON object")
        mapping = cast("dict[object, object]", value)
        if not all(isinstance(key, str) for key in mapping):
            raise TypeError("session state field names must be strings")
        return cast("dict[str, object]", mapping)

    @staticmethod
    def _required_string(fields: dict[str, object], key: str) -> str:
        """Read one required non-empty string from session state."""

        item = fields.get(key)
        if not isinstance(item, str) or not item:
            raise TypeError(f"session state field {key!r} has the wrong type")
        return item

    @staticmethod
    def _optional_string(fields: dict[str, object], key: str) -> str | None:
        """Read one optional string from session state."""

        item = fields.get(key)
        if item is not None and not isinstance(item, str):
            raise TypeError(f"session state field {key!r} has the wrong type")
        return item

    @staticmethod
    def _string_tuple(fields: dict[str, object], key: str) -> tuple[str, ...]:
        """Read one string array from session state as a tuple."""

        item = fields.get(key, [])
        if not isinstance(item, list):
            raise TypeError(f"session state field {key!r} has the wrong type")
        values = cast("list[object]", item)
        if not all(isinstance(part, str) for part in values):
            raise TypeError(f"session state field {key!r} has the wrong type")
        return tuple(cast("list[str]", values))

    @classmethod
    def _common_fields(cls, fields: dict[str, object]) -> _SessionCommon:
        """Decode fields shared by current and legacy session records."""

        session_started = fields.get("session_started", False)
        if not isinstance(session_started, bool):
            raise TypeError("session state field 'session_started' has the wrong type")

        thinking = cls._required_string(fields, "thinking")
        try:
            ThinkingLevel(thinking)
        except ValueError as error:
            raise TypeError("session state field 'thinking' has an unsupported value") from error

        return _SessionCommon(
            sandbox=cls._required_string(fields, "sandbox"),
            template=cls._required_string(fields, "template"),
            model=cls._optional_string(fields, "model"),
            thinking=thinking,
            read_only_refs=cls._string_tuple(fields, "read_only_refs"),
            skill_paths=cls._string_tuple(fields, "skill_paths"),
            profile=cls._optional_string(fields, "profile"),
            created_at=cls._required_string(fields, "created_at"),
            last_used_at=cls._required_string(fields, "last_used_at"),
            session_started=session_started,
        )

    @classmethod
    def _from_legacy_task(cls, fields: dict[str, object]) -> Self:
        """Convert a schema-v1 Git task into a current branch session."""

        common = cls._common_fields(fields)
        return cls(
            schema_version=_CURRENT_SESSION_SCHEMA,
            name=cls._required_string(fields, "task"),
            kind=SessionKind.BRANCH,
            sandbox=common.sandbox,
            workspace=cls._required_string(fields, "repo"),
            branch=cls._required_string(fields, "branch"),
            base_commit=cls._required_string(fields, "base_commit"),
            template=common.template,
            model=common.model,
            thinking=common.thinking,
            read_only_refs=common.read_only_refs,
            skill_paths=common.skill_paths,
            profile=common.profile,
            created_at=common.created_at,
            last_used_at=common.last_used_at,
            session_started=common.session_started,
        )

    @classmethod
    def from_json_object(cls, value: object) -> Self:
        """Validate current state or upgrade a schema-v1 branch task in memory."""

        fields = cls._fields(value)
        schema_version = fields.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise TypeError("session state field 'schema_version' has the wrong type")
        if schema_version == 1:
            return cls._from_legacy_task(fields)
        if schema_version != _CURRENT_SESSION_SCHEMA:
            raise TypeError(f"unsupported session state schema {schema_version}")

        kind_value = cls._required_string(fields, "kind")
        try:
            kind = SessionKind(kind_value)
        except ValueError as error:
            raise TypeError("session state field 'kind' has an unsupported value") from error

        branch = cls._optional_string(fields, "branch")
        base_commit = cls._optional_string(fields, "base_commit")
        if kind is SessionKind.BRANCH and (not branch or not base_commit):
            raise TypeError("branch session state requires branch and base_commit")
        if kind is SessionKind.CHAT and (branch is not None or base_commit is not None):
            raise TypeError("chat session state cannot contain Git fields")

        common = cls._common_fields(fields)
        return cls(
            schema_version=_CURRENT_SESSION_SCHEMA,
            name=cls._required_string(fields, "name"),
            kind=kind,
            sandbox=common.sandbox,
            workspace=cls._required_string(fields, "workspace"),
            branch=branch,
            base_commit=base_commit,
            template=common.template,
            model=common.model,
            thinking=common.thinking,
            read_only_refs=common.read_only_refs,
            skill_paths=common.skill_paths,
            profile=common.profile,
            created_at=common.created_at,
            last_used_at=common.last_used_at,
            session_started=common.session_started,
        )


@dataclass(frozen=True, slots=True)
class SecretRecord:
    """Redacted metadata for one piw-managed Docker Sandbox secret."""

    schema_version: int
    source_env: str
    sandbox_env: str
    hosts: tuple[str, ...]
    placeholder_template: str
    placeholder: str
    fingerprint: str
    synced_at: str

    def to_json_object(self) -> dict[str, object]:
        """Return a JSON-safe representation that never contains the secret value."""

        return asdict(self)

    @classmethod
    def from_json_object(cls, value: object) -> Self:
        """Validate and decode redacted secret synchronization state."""

        if not isinstance(value, dict):
            raise TypeError("secret state record must be a JSON object")
        mapping = cast("dict[object, object]", value)
        if not all(isinstance(key, str) for key in mapping):
            raise TypeError("secret state field names must be strings")
        fields = cast("dict[str, object]", mapping)

        def required_string(key: str) -> str:
            """Read a required non-empty string from the secret state object."""

            item = fields.get(key)
            if not isinstance(item, str) or not item:
                raise TypeError(f"secret state field {key!r} has the wrong type")
            return item

        schema_version = fields.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise TypeError("secret state field 'schema_version' has the wrong type")

        hosts_value = fields.get("hosts")
        if not isinstance(hosts_value, list) or not all(
            isinstance(host, str) for host in cast("list[object]", hosts_value)
        ):
            raise TypeError("secret state field 'hosts' has the wrong type")
        hosts = tuple(cast("list[str]", hosts_value))
        if not hosts or len(hosts) != len(set(hosts)) or any(not host for host in hosts):
            raise TypeError("secret state field 'hosts' has an invalid value")

        placeholder_template = required_string("placeholder_template")
        if placeholder_template.count("{rand}") != 1:
            raise TypeError("secret state field 'placeholder_template' has an invalid value")

        fingerprint = required_string("fingerprint")
        if len(fingerprint) != _SHA256_HEX_LENGTH or any(
            character not in "0123456789abcdef" for character in fingerprint
        ):
            raise TypeError("secret state field 'fingerprint' has an invalid value")

        return cls(
            schema_version=schema_version,
            source_env=required_string("source_env"),
            sandbox_env=required_string("sandbox_env"),
            hosts=hosts,
            placeholder_template=placeholder_template,
            placeholder=required_string("placeholder"),
            fingerprint=fingerprint,
            synced_at=required_string("synced_at"),
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
    """Stable structured-output envelope emitted by every command."""

    schema_version: int
    command: str
    ok: bool
    data: object
    warnings: tuple[str, ...] = ()
    error: dict[str, object] | None = None

    def to_json_object(self) -> dict[str, object]:
        """Return a JSON-safe dictionary."""

        return asdict(self)
