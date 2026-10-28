"""Another session holds a lock on the P2 worktree. Only P1 can be wrapped up."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from digest_fixture import build, expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plc-checkpoint"))
from fixture_lib import destination  # noqa: E402

dest = destination()
tips = build(dest, "active-agent")
expect(
    dest,
    merged=[tips["p1"]],
    not_merged=[tips["p2"]],
    removed_worktrees=["notify-wt/digest/p1-email"],
    deleted_branches=["plc/digest-p1"],
    deleted_remote_branches=["plc/digest-p1"],
    kept_worktrees=["notify-wt/digest/p2-slack"],
    locked_worktrees=["notify-wt/digest/p2-slack"],
    kept_branches=["plc/digest-p2"],
    remote_files=["docs/plans/digest/README.md"],
)
print(dest)
