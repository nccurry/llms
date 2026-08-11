"""Atomic persistence for non-secret task records."""

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from piw.config import state_home
from piw.errors import ExitCode, PiwError
from piw.models import TaskRecord


class StateStore:
    """Read and write versioned task state under the XDG state directory."""

    def __init__(self, root: Path | None = None) -> None:
        """Initialize the store at an optional test-specific root."""

        self.root = (root or state_home() / "tasks").expanduser()

    def path_for(self, task: str) -> Path:
        """Return the task's state path."""

        return self.root / f"{task}.json"

    def exists(self, task: str) -> bool:
        """Return whether a task record exists."""

        return self.path_for(task).is_file()

    def load(self, task: str) -> TaskRecord:
        """Load and validate a task record."""

        path = self.path_for(task)
        try:
            decoded: object = json.loads(path.read_text(encoding="utf-8"))
            record = TaskRecord.from_json_object(decoded)
        except FileNotFoundError as error:
            raise PiwError(
                f"task {task!r} does not exist",
                code=ExitCode.TASK,
                kind="task_not_found",
                hint="Run 'piw list' to see known tasks.",
            ) from error
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PiwError(
                f"cannot read task state {path}: {error}",
                code=ExitCode.STATE,
                kind="invalid_task_state",
            ) from error
        if record.schema_version != 1:
            raise PiwError(
                f"task {task!r} uses unsupported state schema {record.schema_version}",
                code=ExitCode.STATE,
                kind="unsupported_task_state",
            )
        return record

    def save(self, record: TaskRecord) -> None:
        """Atomically save a task record with user-only permissions."""

        payload = json.dumps(record.to_json_object(), indent=2, sort_keys=True) + "\n"
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{record.task}.",
                suffix=".tmp",
                dir=self.root,
                text=True,
            )
        except OSError as error:
            raise PiwError(
                f"cannot create task state in {self.root}: {error}",
                code=ExitCode.STATE,
                kind="task_state_write_failed",
            ) from error
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path_for(record.task))
        except OSError as error:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
            raise PiwError(
                f"cannot save task state {self.path_for(record.task)}: {error}",
                code=ExitCode.STATE,
                kind="task_state_write_failed",
            ) from error

    def delete(self, task: str) -> None:
        """Delete one task record if present."""

        self.path_for(task).unlink(missing_ok=True)

    def list(self) -> tuple[TaskRecord, ...]:
        """Load all valid task records in stable order."""

        if not self.root.is_dir():
            return ()
        return tuple(self.load(path.stem) for path in sorted(self.root.glob("*.json")))
