"""Each branch passes alone, but P2's test fails once P1 is merged in."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from digest_fixture import build, expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plc-checkpoint"))
from fixture_lib import destination  # noqa: E402

dest = destination()
tips = build(dest, "failing")
expect(
    dest,
    not_merged=[tips["p2"]],
    kept_worktrees=["notify-wt/digest/p2-slack"],
    kept_branches=["plc/digest-p2"],
)
print(dest)
