"""Read-only host Git inspection and portable working-tree capture."""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from piw.errors import ExitCode, PiwError
from piw.process import Runner

_MIN_STATUS_ENTRY_LENGTH: Final = 4


@dataclass(frozen=True, slots=True)
class HostStatus:
    """Tracked, untracked, and conflicted paths in a host working tree."""

    paths: tuple[str, ...]
    conflicts: tuple[str, ...]

    @property
    def dirty(self) -> bool:
        """Return whether the host has changes that require a policy decision."""

        return bool(self.paths)


@dataclass(frozen=True, slots=True)
class HostPatch:
    """A binary-safe patch that recreates final host working-tree contents."""

    text: str
    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExistingBranch:
    """One exact local or remote-tracking branch selected on the host."""

    branch: str
    source_ref: str
    full_ref: str
    commit: str
    upstream: str | None
    upstream_ref: str | None


class GitClient:
    """Inspect a host repository without changing it."""

    def __init__(self, runner: Runner) -> None:
        """Initialize the client with an external command runner."""

        self.runner = runner

    def _read(self, repo: Path, *args: str) -> str:
        """Run Git and return its output without surrounding whitespace."""

        return self._read_with_env(repo, *args).strip()

    def _read_with_env(
        self,
        repo: Path,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> str:
        """Run Git in a repository and raise a typed error if it fails."""

        result = self.runner.run(("git", "-C", str(repo), *args), env=env)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "git command failed"
            raise PiwError(
                message,
                code=ExitCode.PREREQUISITE,
                kind="git_error",
            )

        return result.stdout

    @staticmethod
    def _nul_paths(value: str) -> tuple[str, ...]:
        """Decode Git's NUL-delimited path output without losing spaces."""

        return tuple(path for path in value.split("\0") if path)

    @classmethod
    def _parse_status(cls, value: str) -> HostStatus:
        """Parse porcelain-v1 status into changed paths and conflicts."""

        entries = value.split("\0")
        paths: set[str] = set()
        conflicts: set[str] = set()
        conflict_states = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
        index = 0

        while index < len(entries):
            entry = entries[index]
            index += 1
            if not entry:
                continue

            if len(entry) < _MIN_STATUS_ENTRY_LENGTH or entry[2] != " ":
                raise PiwError(
                    "Git returned malformed working-tree status",
                    code=ExitCode.PREREQUISITE,
                    kind="git_status_error",
                )

            state = entry[:2]
            path = entry[3:]
            paths.add(path)

            if state in conflict_states:
                conflicts.add(path)
            if "R" in state or "C" in state:
                if index >= len(entries) or not entries[index]:
                    raise PiwError(
                        "Git returned an incomplete rename or copy status",
                        code=ExitCode.PREREQUISITE,
                        kind="git_status_error",
                    )
                paths.add(entries[index])
                index += 1

        return HostStatus(tuple(sorted(paths)), tuple(sorted(conflicts)))

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

    def status(self, repo: Path) -> HostStatus:
        """Return changed paths and unresolved conflicts without changing the host."""

        value = self._read_with_env(
            repo,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        )
        return self._parse_status(value)

    def capture_worktree_patch(self, repo: Path) -> HostPatch:
        """Capture final working-tree contents relative to HEAD without touching Git state."""

        objects_value = self._read(repo, "rev-parse", "--git-path", "objects")
        objects = Path(objects_value)
        if not objects.is_absolute():
            objects = (repo / objects).resolve()

        with tempfile.TemporaryDirectory(prefix="piw-host-changes-") as temporary:
            root = Path(temporary)
            isolated_objects = root / "objects"
            isolated_objects.mkdir()

            env = {
                "GIT_INDEX_FILE": str(root / "index"),
                "GIT_OBJECT_DIRECTORY": str(isolated_objects),
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(objects),
            }

            self._read_with_env(repo, "read-tree", "HEAD", env=env)
            self._read_with_env(repo, "add", "--all", "--", env=env)

            paths = self._nul_paths(
                self._read_with_env(
                    repo,
                    "diff",
                    "--cached",
                    "--name-only",
                    "-z",
                    "HEAD",
                    "--",
                    env=env,
                )
            )
            patch = self._read_with_env(
                repo,
                "diff",
                "--cached",
                "--binary",
                "--full-index",
                "--no-color",
                "--no-ext-diff",
                "--no-textconv",
                "HEAD",
                "--",
                env=env,
            )

        return HostPatch(text=patch, paths=paths)

    def is_valid_branch(self, repo: Path, branch: str) -> bool:
        """Return whether Git accepts a proposed branch name."""

        result = self.runner.run(("git", "-C", str(repo), "check-ref-format", "--branch", branch))
        return result.returncode == 0

    def _ref_exists(self, repo: Path, full_ref: str) -> bool:
        """Return whether one fully qualified branch ref exists."""

        result = self.runner.run(
            ("git", "-C", str(repo), "show-ref", "--verify", "--quiet", full_ref)
        )
        if result.returncode in {0, 1}:
            return result.returncode == 0
        message = result.stderr.strip() or result.stdout.strip() or "cannot inspect Git refs"
        raise PiwError(message, code=ExitCode.PREREQUISITE, kind="git_error")

    def _local_branch(self, repo: Path, branch: str) -> ExistingBranch | None:
        """Resolve one exact local branch without DWIM ref matching."""

        if not self.is_valid_branch(repo, branch):
            return None
        full_ref = f"refs/heads/{branch}"
        if not self._ref_exists(repo, full_ref):
            return None
        upstream_ref = self._read(
            repo,
            "for-each-ref",
            "--format=%(upstream)",
            full_ref,
        )
        upstream = (
            self._read(
                repo,
                "for-each-ref",
                "--format=%(upstream:short)",
                full_ref,
            )
            if upstream_ref and self._ref_exists(repo, upstream_ref)
            else ""
        )
        return ExistingBranch(
            branch=branch,
            source_ref=branch,
            full_ref=full_ref,
            commit=self.resolve_ref(repo, full_ref),
            upstream=upstream or None,
            upstream_ref=upstream_ref if upstream else None,
        )

    def _remote_branch(
        self,
        repo: Path,
        value: str,
        remotes: tuple[str, ...],
    ) -> ExistingBranch | None:
        """Resolve one explicit remote-tracking branch and infer its local name."""

        for remote in sorted(remotes, key=len, reverse=True):
            prefix = f"{remote}/"
            if not value.startswith(prefix):
                continue
            branch = value.removeprefix(prefix)
            if not self.is_valid_branch(repo, branch):
                raise PiwError(
                    f"Git does not accept existing branch name {value!r}",
                    code=ExitCode.USAGE,
                    kind="invalid_existing_branch",
                )
            full_ref = f"refs/remotes/{value}"
            if not self._ref_exists(repo, full_ref):
                return None
            return ExistingBranch(
                branch=branch,
                source_ref=value,
                full_ref=full_ref,
                commit=self.resolve_ref(repo, full_ref),
                upstream=value,
                upstream_ref=full_ref,
            )
        return None

    def resolve_existing_branch(self, repo: Path, value: str) -> ExistingBranch:
        """Resolve an exact local or explicitly named remote-tracking branch."""

        requested = value.strip()
        if not requested:
            raise PiwError(
                "--existing requires a branch name",
                code=ExitCode.USAGE,
                kind="invalid_existing_branch",
            )
        if not requested.startswith("refs/") and not self.is_valid_branch(repo, requested):
            raise PiwError(
                f"Git does not accept existing branch name {requested!r}",
                code=ExitCode.USAGE,
                kind="invalid_existing_branch",
            )

        remotes = tuple(sorted(part for part in self._read(repo, "remote").splitlines() if part))
        if requested.startswith("refs/heads/"):
            local_name = requested.removeprefix("refs/heads/")
            if not self.is_valid_branch(repo, local_name):
                raise PiwError(
                    f"Git does not accept existing branch name {requested!r}",
                    code=ExitCode.USAGE,
                    kind="invalid_existing_branch",
                )
            resolved = self._local_branch(repo, local_name)
        elif requested.startswith("refs/remotes/"):
            remote_name = requested.removeprefix("refs/remotes/")
            resolved = self._remote_branch(repo, remote_name, remotes)
        elif requested.startswith("refs/"):
            raise PiwError(
                "--existing accepts only refs/heads/* or refs/remotes/* branch refs",
                code=ExitCode.USAGE,
                kind="invalid_existing_branch",
            )
        else:
            resolved = self._local_branch(repo, requested)
            if resolved is None:
                resolved = self._remote_branch(repo, requested, remotes)

        if resolved is not None:
            return resolved

        suggestions = tuple(
            candidate
            for remote in remotes
            if self._ref_exists(repo, f"refs/remotes/{remote}/{requested}")
            for candidate in (f"{remote}/{requested}",)
        )
        if len(suggestions) == 1:
            hint = f"Use '--existing {suggestions[0]}' to select the remote-tracking branch."
        elif suggestions:
            choices = " or ".join(f"'--existing {item}'" for item in suggestions)
            hint = f"Choose one remote-tracking branch explicitly: {choices}."
        else:
            hint = "Fetch the branch, then retry with its local name or REMOTE/BRANCH."
        raise PiwError(
            f"existing branch {requested!r} was not found",
            code=ExitCode.PREREQUISITE,
            kind="existing_branch_not_found",
            hint=hint,
        )

    def resolve_ref(self, repo: Path, ref: str) -> str:
        """Resolve a Git revision to a commit ID."""

        return self._read(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
