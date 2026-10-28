"""A one-phase PLC whose only phase is done on its branch. Wrapping it up completes the PLC."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from digest_fixture import build, expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plc-checkpoint"))
from fixture_lib import destination  # noqa: E402

dest = destination()
tips = build(dest, "complete")
expect(
    dest,
    merged=[tips["p1"]],
    removed_worktrees=["notify-wt/digest/p1-email"],
    deleted_branches=["plc/digest-p1"],
    deleted_remote_branches=["plc/digest-p1"],
    remote_files=["docs/plans/done/digest/README.md"],
    absent_remote_files=["docs/plans/digest/README.md"],
)
print(dest)
