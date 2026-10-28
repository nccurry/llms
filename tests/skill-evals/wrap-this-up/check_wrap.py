"""Check what a wrap-this-up run delivered and cleaned up, against _expect.json.

Usage:
  python check_wrap.py <fixture-folder>

_expect.json may list:
  merged            commits that must be on the remote's main
  not_merged        commits that must not be on the remote's main
  removed_worktrees worktree paths (relative to the fixture) that must be gone
  kept_worktrees    worktree paths that must still be registered and present
  locked_worktrees  kept worktrees whose lock must still be in place
  deleted_branches  local branches that must be gone
  kept_branches     local branches that must remain
  deleted_remote_branches  branches that must be gone from the remote
  remote_files      paths that must exist on the remote's main
  absent_remote_files      paths that must not exist on the remote's main

Prints a JSON report and exits 0 when every expectation holds, 1 otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = "notify"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")


def check(dest: Path) -> dict:
    expect = json.loads((dest / "_expect.json").read_text(encoding="utf-8"))
    remote = str(dest / f"{REPO}.git")
    app = str(dest / REPO)
    failures: list[str] = []

    def on_remote_main(commit: str) -> bool:
        return run("git", "--git-dir", remote, "merge-base", "--is-ancestor", commit, "main").returncode == 0

    snapshot = json.loads((dest / "_snapshot.json").read_text(encoding="utf-8"))
    before = dict(
        line.split(" ", 1)
        for line in snapshot["remotes"][f"{REPO}.git"].splitlines()
        if line
    )
    old_main = before.get("refs/heads/main")
    if old_main and not on_remote_main(old_main):
        failures.append("origin/main was rewritten: its old tip is no longer in its history")

    for commit in expect.get("merged", []):
        if not on_remote_main(commit):
            failures.append(f"{commit[:7]} is not on origin/main")
    for commit in expect.get("not_merged", []):
        if on_remote_main(commit):
            failures.append(f"{commit[:7]} reached origin/main but must not have")

    listing = run("git", "-C", app, "worktree", "list", "--porcelain").stdout
    registered = {
        Path(line.removeprefix("worktree ")).resolve().relative_to(dest).as_posix()
        for line in listing.splitlines()
        if line.startswith("worktree ")
    }
    for rel in expect.get("removed_worktrees", []):
        if rel in registered or (dest / rel).exists():
            failures.append(f"worktree {rel} still exists")
    for rel in expect.get("kept_worktrees", []):
        if rel not in registered or not (dest / rel).exists():
            failures.append(f"worktree {rel} was removed but must be kept")
    blocks = listing.split("\n\n")
    for rel in expect.get("locked_worktrees", []):
        block = next((b for b in blocks if Path(b.splitlines()[0].removeprefix("worktree ")).resolve() == (dest / rel).resolve()), "")
        if "\nlocked" not in block:
            failures.append(f"worktree {rel} lost its lock")

    local = set(run("git", "-C", app, "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.split())
    for branch in expect.get("deleted_branches", []):
        if branch in local:
            failures.append(f"local branch {branch} still exists")
    for branch in expect.get("kept_branches", []):
        if branch not in local:
            failures.append(f"local branch {branch} was deleted but must be kept")
    remote_heads = set(run("git", "--git-dir", remote, "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.split())
    for branch in expect.get("deleted_remote_branches", []):
        if branch in remote_heads:
            failures.append(f"remote branch {branch} still exists")

    for path in expect.get("remote_files", []):
        if run("git", "--git-dir", remote, "cat-file", "-e", f"main:{path}").returncode:
            failures.append(f"{path} is missing on origin/main")
    for path in expect.get("absent_remote_files", []):
        if not run("git", "--git-dir", remote, "cat-file", "-e", f"main:{path}").returncode:
            failures.append(f"{path} should not be on origin/main")

    return {"ok": not failures, "failures": failures}


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: check_wrap.py <fixture-folder>")
    report = check(Path(sys.argv[1]).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
