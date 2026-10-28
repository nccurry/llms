"""P1 is done and pushed; P2 is half done. The user wants it all merged now."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from digest_fixture import build, expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plc-checkpoint"))
from fixture_lib import destination  # noqa: E402

dest = destination()
tips = build(dest, "mid-stream")
expect(
    dest,
    merged=[tips["p1"], tips["p2"]],
    removed_worktrees=["notify-wt/digest/p1-email", "notify-wt/digest/p2-slack"],
    deleted_branches=["plc/digest-p1", "plc/digest-p2"],
    deleted_remote_branches=["plc/digest-p1"],
    remote_files=["docs/plans/digest/README.md"],
    absent_remote_files=["docs/plans/done/digest/README.md"],
)
print(dest)
