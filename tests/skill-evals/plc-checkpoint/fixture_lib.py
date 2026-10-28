"""Build small git repositories with a plan packet for plc-checkpoint and
wrap-this-up eval cases.

Each case's fixture/build.py calls these helpers to create, under a destination
folder: a bare `<name>.git` remote, a primary checkout `<name>/`, and campaign
worktrees under `<name>-wt/<campaign>/<checkout>`. Nothing here needs network
access or a PR host.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def commit(checkout: Path, message: str, files: dict[str, str]) -> str:
    write(checkout, files)
    git(checkout, "add", "--all")
    git(checkout, "commit", "-q", "-m", message)
    return git(checkout, "rev-parse", "--short", "HEAD")


def configure(checkout: Path) -> None:
    git(checkout, "config", "user.name", "Eval Fixture")
    git(checkout, "config", "user.email", "eval@example.invalid")
    git(checkout, "config", "core.autocrlf", "false")


def make_repo(dest: Path, name: str, files: dict[str, str]) -> Path:
    """Create `<name>.git` and a primary checkout `<name>/` with one commit on main."""
    remote = dest / f"{name}.git"
    checkout = dest / name
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(remote)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(checkout)],
        check=True,
        capture_output=True,
    )
    configure(checkout)
    git(checkout, "checkout", "-q", "-B", "main")
    commit(checkout, "docs: add plan", files)
    git(checkout, "push", "-q", "-u", "origin", "main")
    return checkout


def add_worktree(
    checkout: Path, campaign: str, name: str, branch: str, base: str = "main"
) -> Path:
    path = checkout.parent / f"{checkout.name}-wt" / campaign / name
    git(checkout, "worktree", "add", "-q", "-b", branch, str(path), base)
    return path


def second_clone(dest: Path, name: str, clone_name: str) -> Path:
    """Clone the remote again to push work the primary checkout has not fetched."""
    path = dest / "_others" / clone_name
    subprocess.run(
        ["git", "clone", "-q", str(dest / f"{name}.git"), str(path)],
        check=True,
        capture_output=True,
    )
    configure(path)
    return path


def checkout_state(path: Path) -> dict:
    """Head, status, and packet file hashes for one checkout or worktree."""
    plans = path / "docs" / "plans"
    packet_files = {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(plans.rglob("*"))
        if file.is_file()
    }
    return {
        "head": git(path, "rev-parse", "HEAD"),
        "branch": git(path, "branch", "--show-current"),
        "status": git(path, "status", "--short", "--untracked-files=all"),
        "packet_files": packet_files,
    }


def snapshot(dest: Path, checkouts: list[Path]) -> None:
    """Record repo state so check_state.py can classify what a run changed."""
    state: dict = {"checkouts": {}, "remotes": {}}
    for checkout in checkouts:
        worktrees = [
            Path(line.removeprefix("worktree "))
            for line in git(checkout, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        ]
        state["checkouts"][checkout.relative_to(dest).as_posix()] = {
            "branches": git(
                checkout,
                "for-each-ref",
                "--format=%(refname) %(objectname)",
                "refs/heads",
            ),
            "worktrees": {
                worktree.resolve().relative_to(dest).as_posix(): checkout_state(
                    worktree
                )
                for worktree in worktrees
            },
        }
    for remote in sorted(dest.glob("*.git")):
        state["remotes"][remote.name] = subprocess.run(
            [
                "git",
                "--git-dir",
                str(remote),
                "for-each-ref",
                "--format=%(refname) %(objectname)",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    (dest / "_snapshot.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def expect(
    dest: Path,
    removed_worktrees: list[str] = (),
    deleted_branches: dict[str, list[str]] | None = None,
    deleted_remote_branches: dict[str, list[str]] | None = None,
    no_packet_changes: bool = False,
) -> None:
    """Record the tidying a run must do. Anything removed beyond this fails.

    Paths are relative to `dest`; branches are short names such as `plc/x-p1`.
    """
    data = {
        "removed_worktrees": list(removed_worktrees),
        "deleted_branches": deleted_branches or {},
        "deleted_remote_branches": deleted_remote_branches or {},
        "no_packet_changes": no_packet_changes,
    }
    (dest / "_expect.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def current_work(
    last_updated: str,
    rows: list[tuple[str, str, str, str]],
    checkouts: list[tuple[str, str, str]],
    next_action: str,
    blocker: str = "none",
    status: str = "In progress",
) -> str:
    """A Current Work block in the plc-planning default format.

    `rows` are (phase or task, state, owner, evidence); they become the
    current-state line.
    """
    state = "; ".join(
        f"{phase}: {state} ({owner}; evidence: {evidence})"
        for phase, state, owner, evidence in rows
    )
    checkout_lines = "".join(f"| `{a}` | `{b}` | {c} |\n" for a, b, c in checkouts)
    return (
        "## Current Work\n\n"
        "Replace this block as work changes; do not append successive checkpoints.\n\n"
        f"- Status: {status}\n"
        "- Owner: the user\n"
        f"- Last updated: {last_updated}\n"
        f"- Current state: {state}\n"
        f"- Next action: {next_action}\n"
        f"- Blocker: {blocker}\n\n"
        "Where the work lives:\n\n"
        "| Checkout | Branch | State |\n| --- | --- | --- |\n"
        f"{checkout_lines}"
    )


def destination() -> Path:
    if len(sys.argv) != 2:
        sys.exit("usage: build.py <empty-destination-folder>")
    dest = Path(sys.argv[1]).resolve()
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"destination is not empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def packet(
    title: str,
    requirements: str,
    phases: str,
    extra: str = "",
    status: str = "## Status\n\n- Status: In progress\n",
) -> dict[str, str]:
    """Return a minimal packet in the plc-planning default shape.

    The default `status` is the older one-line form existing packets use; pass
    `current_work(...)` for the current format.
    """
    root = f"docs/plans/{title}"
    return {
        f"{root}/README.md": (
            f"# {title} PLC\n\n{status}\n"
            "## Packet\n\n- [SRD.md](SRD.md)\n- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)\n"
            f"{extra}"
        ),
        f"{root}/SRD.md": f"# {title} requirements\n\n{requirements}",
        f"{root}/IMPLEMENTATION_PLAN.md": f"# {title} implementation plan\n\n{phases}",
    }
