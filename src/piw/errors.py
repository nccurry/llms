"""Stable errors and exit codes for piw."""

from dataclasses import dataclass
from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes that form part of piw's public interface."""

    SUCCESS = 0
    USAGE = 2
    CONFIG = 10
    PREREQUISITE = 11
    TASK = 12
    SANDBOX = 13
    UNSAFE = 14
    TIMEOUT = 15
    STATE = 16
    COMMAND = 20
    INTERRUPTED = 130


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    """Machine-readable error details."""

    kind: str
    message: str
    hint: str | None = None


class PiwError(Exception):
    """Expected operational failure with a stable exit code."""

    def __init__(
        self,
        message: str,
        *,
        code: ExitCode,
        kind: str,
        hint: str | None = None,
    ) -> None:
        """Initialize an expected failure."""

        super().__init__(message)
        self.code = code
        self.detail = ErrorDetail(kind=kind, message=message, hint=hint)
