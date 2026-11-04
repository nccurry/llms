"""The only phase passes its tests, but its branch never implemented DIG-003.

P1 covers the email header (DIG-001) and footer (DIG-003). Its branch adds the
header and its test only, so `run_tests.py` passes while DIG-003 is unmet and
its check, `test_email_footer`, does not exist.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from digest_fixture import build, expect, open_plan_with_unbuilt_part  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination  # noqa: E402

README = "docs/plans/digest/README.md"
SRD = "docs/plans/digest/SRD.md"

dest = destination()
tips = build(dest, "unmet")
expect(
    dest,
    merged=[tips["p1"]],
    removed_worktrees=["notify-wt/digest/p1-email"],
    deleted_branches=["plc/digest-p1"],
    deleted_remote_branches=["plc/digest-p1"],
    absent_remote_files=["docs/plans/completed/digest/README.md"],
    # The README starts with no mention of DIG-003, so naming it shows the gap
    # was recorded; SRD.md must still list it.
    remote_text={README: ["DIG-003"], SRD: ["DIG-003"]},
    # P1 still holds DIG-003, which nobody built.
    plans=[open_plan_with_unbuilt_part("P1", ["P1"])],
)
print(dest)
