"""Check a plc-wrapup run on the merge request route, against the
_expect.json its fixture wrote and the fake host's state.

Usage: check_mr_route.py <dest>. Prints JSON and exits 1 when a rule fails.

Rules, each a failure when broken:
- The fake host has an open merge request from `branch` to `target`, not
  merged and not set to merge when green: the user asked to leave it for
  review.
- `main` on the remote is where it started.
- The remote `branch` still holds `branch_start`.
- The plan at `plan` on the remote `branch` passes fixture_lib's
  packet_shape_problems, with the `owner` rule; its status is one of
  `statuses` and `phase` is one of `phase_states`.
- Each of `removed_worktrees` is unregistered and its folder gone, and
  "Where the work lives" no longer names it.
- The primary checkout is still on `main`.

Suggestions, reported but never a failure, since plc-planning encourages
but does not require recording merge requests:
- `merge_requests_row`: the plan's `## Merge requests` table has a row for
  `phase` that names the open merge request, with State `Open`.
- `plan_line`: the merge request's description has a
  `Plan: <packet ID or slug> <phase>` line, using one of `plan_names`.
Each one missing is listed in `missed_suggestions`.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixture_lib import (  # noqa: E402
    GIT_ENV,
    format_check,
    listed_checkouts,
    packet_shape_problems,
    packet_status,
    phase_state,
    run_git,
    section_lines,
    worktree_paths,
)
from host_fixture import host_state  # noqa: E402

REPO = "app"


def plan_on_branch(dest: Path, branch: str, path: str) -> str | None:
    """A tar archive of the plan folder on the remote branch, or None when
    the branch or folder is not there."""
    archive = subprocess.run(
        ["git", "--git-dir", str(dest / f"{REPO}.git"), "archive", "--format=tar",
         f"refs/heads/{branch}", path],
        capture_output=True,
        env=GIT_ENV,
    )
    return archive.stdout if archive.returncode == 0 else None


def names_mr(cell: str, number: int) -> bool:
    """True when a Merge request cell names merge request `number`: `!N`, a
    URL ending in `/N`, or a link whose text or target does."""
    return re.search(rf"(?:!|/){number}(?![\d])", cell) is not None


def has_mr_row(readme: str, phase: str, number: int) -> bool:
    fc = format_check()
    rows = [fc.cells(line) for line in section_lines(readme, "Merge requests")
            if line.lstrip().startswith("|")]
    return any(
        len(row) >= 3 and row[0].strip("*_` ") == phase and names_mr(row[1], number)
        and row[2].strip() == "Open"
        for row in rows[2:]
    )


def has_plan_line(body: str, names: list[str], phase: str) -> bool:
    alternatives = "|".join(re.escape(name) for name in names)
    pattern = rf"^\s*(?:[-*]\s+)?(?:\*\*)?Plan:(?:\*\*)?\s+`?(?:{alternatives})`?\s+`?{re.escape(phase)}\b"
    return re.search(pattern, body, flags=re.MULTILINE | re.IGNORECASE) is not None


class Checker:
    def __init__(self, dest: Path):
        self.dest = dest
        self.app = dest / REPO
        self.expect = json.loads((dest / "_expect.json").read_text(encoding="utf-8"))
        self.failures: list[str] = []
        self.suggestions = {"merge_requests_row": False, "plan_line": False}

    def remote(self, *args: str) -> subprocess.CompletedProcess:
        return run_git(self.dest, "--git-dir", str(self.dest / f"{REPO}.git"), *args)

    def run(self) -> dict:
        mr = self.check_merge_request()
        self.check_remote()
        readme = self.check_plan()
        self.check_worktrees(readme)
        branch = run_git(self.app, "branch", "--show-current").stdout.strip()
        if branch != "main":
            self.failures.append(f"primary checkout switched from main to {branch or 'a detached HEAD'}")
        if mr is not None:
            phase = self.expect["phase"]
            self.suggestions["merge_requests_row"] = readme is not None and has_mr_row(
                readme, phase, mr["number"]
            )
            self.suggestions["plan_line"] = has_plan_line(mr["body"], self.expect["plan_names"], phase)
        return {
            "ok": not self.failures,
            "failures": self.failures,
            "suggestions": self.suggestions,
            "missed_suggestions": [name for name, met in self.suggestions.items() if not met],
        }

    def check_merge_request(self) -> dict | None:
        branch, target = self.expect["branch"], self.expect["target"]
        mrs = [mr for mr in host_state(self.dest)["mrs"]
               if mr["source"] == branch and mr["target"] == target]
        if not mrs:
            self.failures.append(f"no merge request from {branch} to {target}")
            return None
        mr = mrs[-1]
        if mr["state"] != "opened" or mr["auto_merge"]:
            self.failures.append(
                f"merge request !{mr['number']} was merged or set to merge, "
                "but the user asked to leave it for review"
            )
        return mr

    def check_remote(self) -> None:
        main = self.remote("rev-parse", "refs/heads/main").stdout.strip()
        if main != self.expect["main"]:
            self.failures.append("main on the remote moved; the work must reach it through the merge request")
        branch = self.expect["branch"]
        start = self.expect["branch_start"]
        contains = self.remote("merge-base", "--is-ancestor", start, f"refs/heads/{branch}")
        if contains.returncode:
            self.failures.append(f"{branch} on the remote no longer holds its starting commit")

    def check_plan(self) -> str | None:
        path, branch = self.expect["plan"], self.expect["branch"]
        label = f"plan {path} on {branch}"
        archive = plan_on_branch(self.dest, branch, path)
        if archive is None:
            self.failures.append(f"{label} is missing")
            return None
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(root, filter="data")
            packet = root / path
            if not (packet / "README.md").is_file():
                self.failures.append(f"{label} has no README.md")
                return None
            prefix = f"{root.as_posix()}/"
            for problem in packet_shape_problems(packet, owner=self.expect["owner"]):
                self.failures.append(f"{label}: {problem.replace(prefix, '')}")
            readme = (packet / "README.md").read_text(encoding="utf-8")
        status = packet_status(readme)
        if status not in self.expect["statuses"]:
            wanted = " or ".join(self.expect["statuses"])
            self.failures.append(f"{label}: status is {status or 'missing'}, expected {wanted}")
        phase = self.expect["phase"]
        state = phase_state(readme, phase)
        if state not in self.expect["phase_states"]:
            wanted = " or ".join(self.expect["phase_states"])
            self.failures.append(f"{label}: phase {phase} is {state or 'missing'}, expected {wanted}")
        return readme

    def check_worktrees(self, readme: str | None) -> None:
        registered = {path.resolve() for path in worktree_paths(self.app, check=False)}
        listed = listed_checkouts(readme) if readme else []
        for rel in self.expect["removed_worktrees"]:
            path = (self.dest / rel).resolve()
            if path in registered:
                self.failures.append(f"worktree {rel} is still registered")
            if path.exists():
                self.failures.append(f"worktree {rel} folder still exists")
            if path not in registered and any(rel in cell for cell in listed):
                self.failures.append(f"Where the work lives still names removed {rel}")


def check(dest: Path) -> dict:
    return Checker(dest).run()


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: check_mr_route.py <fixture-folder>")
    report = check(Path(sys.argv[1]).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
