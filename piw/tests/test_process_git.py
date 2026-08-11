"""Subprocess and host Git adapter tests."""

import sys
from pathlib import Path
from typing import Final

from piw.git import GitClient
from piw.process import SubprocessRunner, render_command
from tests.fakes import ScenarioRunner

_GIT_ENV: Final = ("-c", "user.name=piw test", "-c", "user.email=piw@example.com")


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
    assert git.status(tmp_path).paths == ("host-change.txt",)


def test_git_client_reports_conflicts_and_captures_host_patch(tmp_path: Path) -> None:
    """Host capture reports conflicts and isolates the synthesized index and objects."""

    runner = ScenarioRunner(tmp_path)
    git = GitClient(runner)
    runner.host_conflicts = ("conflicted.txt",)
    assert git.status(tmp_path).conflicts == ("conflicted.txt",)

    runner.host_conflicts = ()
    runner.host_clean = False
    runner.host_patch_paths = ("host-change.txt",)
    runner.host_patch = "diff --git a/host-change.txt b/host-change.txt\n"
    captured = git.capture_worktree_patch(tmp_path)
    assert captured.paths == ("host-change.txt",)
    assert captured.text == runner.host_patch


def test_git_client_patch_recreates_real_worktree_without_mutating_host_git(
    tmp_path: Path,
) -> None:
    """The real patch path carries final file contents while leaving host Git state intact."""

    runner = SubprocessRunner()
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()

    def git(repo: Path, *args: str, input_text: str | None = None) -> str:
        result = runner.run(("git", *_GIT_ENV, "-C", str(repo), *args), input_text=input_text)
        assert result.returncode == 0, result.stderr
        return result.stdout

    git(source, "init", "--initial-branch=main")
    (source / ".gitignore").write_text("ignored.bin\n", encoding="utf-8")
    (source / "modified.txt").write_text("base\n", encoding="utf-8")
    (source / "deleted.txt").write_text("remove me\n", encoding="utf-8")
    git(source, "add", "--all")
    git(source, "commit", "-m", "base")

    (source / "modified.txt").write_text("staged\n", encoding="utf-8")
    git(source, "add", "modified.txt")
    (source / "modified.txt").write_text("final\n", encoding="utf-8")
    (source / "deleted.txt").unlink()
    (source / "new binary.bin").write_bytes(bytes(range(256)))
    executable = source / "run-me"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    (source / "empty.txt").touch()
    (source / "ignored.bin").write_bytes(b"not carried")

    client = GitClient(runner)
    status = client.status(source)
    assert set(status.paths) == {
        "deleted.txt",
        "empty.txt",
        "modified.txt",
        "new binary.bin",
        "run-me",
    }
    index_before = git(source, "ls-files", "--stage", "-z")
    objects_before = git(source, "count-objects", "-v")
    patch = client.capture_worktree_patch(source)
    assert git(source, "ls-files", "--stage", "-z") == index_before
    assert git(source, "count-objects", "-v") == objects_before
    assert "ignored.bin" not in patch.paths

    clone = runner.run(("git", "clone", "--quiet", str(source), str(target)))
    assert clone.returncode == 0, clone.stderr
    git(
        target,
        "apply",
        "--binary",
        "--whitespace=nowarn",
        "-",
        input_text=patch.text,
    )
    assert (target / "modified.txt").read_text(encoding="utf-8") == "final\n"
    assert not (target / "deleted.txt").exists()
    assert (target / "new binary.bin").read_bytes() == bytes(range(256))
    assert (target / "run-me").stat().st_mode & 0o111
    assert (target / "empty.txt").is_file()
    assert not (target / "ignored.bin").exists()
