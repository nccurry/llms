"""Atomic persistence for session records and redacted secret metadata."""

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import cast

from piw.config import state_home
from piw.errors import ExitCode, PiwError
from piw.models import SecretRecord, SessionRecord


def _atomic_write(path: Path, payload: str, error_kind: str, label: str) -> None:
    """Write one user-only state file atomically."""

    root = path.parent
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=root,
            text=True,
        )
    except OSError as error:
        raise PiwError(
            f"cannot create {label} in {root}: {error}",
            code=ExitCode.STATE,
            kind=error_kind,
        ) from error

    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        temporary.replace(path)
    except OSError as error:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        with suppress(OSError):
            temporary.unlink(missing_ok=True)

        raise PiwError(
            f"cannot save {label} {path}: {error}",
            code=ExitCode.STATE,
            kind=error_kind,
        ) from error


def _decode_secret_records(decoded: object) -> tuple[SecretRecord, ...]:
    """Validate the outer secret state document."""

    if not isinstance(decoded, dict):
        raise TypeError("secret state must be a JSON object")
    mapping = cast("dict[object, object]", decoded)
    schema_version = mapping.get("schema_version")
    if schema_version != 1:
        raise TypeError(f"unsupported secret state schema {schema_version!r}")
    raw_records = mapping.get("records")
    if not isinstance(raw_records, list):
        raise TypeError("secret state records must be an array")

    return tuple(SecretRecord.from_json_object(item) for item in cast("list[object]", raw_records))


class StateStore:
    """Read and write persistent session state with legacy task migration."""

    def __init__(
        self,
        root: Path | None = None,
        legacy_root: Path | None = None,
    ) -> None:
        """Initialize the store at an optional test-specific root."""

        if root is None:
            self.root = (state_home() / "sessions").expanduser()
            self.legacy_root = (legacy_root or state_home() / "tasks").expanduser()
        else:
            self.root = root.expanduser()
            self.legacy_root = legacy_root.expanduser() if legacy_root else None

    def path_for(self, name: str) -> Path:
        """Return the current state path for one session name."""

        return self.root / f"{name}.json"

    def _legacy_path_for(self, name: str) -> Path | None:
        """Return a legacy task path when migration support is active."""

        return self.legacy_root / f"{name}.json" if self.legacy_root else None

    def exists(self, name: str) -> bool:
        """Return whether current or legacy state exists for a session."""

        legacy = self._legacy_path_for(name)
        return self.path_for(name).is_file() or bool(legacy and legacy.is_file())

    def _path_for_load(self, name: str) -> Path:
        """Prefer current state and fall back to a legacy task record."""

        current = self.path_for(name)
        if current.is_file():
            return current
        legacy = self._legacy_path_for(name)
        return legacy if legacy and legacy.is_file() else current

    def load(self, name: str) -> SessionRecord:
        """Load a session record, upgrading schema-v1 tasks in memory."""

        path = self._path_for_load(name)
        try:
            decoded: object = json.loads(path.read_text(encoding="utf-8"))
            record = SessionRecord.from_json_object(decoded)
        except FileNotFoundError as error:
            raise PiwError(
                f"session {name!r} does not exist",
                code=ExitCode.SESSION,
                kind="session_not_found",
                hint="Run 'piw list' to see known sessions.",
            ) from error
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PiwError(
                f"cannot read session state {path}: {error}",
                code=ExitCode.STATE,
                kind="invalid_session_state",
            ) from error

        if record.name != name:
            raise PiwError(
                f"session state {path} belongs to {record.name!r}, not {name!r}",
                code=ExitCode.STATE,
                kind="invalid_session_state",
            )

        return record

    def save(self, record: SessionRecord) -> None:
        """Save current state, then remove the migrated legacy record."""

        payload = json.dumps(record.to_json_object(), indent=2, sort_keys=True) + "\n"
        _atomic_write(
            self.path_for(record.name),
            payload,
            "session_state_write_failed",
            "session state",
        )
        legacy = self._legacy_path_for(record.name)
        if legacy:
            with suppress(OSError):
                legacy.unlink(missing_ok=True)

    def delete(self, name: str) -> None:
        """Delete current and legacy state for one session."""

        try:
            self.path_for(name).unlink(missing_ok=True)
            legacy = self._legacy_path_for(name)
            if legacy:
                legacy.unlink(missing_ok=True)
        except OSError as error:
            raise PiwError(
                f"cannot delete session state for {name!r}: {error}",
                code=ExitCode.STATE,
                kind="session_state_delete_failed",
            ) from error

    @staticmethod
    def _state_names(root: Path | None) -> set[str]:
        """Return JSON record names found beneath one optional state root."""

        if root is None or not root.is_dir():
            return set()
        return {path.stem for path in root.glob("*.json")}

    def list(self) -> tuple[SessionRecord, ...]:
        """Load current and legacy session records in stable name order."""

        names = self._state_names(self.root) | self._state_names(self.legacy_root)
        return tuple(self.load(name) for name in sorted(names))


class SecretStateStore:
    """Persist fingerprints and placeholders without persisting credential values."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the store at an optional test-specific path."""

        self.path = (path or state_home() / "secrets.json").expanduser()

    def load(self) -> tuple[SecretRecord, ...]:
        """Load all redacted synchronization records in stable order."""

        if not self.path.exists():
            return ()

        try:
            decoded: object = json.loads(self.path.read_text(encoding="utf-8"))
            records = _decode_secret_records(decoded)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PiwError(
                f"cannot read secret state {self.path}: {error}",
                code=ExitCode.STATE,
                kind="invalid_secret_state",
            ) from error

        if any(record.schema_version != 1 for record in records):
            raise PiwError(
                "secret state contains an unsupported record schema",
                code=ExitCode.STATE,
                kind="invalid_secret_state",
            )

        sandbox_envs = [record.sandbox_env for record in records]
        if len(sandbox_envs) != len(set(sandbox_envs)):
            raise PiwError(
                "secret state contains duplicate sandbox environment names",
                code=ExitCode.STATE,
                kind="invalid_secret_state",
            )

        return tuple(sorted(records, key=lambda record: record.sandbox_env))

    def save(self, records: tuple[SecretRecord, ...]) -> None:
        """Atomically save redacted synchronization records."""

        payload = (
            json.dumps(
                {
                    "schema_version": 1,
                    "records": [
                        record.to_json_object()
                        for record in sorted(records, key=lambda item: item.sandbox_env)
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        _atomic_write(
            self.path,
            payload,
            "secret_state_write_failed",
            "secret state",
        )
