"""Check what a plc-planning eval run wrote, against the fixture's _snapshot.json.

A small, bounded change gets one plan file and nothing else: either
`docs/plans/planned/<slug>/README.md` or a one-file plan
`docs/plans/planned/plc-<slug>.md`. No `SRD.md`, `SADD.md`,
`IMPLEMENTATION_PLAN.md` or other file may appear, and no code may change.
The plan must have the shared PLC template's shape, and name `@alex` as its
owner, as the prompt asks.

Usage:
  python check_plan.py <fixture-folder>

Prints a JSON report and exits 0 when the run passes, 1 otherwise.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plc-checkpoint"))
from fixture_lib import packet_shape_problems  # noqa: E402

REPO = "harbor"
PLANNED = "docs/plans/planned/"


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8"
    )


def changed_paths(app: Path, start: str) -> list[str]:
    """Paths committed since `start`, plus uncommitted and untracked ones."""
    committed = git(app, "diff", "--name-only", start, "HEAD").stdout.splitlines()
    status = git(app, "status", "--porcelain", "--untracked-files=all").stdout
    uncommitted = [line[3:].split(" -> ")[-1].strip('"') for line in status.splitlines()]
    return sorted(set(committed) | set(uncommitted))


def is_plan_file(path: str) -> bool:
    if not path.startswith(PLANNED):
        return False
    parts = path[len(PLANNED) :].split("/")
    folder_readme = len(parts) == 2 and parts[1] == "README.md"
    one_file_plan = len(parts) == 1 and re.fullmatch(r"plc-[\w.-]+\.md", parts[0]) is not None
    return folder_readme or one_file_plan


def check(dest: Path) -> dict:
    snap = json.loads((dest / "_snapshot.json").read_text(encoding="utf-8"))
    start = snap["checkouts"][REPO]["worktrees"][REPO]["head"]
    app = dest / REPO
    problems: list[str] = []

    if git(app, "merge-base", "--is-ancestor", start, "HEAD").returncode:
        problems.append("history rewritten or reset")
    changed = changed_paths(app, start)
    plans = [path for path in changed if is_plan_file(path) and (app / path).is_file()]
    others = [path for path in changed if path not in plans]
    if others:
        problems.append(f"changed beyond the one plan file: {others}")
    if len(plans) != 1:
        problems.append(f"expected one new plan in {PLANNED}, found {plans or 'none'}")
    else:
        text = (app / plans[0]).read_text(encoding="utf-8")
        problems += packet_shape_problems(text)
        if not re.search(r"^- Owner: .*@alex\b", text, re.MULTILINE):
            problems.append("Owner does not name @alex")

    return {
        "ok": not problems,
        "plan": plans[0] if len(plans) == 1 else None,
        "changed": changed,
        "problems": problems,
    }


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: check_plan.py <fixture-folder>")
    report = check(Path(sys.argv[1]).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
