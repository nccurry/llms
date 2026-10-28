"""The mid-stream fixture, but the user only asks where things stand."""

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
    not_merged=[tips["p1"], tips["p2"]],
    kept_worktrees=["notify-wt/digest/p1-email", "notify-wt/digest/p2-slack"],
    kept_branches=["plc/digest-p1", "plc/digest-p2"],
)
print(dest)
