"""Subprocess and host Git adapter tests."""

import sys
from pathlib import Path

from piw.git import GitClient
from piw.process import SubprocessRunner, render_command
from tests.piw.fakes import ScenarioRunner


def test_subprocess_runner_captures_output_and_environment(tmp_path: Path) -> None:
    """The production boundary avoids a shell and captures deterministic results."""

    runner = SubprocessRunner()
    result = runner.run(
        (
            sys.executable,
            "-c",
            "import os,sys; print(os.environ['PIW_TEST']); print(sys.stdin.read())",
        ),
        cwd=tmp_path,
        input_text="input",
        env={"PIW_TEST": "value"},
        timeout_seconds=10,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["value", "input"]
    assert result.duration_seconds >= 0
    assert runner.which("python")


def test_render_command_quotes_without_execution() -> None:
    """Diagnostic rendering preserves argument boundaries."""

    assert render_command(("printf", "%s", "two words")) == "printf %s 'two words'"


def test_git_client_reads_repository_state(tmp_path: Path) -> None:
    """All Git host inspection is read-only and explicitly typed."""

    runner = ScenarioRunner(tmp_path)
    git = GitClient(runner)
    assert git.root(tmp_path) == tmp_path
    assert git.is_clean(tmp_path)
    assert git.resolve_ref(tmp_path, "HEAD") == "a" * 40
    runner.host_clean = False
    assert not git.is_clean(tmp_path)
