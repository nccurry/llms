#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Report facts about every registered worktree. Read-only; makes no decisions."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def git(cwd: str | Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def out(cwd: str | Path, *args: str) -> str:
    return git(cwd, *args).stdout.strip()


def iso(epoch: int | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def parse_worktrees(porcelain: str) -> list[dict]:
    entries, current = [], {}
    for line in porcelain.splitlines() + [""]:
        if not line:
            if current:
                entries.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current = {"path": value, "branch": None, "detached": False}
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key == "detached":
            current["detached"] = True
        elif key == "bare":
            current["bare"] = True
        elif key in ("locked", "prunable"):
            current[key] = value or True
    return entries


def resolve_target(root: str, remote: str, requested: str | None) -> str | None:
    if requested:
        # An explicit target never falls back to another branch.
        candidates = [requested]
    else:
        head = out(root, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD")
        candidates = [head, f"{remote}/main", f"{remote}/master", "main", "master"]
    for ref in filter(None, candidates):
        if git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0:
            return ref
    return None


def in_target(path: str, target: str) -> str:
    if git(path, "merge-base", "--is-ancestor", "HEAD", target).returncode == 0:
        return "ancestor"
    merged = git(path, "merge-tree", "--write-tree", "--no-messages", target, "HEAD")
    if merged.returncode not in (0, 1):
        return "unknown"
    tree = merged.stdout.splitlines()[0] if merged.stdout else ""
    if merged.returncode == 0 and tree == out(path, "rev-parse", f"{target}^{{tree}}"):
        return "content"
    return "no"


def local_changes(path: str) -> dict:
    counts = {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0}
    status = git(path, "status", "--porcelain", "--untracked-files=all").stdout
    for line in status.splitlines():
        code = line[:2]
        if code == "??":
            counts["untracked"] += 1
        elif "U" in code or code in ("AA", "DD"):
            counts["conflicted"] += 1
        else:
            counts["staged"] += code[0] not in " ?"
            counts["unstaged"] += code[1] not in " ?"
    return counts


def review(root: str, branch: str, remote_url: str) -> dict:
    if "github.com" in remote_url:
        tool = ["gh", "pr", "list", "--head", branch, "--state", "all",
                "--json", "number,state,headRefOid"]
    else:
        tool = ["glab", "mr", "list", "--source-branch", branch, "--all", "-F", "json"]
    if not shutil.which(tool[0]):
        return {"error": f"{tool[0]} not found"}
    result = subprocess.run(tool, cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return {"error": result.stderr.strip()[:200]}
    items = json.loads(result.stdout or "[]")
    return {"items": [
        {"id": item.get("number", item.get("iid")),
         "state": str(item.get("state", "")).lower(),
         "head": item.get("headRefOid", item.get("sha"))}
        for item in items
    ]}


def campaign_of(path: Path, root: Path) -> str | None:
    wt_root = root.parent / f"{root.name}-wt"
    try:
        relative = path.relative_to(wt_root)
    except ValueError:
        return None
    return relative.parts[0] if len(relative.parts) > 1 else None


def build_report(start: str, remote: str, target: str | None, fetch: bool,
                 reviews: bool) -> dict:
    root = out(start, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not root:
        raise SystemExit(f"not a Git repository: {start}")
    entries = parse_worktrees(out(start, "worktree", "list", "--porcelain"))
    primary = Path(entries[0]["path"])
    if fetch and out(primary, "remote"):
        git(primary, "fetch", "--prune", remote)
    target_ref = resolve_target(str(primary), remote, target)
    remote_url = out(primary, "remote", "get-url", remote)
    now = int(time.time())

    worktrees = []
    for index, entry in enumerate(entries):
        path = entry["path"]
        fact = dict(entry, primary=index == 0, exists=Path(path).is_dir(),
                    campaign=campaign_of(Path(path), primary))
        if not fact["exists"] or entry.get("bare"):
            worktrees.append(fact)
            continue
        commit = out(path, "log", "-1", "--format=%ct")
        activity = out(path, "log", "-g", "-1", "--format=%ct") or commit
        last = max(int(commit or 0), int(activity or 0)) or None
        fact.update(lastCommit=iso(int(commit)) if commit else None,
                    lastActivity=iso(last),
                    idleDays=round((now - last) / 86400, 1) if last else None,
                    changes=local_changes(path))
        if target_ref:
            behind, _, ahead = out(path, "rev-list", "--left-right", "--count",
                                   f"{target_ref}...HEAD").partition("\t")
            fact.update(behind=int(behind or 0), ahead=int(ahead or 0),
                        inTarget=in_target(path, target_ref))
        fact["onRemote"] = bool(out(path, "branch", "-r", "--contains", "HEAD"))
        if reviews and entry["branch"]:
            fact["review"] = review(str(primary), entry["branch"], remote_url)
        worktrees.append(fact)

    report = {"repository": str(primary), "target": target_ref,
              "targetCommit": out(primary, "rev-parse", target_ref) if target_ref else None,
              "worktrees": worktrees}
    if not target_ref:
        report["warning"] = (f"Target {target!r} was not found." if target else
                             f"No target branch found for remote {remote!r}; "
                             "pass --target to compare checkouts with it.")
    return report


def table(report: dict) -> str:
    rows = [("path", "branch", "idle", "ahead/behind", "in target", "changes", "lock")]
    for w in report["worktrees"]:
        changes = w.get("changes") or {}
        lock = w.get("locked")
        rows.append((
            w["path"],
            w["branch"] or "(detached)",
            f"{w['idleDays']}d" if w.get("idleDays") is not None else "-",
            f"{w.get('ahead', '-')}/{w.get('behind', '-')}",
            w.get("inTarget", "-"),
            "/".join(str(changes.get(k, 0)) for k in
                     ("staged", "unstaged", "untracked", "conflicted")),
            (lock if isinstance(lock, str) else "yes") if lock else "",
        ))
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip()
                     for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=".")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--target", help="target ref; defaults to the remote default branch")
    parser.add_argument("--fetch", action="store_true", help="fetch the remote first")
    parser.add_argument("--reviews", action="store_true", help="look up MRs/PRs with glab or gh")
    parser.add_argument("--format", choices=("json", "table"), default="json")
    args = parser.parse_args()
    if not shutil.which("git"):
        print("git was not found on PATH.", file=sys.stderr)
        return 1
    report = build_report(args.path, args.remote, args.target, args.fetch, args.reviews)
    if args.format == "table":
        print(table(report))
        if report.get("warning"):
            print(report["warning"], file=sys.stderr)
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
