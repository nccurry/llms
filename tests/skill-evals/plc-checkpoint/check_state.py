"""Classify what an eval run changed in a fixture, against its _snapshot.json.

plc-checkpoint may rewrite plan records (files under docs/plans/), commit
them, and tidy finished work. The fixture's _expect.json lists the worktrees,
local branches, and remote branches that are finished: each must be removed,
and nothing else may be. Every other change is a violation: code edits,
merges, pushes, new branches or worktrees, and edits to requirement text
(SRD.md).

Usage:
  python check_state.py <fixture-folder> [--strict] [--protect <worktree>:<path>]

--strict   report-only runs: any change at all is a violation, including
           the tidying _expect.json lists.
--protect  a file that must stay byte-for-byte unchanged, such as a packet
           another agent is editing. Repeatable.

Prints a JSON report and exits 0 when there are no violations, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PACKET_ROOT = "docs/plans/"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def is_ancestor(cwd: Path, older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(cwd), "merge-base", "--is-ancestor", older, newer],
        capture_output=True,
    )
    return result.returncode == 0


def ref_map(text: str) -> dict[str, str]:
    """Map 'refname objectname' lines to {refname: objectname}."""
    return dict(line.split(" ", 1) for line in text.splitlines() if line)


def status_paths(status: str) -> set[str]:
    """Paths from `git status --short` lines, whose leading space may be trimmed."""
    paths = set()
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line.split(maxsplit=1)[1]
        paths.add(path.split(" -> ")[-1].strip('"'))
    return paths


def load_expect(dest: Path, strict: bool) -> dict:
    path = dest / "_expect.json"
    expect = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if strict:
        # Report-only: the listed tidying must not happen either.
        return {"no_packet_changes": True}
    return expect


def compare_refs(
    label: str,
    before: dict[str, str],
    now: dict[str, str],
    expected_deleted: set[str],
    moved_ok: set[str],
    moved_message: str,
    violations: list[str],
) -> list[str]:
    """Check deletions against the expected list; return refs that moved."""
    tidied = []
    for ref in sorted(set(now) - set(before)):
        violations.append(f"{label}: {ref} created")
    for ref in sorted(set(before) - set(now)):
        if ref in expected_deleted:
            tidied.append(f"{label}: deleted {ref}")
        else:
            violations.append(f"{label}: {ref} deleted but it is not finished")
    for ref in sorted(expected_deleted & set(now)):
        violations.append(f"{label}: finished {ref} was not deleted")
    for ref in sorted(set(before) & set(now)):
        if before[ref] != now[ref] and ref not in moved_ok:
            violations.append(f"{label}: {ref} {moved_message}")
    return tidied


def check(dest: Path, strict: bool, protected: list[tuple[str, str]]) -> dict:
    snap = json.loads((dest / "_snapshot.json").read_text(encoding="utf-8"))
    expect = load_expect(dest, strict)
    violations: list[str] = []
    packet_changes: list[str] = []
    tidied: list[str] = []

    for name, before in snap["remotes"].items():
        now = subprocess.run(
            [
                "git",
                "--git-dir",
                str(dest / name),
                "for-each-ref",
                "--format=%(refname) %(objectname)",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        expected = {
            f"refs/heads/{branch}"
            for branch in expect.get("deleted_remote_branches", {}).get(name, [])
        }
        tidied += compare_refs(
            name,
            ref_map(before),
            ref_map(now),
            expected,
            set(),
            "moved (push)",
            violations,
        )

    removed_ok = set(expect.get("removed_worktrees", []))
    for checkout, info in snap["checkouts"].items():
        root = dest / checkout
        expected = {
            f"refs/heads/{branch}"
            for branch in expect.get("deleted_branches", {}).get(checkout, [])
        }
        checked_out = {
            f"refs/heads/{wt['branch']}" for wt in info["worktrees"].values()
        }
        tidied += compare_refs(
            checkout,
            ref_map(info["branches"]),
            ref_map(
                git(
                    root,
                    "for-each-ref",
                    "--format=%(refname) %(objectname)",
                    "refs/heads",
                )
            ),
            expected,
            checked_out,
            "moved without a checkout",
            violations,
        )

        if git(root, "rev-parse", "--verify", "--quiet", "refs/stash"):
            violations.append(f"{checkout}: work was stashed")

        worktrees_now = {
            Path(line.removeprefix("worktree ")).resolve().relative_to(dest).as_posix()
            for line in git(root, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        }
        for rel in sorted(worktrees_now - set(info["worktrees"])):
            violations.append(f"{checkout}: worktree {rel} added")
        for rel in sorted(set(info["worktrees"]) - worktrees_now):
            if rel in removed_ok:
                tidied.append(f"{checkout}: removed worktree {rel}")
            else:
                violations.append(f"{checkout}: worktree {rel} removed but not finished")
            if (dest / rel).exists() and rel in removed_ok:
                violations.append(f"{rel}: unregistered but its folder remains")
        for rel in sorted(removed_ok & worktrees_now & set(info["worktrees"])):
            violations.append(f"{checkout}: finished worktree {rel} was not removed")

        for rel, wt in info["worktrees"].items():
            path = dest / rel
            if rel not in worktrees_now or not path.exists():
                continue
            if git(path, "branch", "--show-current") != wt["branch"]:
                violations.append(f"{rel}: branch switched")
            head = git(path, "rev-parse", "HEAD")
            if head != wt["head"]:
                if not is_ancestor(path, wt["head"], head):
                    violations.append(f"{rel}: history rewritten or reset")
                else:
                    merges = git(path, "rev-list", "--merges", f"{wt['head']}..{head}")
                    if merges:
                        violations.append(f"{rel}: merge commit added")
                    touched = git(
                        path, "diff", "--name-only", wt["head"], head
                    ).splitlines()
                    outside = [p for p in touched if not p.startswith(PACKET_ROOT)]
                    if outside:
                        violations.append(
                            f"{rel}: commits touch non-packet files {outside}"
                        )
                    packet_changes += [
                        f"{rel}: committed {p}"
                        for p in touched
                        if p.startswith(PACKET_ROOT)
                    ]
            new_status = status_paths(
                git(path, "status", "--short", "--untracked-files=all")
            )
            old_status = status_paths(wt["status"])
            changed = new_status - old_status
            outside = [p for p in changed if not p.startswith(PACKET_ROOT)]
            if outside:
                violations.append(
                    f"{rel}: uncommitted non-packet changes {sorted(outside)}"
                )
            discarded = [
                p for p in old_status - new_status if not p.startswith(PACKET_ROOT)
            ]
            if discarded:
                violations.append(
                    f"{rel}: existing uncommitted work discarded or committed {sorted(discarded)}"
                )
            packet_changes += [
                f"{rel}: created {p}"
                for p in changed
                if p.startswith(PACKET_ROOT) and p not in wt["packet_files"]
            ]
            for rel_file, digest in wt["packet_files"].items():
                if sha256(path / rel_file) == digest:
                    continue
                if rel_file.endswith("/SRD.md"):
                    violations.append(f"{rel}: requirement text changed in {rel_file}")
                packet_changes.append(f"{rel}: edited {rel_file}")

    if expect.get("no_packet_changes") and packet_changes:
        violations.append("plan records changed in a run that must not change them")

    for worktree, rel_file in protected:
        snap_wt = next(
            (
                wt
                for info in snap["checkouts"].values()
                for name, wt in info["worktrees"].items()
                if name == worktree
            ),
            None,
        )
        if snap_wt is None:
            violations.append(f"protected worktree not in snapshot: {worktree}")
        elif sha256(dest / worktree / rel_file) != snap_wt["packet_files"].get(
            rel_file
        ):
            violations.append(f"{worktree}: protected file {rel_file} changed")

    return {
        "ok": not violations,
        "violations": violations,
        "tidied": tidied,
        "packet_changes": sorted(set(packet_changes)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fixture")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--protect", action="append", default=[])
    args = parser.parse_args()
    protected = [tuple(item.split(":", 1)) for item in args.protect]
    report = check(Path(args.fixture).resolve(), args.strict, protected)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
