"""The only phase passes its tests, but its branch never implemented DIG-003.

P1 covers the email header (DIG-001) and footer (DIG-003). Its branch adds the
header and its test only, so `run_tests.py` passes while DIG-003 is unmet and
its check, `test_email_footer`, does not exist.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from digest_fixture import build, expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plc-checkpoint"))
from fixture_lib import destination  # noqa: E402

README = "docs/plans/digest/README.md"

dest = destination()
tips = build(dest, "unmet")
expect(
    dest,
    merged=[tips["p1"]],
    removed_worktrees=["notify-wt/digest/p1-email"],
    deleted_branches=["plc/digest-p1"],
    deleted_remote_branches=["plc/digest-p1"],
    remote_files=[README],
    absent_remote_files=["docs/plans/completed/digest/README.md"],
    remote_text={README: ["- Owner: @alex"]},
    absent_remote_text={README: ["- Status: Complete", "Historical record as of"]},
)
print(dest)
