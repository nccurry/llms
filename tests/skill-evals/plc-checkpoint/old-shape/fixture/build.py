"""An active packet still in an older shape, and P1 has merged since its status
was written.

The README has a `## Status` section with a bare `Status:` paragraph and older
key names, and the summary sits under `## Summary`. Phase state lives in a
Phase Status table in the implementation plan. There is no `## Log`. This
fixture keeps that shape on purpose: the case checks that the packet is
converted to the shared template before its status is updated.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import (
    add_worktree,
    commit,
    destination,
    expect,
    git,
    make_repo,
    phase_rule,
    snapshot,
)

PACKET = "docs/plans/audit-log"
# The line step M5 writes where the phase table was, and the line step M8
# puts under `## Done when` in a repository with no README template of its own.
POINTER_LINE = "Phase state lives in the README's [Phases](README.md#phases) table."
DONE_WHEN_LINE = "The requirements and their checks are in [SRD.md](SRD.md)."


def readme(start: str) -> str:
    return f"""# Audit log PLC

## Status

Status: In progress

- Owner: @alex
- Updated: 2026-10-22, `main` at `{start}`
- Current phase: P1 in progress in `marina-wt/audit-log/p1-record`
- Next step: finish P1 and merge it into `main`
- Blockers: none
- Created: 2026-10-20
- Folder: {PACKET}

## Summary

Record who changed each berth booking, so support can answer "who changed
this?" without reading server logs.

The record is written in the same transaction as the booking change.

## Packet

- [SRD.md](SRD.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
"""


SRD = """# Audit log requirements

| ID | Requirement | Acceptance |
| --- | --- | --- |
| AUD-001 | Each booking change records who made it. | `test_record_user` passes. |
| AUD-002 | `marina audit` lists the last 20 records, newest first. | `test_audit_order` passes. |
"""

PLAN = """# Audit log implementation plan

Lifecycle status: In progress

## Phase Status

| Phase | Name | Requirements | Status |
| --- | --- | --- | --- |
| P1 | Record changes | AUD-001 | In progress |
| P2 | Audit command | AUD-002 | Not started |

## P1: Record changes

- Add `record(change, user)` and call it from `save_booking`.
- Check: `test_record_user` passes.

## P2: Audit command

- `marina audit` prints the last 20 records, newest first.
- Check: `test_audit_order` passes.
"""

dest = destination()
app = make_repo(dest, "marina", {"README.md": "# marina\n"})
start = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): add audit log PLC",
    {
        f"{PACKET}/README.md": readme(start),
        f"{PACKET}/SRD.md": SRD,
        f"{PACKET}/IMPLEMENTATION_PLAN.md": PLAN,
    },
)
git(app, "push", "-q", "origin", "main")
p1 = add_worktree(app, "audit-log", "p1-record", "plc/audit-log-p1")
commit(
    p1,
    "feat(audit): record who changed each booking (AUD-001)",
    {
        "src/audit.py": (
            "RECORDS = []\n\n\n"
            "def record(change, user):\n"
            "    RECORDS.append({'change': change, 'user': user})\n"
        ),
        "tests/test_audit.py": (
            "from src.audit import RECORDS, record\n\n\n"
            "def test_record_user():\n"
            "    record('berth A1 moved', 'sam')\n"
            "    assert RECORDS[-1] == {'change': 'berth A1 moved', 'user': 'sam'}\n"
        ),
    },
)
# After the Status above was written, P1 merged into main and was pushed.
git(app, "merge", "-q", "--no-ff", "plc/audit-log-p1", "-m", "Merge P1 audit records (AUD-001)")
git(app, "push", "-q", "origin", "main")

snapshot(dest, [app])
# P1 is merged and its worktree is clean, so its worktree and branch are finished.
expect(
    dest,
    removed_worktrees=["marina-wt/audit-log/p1-record"],
    deleted_branches={"marina": ["plc/audit-log-p1"]},
    # P1 merged `record` but nobody built the call from `save_booking`, so it
    # stays In progress unless the call moves to a new row, and then must be
    # Merged or Verified. Steps M5 and M8 leave their lines, and the rewritten
    # Current Work no longer lists the removed p1-record worktree.
    packet_content={
        "path": f"marina/{PACKET}",
        "phases": {"P1": phase_rule(["In progress"], ["Merged", "Verified"], ["P1", "P2"])},
        "plan_has": [POINTER_LINE],
        "plan_lacks": ["## Phase Status"],
        "done_when": DONE_WHEN_LINE,
        "lists_no_removed_checkouts": True,
    },
)
print(dest)
