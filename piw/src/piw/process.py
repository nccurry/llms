"""Subprocess boundary for external command execution."""

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Protocol

from piw.models import CommandResult


class Runner(Protocol):
    """Protocol used by services and deterministic tests."""

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
        interactive: bool = False,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run one command and return its result."""

        ...

    def which(self, command: str) -> str | None:
        """Locate an executable on PATH."""

        ...


class SubprocessRunner:
    """Production subprocess implementation."""

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
        interactive: bool = False,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run a subprocess without invoking a host shell."""

        started = time.monotonic()
        command_env = os.environ.copy()
        if env:
            command_env.update(env)

        completed = subprocess.run(  # noqa: S603
            argv,
            cwd=cwd,
            input=input_text,
            text=True,
            capture_output=not interactive,
            check=False,
            timeout=timeout_seconds,
            env=command_env,
        )

        return CommandResult(
            argv=argv,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_seconds=time.monotonic() - started,
        )

    def which(self, command: str) -> str | None:
        """Locate an executable on PATH."""

        return shutil.which(command)


def render_command(argv: tuple[str, ...]) -> str:
    """Render a diagnostic command line without interpreting it."""

    return shlex.join(argv)
