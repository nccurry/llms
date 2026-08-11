"""Read-only host Git inspection."""

from pathlib import Path

from piw.errors import ExitCode, PiwError
from piw.process import Runner


class GitClient:
    """Inspect a host repository without changing it."""

    def __init__(self, runner: Runner) -> None:
        """Initialize the client with an external command runner."""

        self.runner = runner

    def _read(self, repo: Path, *args: str) -> str:
        result = self.runner.run(("git", "-C", str(repo), *args))
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "git command failed"
            raise PiwError(
                message,
                code=ExitCode.PREREQUISITE,
                kind="git_error",
            )
        return result.stdout.strip()

    def root(self, candidate: Path) -> Path:
        """Resolve the containing Git worktree root."""

        result = self.runner.run(
            ("git", "-C", str(candidate.expanduser()), "rev-parse", "--show-toplevel")
        )
        if result.returncode != 0:
            raise PiwError(
                f"{candidate} is not inside a Git worktree",
                code=ExitCode.PREREQUISITE,
                kind="not_a_repository",
            )
        return Path(result.stdout.strip()).resolve()

    def is_clean(self, repo: Path) -> bool:
        """Return whether tracked and untracked host files are clean."""

        return not self._read(repo, "status", "--porcelain=v1", "--untracked-files=all")

    def is_valid_branch(self, repo: Path, branch: str) -> bool:
        """Return whether Git accepts a proposed branch name."""

        result = self.runner.run(("git", "-C", str(repo), "check-ref-format", "--branch", branch))
        return result.returncode == 0

    def resolve_ref(self, repo: Path, ref: str) -> str:
        """Resolve a Git revision to a commit ID."""

        return self._read(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
