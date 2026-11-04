"""Check what a plc-planning eval run wrote, against the fixture's _snapshot.json.

A small, bounded change gets one plan file and nothing else: a one-file plan
`docs/plans/planned/plc-<slug>.md`, named by the planning skill's format check
rule for one-file plans. The skill chooses a one-file plan when no trigger
in its Adding files rule holds, as here, and the fixture's
`docs/plans/README.md` names that shape for small work. No packet folder, side
file or other file may appear, no code may change, and history must not be
rewritten.
The plan must pass the shipped format check in strict mode, as a packet in
`planned/`, and the evals' own rules for new packets, including an Owner line
that names `@alex`, as the prompt asks.

Usage:
  python check_plan.py <fixture-folder>

Prints a JSON report and exits 0 when the run passes, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture_lib import (  # noqa: E402
    format_check,
    git,
    is_ancestor,
    packet_shape_problems,
    status_paths,
)

REPO = "harbor"
PLANNED = "docs/plans/planned/"


def changed_paths(app: Path, start: str) -> list[str]:
    """Paths committed since `start`, plus uncommitted and untracked ones."""
    committed = git(app, "diff", "-z", "--name-only", start, "HEAD", check=False).split("\0")
    return sorted((set(committed) | status_paths(app)) - {""})


def is_plan_file(app: Path, path: str) -> bool:
    """True for a one-file plan directly under `planned/`."""
    if not path.startswith(PLANNED) or "/" in path[len(PLANNED) :]:
        return False
    return format_check().is_packet(app / path)


def check(dest: Path) -> dict:
    snap = json.loads((dest / "_snapshot.json").read_text(encoding="utf-8"))
    start = snap["checkouts"][REPO]["worktrees"][REPO]["head"]
    app = dest / REPO
    problems: list[str] = []

    if not is_ancestor(app, start, "HEAD"):
        problems.append("history rewritten or reset")
    changed = changed_paths(app, start)
    plans = [path for path in changed if is_plan_file(app, path) and (app / path).is_file()]
    others = [path for path in changed if path not in plans]
    if others:
        problems.append(f"changed beyond the one plan file: {others}")
    if len(plans) != 1:
        problems.append(f"expected one new plan in {PLANNED}, found {plans or 'none'}")
    else:
        # Findings name the plan relative to the repository, as git does.
        problems += [
            problem.replace(f"{app.as_posix()}/", "")
            for problem in packet_shape_problems(app / plans[0], owner="@alex")
        ]

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
