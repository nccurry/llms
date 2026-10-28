"""The packet-drift fixture, with another agent mid-edit on the worktree's packet."""

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import snapshot

dest = Path(sys.argv[1]).resolve()
runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "packet-drift" / "fixture" / "build.py"),
    run_name="__main__",
)

# Another agent is partway through editing the worktree's plan.
plan = (
    dest
    / "billing-wt"
    / "invoice-export"
    / "p1-csv"
    / "docs"
    / "plans"
    / "invoice-export"
    / "IMPLEMENTATION_PLAN.md"
)
with plan.open("a", encoding="utf-8", newline="\n") as file:
    file.write("\n## P2 notes (p2 child, in progress)\n\n- JSON field order: TBD\n")

snapshot(dest, [dest / "billing"])
