#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
import argparse
import json
import os
import subprocess
import sys


def run_git(path, args, check=False):
    result = subprocess.run(
        ["git", "-C", path, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message)

    return result


def ref_exists(path, ref):
    return run_git(path, ["show-ref", "--verify", "--quiet", ref]).returncode == 0


def normalize_path(path):
    return os.path.normcase(os.path.abspath(path))


def same_path(left, right):
    return normalize_path(left) == normalize_path(right)


def is_inside_path(child, parent):
    child_path = normalize_path(child)
    parent_path = normalize_path(parent)

    try:
        return os.path.commonpath([child_path, parent_path]) == parent_path
    except ValueError:
        return False


def parse_worktrees(output):
    worktrees = []
    current = None

    for line in output.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                worktrees.append(current)
            current = {
                "path": line[len("worktree ") :],
                "head": None,
                "branchRef": None,
                "branch": None,
                "detached": False,
                "bare": False,
            }
            continue

        if current is None:
            continue

        if line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            branch_ref = line[len("branch ") :]
            current["branchRef"] = branch_ref
            if branch_ref.startswith("refs/heads/"):
                current["branch"] = branch_ref[len("refs/heads/") :]
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True

    if current is not None:
        worktrees.append(current)

    return worktrees


def worktree_status(path):
    if not os.path.isdir(path):
        return None

    result = run_git(path, ["status", "--porcelain=v1"])
    if result.returncode != 0:
        return None

    return result.stdout.splitlines()


def choose_main_branch(path, requested):
    if requested:
        if ref_exists(path, f"refs/heads/{requested}"):
            return requested

        remotes = run_git(path, ["remote"]).stdout.splitlines()
        for remote in remotes:
            if ref_exists(path, f"refs/remotes/{remote}/{requested}"):
                return requested

        return None

    for candidate in ("main", "master"):
        if ref_exists(path, f"refs/heads/{candidate}"):
            return candidate

    default_remote = run_git(path, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
    default_remote_name = default_remote.stdout.strip()
    if "/" in default_remote_name:
        return default_remote_name.split("/", 1)[1]

    remotes = run_git(path, ["remote"]).stdout.splitlines()
    for candidate in ("main", "master"):
        for remote in remotes:
            if ref_exists(path, f"refs/remotes/{remote}/{candidate}"):
                return candidate

    return None


def choose_remote_main_ref(path, main_branch):
    if not main_branch:
        return None

    remotes = run_git(path, ["remote"]).stdout.splitlines()
    preferred = ["origin", *[remote for remote in remotes if remote != "origin"]]

    for remote in preferred:
        remote_ref = f"refs/remotes/{remote}/{main_branch}"
        if ref_exists(path, remote_ref):
            return f"{remote}/{main_branch}"

    return None


def make_target_report(root, worktrees, branch, target_path):
    report = {
        "targetBranch": branch,
        "targetBranchExists": False,
        "targetBranchWorktreePath": None,
        "targetPath": os.path.abspath(target_path) if target_path else None,
        "targetPathExists": False,
        "targetPathInsideExistingWorktree": None,
    }

    if branch:
        report["targetBranchExists"] = ref_exists(root, f"refs/heads/{branch}")
        for worktree in worktrees:
            if worktree.get("branch") == branch:
                report["targetBranchWorktreePath"] = worktree["path"]
                break

    if target_path:
        target_abs = os.path.abspath(target_path)
        report["targetPathExists"] = os.path.exists(target_abs)

        for worktree in worktrees:
            worktree_path = worktree["path"]
            if same_path(target_abs, worktree_path) or is_inside_path(target_abs, worktree_path):
                report["targetPathInsideExistingWorktree"] = worktree_path
                break

    return report


def build_report(path, requested_main, target_branch, target_path):
    root = run_git(path, ["rev-parse", "--show-toplevel"], check=True).stdout.strip()
    branch = run_git(root, ["branch", "--show-current"], check=True).stdout.strip()
    worktrees = parse_worktrees(run_git(root, ["worktree", "list", "--porcelain"], check=True).stdout)
    main_branch = choose_main_branch(root, requested_main)
    remote_main_ref = choose_remote_main_ref(root, main_branch)
    base_ref = remote_main_ref or main_branch
    remotes = run_git(root, ["remote"]).stdout.splitlines()

    current_worktree = None
    main_worktree = None
    primary_worktree = worktrees[0] if worktrees else None

    for worktree in worktrees:
        status_lines = worktree_status(worktree["path"]) if not worktree.get("bare") else None
        worktree["isDirty"] = bool(status_lines)
        worktree["statusLines"] = status_lines or []

        if same_path(worktree["path"], root):
            current_worktree = worktree
        if main_branch and worktree.get("branch") == main_branch:
            main_worktree = worktree

    target = make_target_report(root, worktrees, target_branch, target_path)

    problems = []
    warnings = []

    if current_worktree is None:
        problems.append("Current path was not found in git worktree list output.")
    if not main_branch:
        problems.append("No local main/master branch or remote default branch was found.")
    if target["targetBranchExists"]:
        problems.append(f"Target branch already exists: {target_branch}.")
    if target["targetPathExists"]:
        problems.append(f"Target path already exists: {target['targetPath']}.")
    if target["targetPathInsideExistingWorktree"]:
        problems.append(
            f"Target path is inside an existing worktree: {target['targetPathInsideExistingWorktree']}."
        )

    if current_worktree and current_worktree["isDirty"]:
        warnings.append("Current worktree has uncommitted changes; leave them untouched.")
    if main_worktree and main_worktree["isDirty"]:
        warnings.append("Main worktree has uncommitted changes; do not pull there.")
    if remotes and not remote_main_ref:
        warnings.append("Repository has remotes, but no remote main ref was found before fetch.")

    return {
        "repoRoot": root,
        "repoName": os.path.basename(root),
        "currentBranch": branch or None,
        "mainBranch": main_branch,
        "remoteMainRef": remote_main_ref,
        "baseRef": base_ref,
        "remotes": remotes,
        "currentWorktreePath": current_worktree["path"] if current_worktree else root,
        "primaryWorktreePath": primary_worktree["path"] if primary_worktree else None,
        "mainWorktreePath": main_worktree["path"] if main_worktree else None,
        "worktreeCount": len(worktrees),
        "worktrees": worktrees,
        "target": target,
        "warnings": warnings,
        "problems": problems,
        "canProceed": not problems,
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect git state before starting an isolated worktree.")
    parser.add_argument("--path", default=".", help="Repository path to inspect.")
    parser.add_argument("--main", help="Main branch name to require instead of auto-detecting main/master.")
    parser.add_argument("--branch", help="Target feature branch to check.")
    parser.add_argument("--worktree-path", help="Target linked worktree path to check.")
    args = parser.parse_args()

    try:
        report = build_report(args.path, args.main, args.branch, args.worktree_path)
    except Exception as exc:
        print(json.dumps({"canProceed": False, "problems": [str(exc)]}, indent=2))
        return 1

    print(json.dumps(report, indent=2))
    return 0 if report["canProceed"] else 2


if __name__ == "__main__":
    sys.exit(main())
