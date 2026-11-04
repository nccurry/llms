"""Yesterday's Current Work is stale: P1 merged into the integration branch since."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import (
    add_worktree,
    commit,
    current_work,
    destination,
    expect,
    git,
    make_repo,
    packet,
    snapshot,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| REC-001 | `match` pairs a bank line with the ledger entry of the same amount and date. | `test_match` passes. |
| REC-002 | `report` lists unmatched lines. | `test_report` passes. |
"""

P1_DETAILS = "- Requirements: REC-001\n- Check: `test_match` passes."
P2_DETAILS = "- Requirements: REC-002\n- Check: `test_report` passes."
INTEGRATION = """Integration: children merge into `plc/reconcile`; it merges into `main` when
both phases pass.
"""

CHECKOUTS = [
    ("ledger-wt/reconcile/integration", "plc/reconcile", "parent", "integration"),
    ("ledger-wt/reconcile/p1-match", "plc/reconcile-p1", "p1 child", "in progress"),
    ("ledger-wt/reconcile/p2-report", "plc/reconcile-p2", "p2 child", "in progress"),
]

# The packet this one replaces, so the Replaces line points at a real folder.
ARCHIVED = """# Bank match

Match bank lines to ledger entries by amount alone.

## Current Work

- Status: Superseded — superseded by the reconcile packet, which also matches on date
- Owner: @alex
- Last updated: 2026-10-24
- Superseded by: `docs/plans/reconcile/`

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | Match by amount | | Dropped — superseded by reconcile P1 |

## Log

- 2026-10-18 Created.
- 2026-10-24 Superseded by the reconcile packet.
"""

dest = destination()
app = make_repo(dest, "ledger", {"README.md": "# ledger\n"})
integration = add_worktree(app, "reconcile", "integration", "plc/reconcile")
start = git(integration, "rev-parse", "--short", "HEAD")
files = packet(
    "reconcile",
    "Reconcile",
    "Match bank statement lines to ledger entries, and list the lines left unmatched.",
    current_work(
        last_updated=f"2026-10-26, `plc/reconcile` at `{start}`",
        next_action="finish P1 and merge it into `plc/reconcile`",
        current_state=(
            "P1 and P2 in progress in their worktrees;"
            " nothing merged into `plc/reconcile` yet."
        ),
        checkouts=CHECKOUTS,
        more_keys=["Replaces: `docs/plans/archived/bank-match/`"],
    ),
    [
        ("P1", "Match lines", "In progress", P1_DETAILS),
        ("P2", "Unmatched report", "In progress", P2_DETAILS),
    ],
    REQUIREMENTS,
    log=["2026-10-24 Created.", "2026-10-25 P1 and P2 started in their worktrees."],
    plan_note=INTEGRATION,
)
files["docs/plans/archived/bank-match/README.md"] = ARCHIVED
commit(integration, "docs(plan): add reconcile PLC", files)

p1 = add_worktree(app, "reconcile", "p1-match", "plc/reconcile-p1", "plc/reconcile")
commit(
    p1,
    "feat(reconcile): match bank lines to ledger entries (REC-001)",
    {
        "src/reconcile.py": (
            "def match(line, entries):\n"
            "    for entry in entries:\n"
            "        if (entry['amount'], entry['date']) == (line['amount'], line['date']):\n"
            "            return entry\n"
            "    return None\n"
        ),
        "tests/test_reconcile.py": (
            "from src.reconcile import match\n\n\n"
            "def test_match():\n"
            "    entry = {'amount': 5, 'date': '2026-10-01'}\n"
            "    assert match({'amount': 5, 'date': '2026-10-01'}, [entry]) is entry\n"
            "    assert match({'amount': 6, 'date': '2026-10-01'}, [entry]) is None\n"
        ),
    },
)
p2 = add_worktree(app, "reconcile", "p2-report", "plc/reconcile-p2", "plc/reconcile")
commit(
    p2,
    "wip(reconcile): start unmatched report (REC-002)",
    {"src/report.py": "def report(lines, entries):\n    raise NotImplementedError\n"},
)

# Late yesterday, after the Current Work block above was written, P1 merged into integration.
git(integration, "merge", "-q", "--no-ff", "plc/reconcile-p1", "-m", "Merge P1 (REC-001)")

snapshot(dest, [app])
expect(
    dest,
    removed_worktrees=["ledger-wt/reconcile/p1-match"],
    deleted_branches={"ledger": ["plc/reconcile-p1"]},
)
print(dest)
