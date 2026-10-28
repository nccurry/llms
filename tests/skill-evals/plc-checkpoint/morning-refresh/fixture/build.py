"""Yesterday's Status is stale: P1 merged into the integration branch since."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import (
    add_worktree,
    commit,
    destination,
    expect,
    git,
    make_repo,
    packet,
    snapshot,
    current_work,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| REC-001 | `match` pairs a bank line with the ledger entry of the same amount and date. | `test_match` passes. |
| REC-002 | `report` lists unmatched lines. | `test_report` passes. |
"""

PLAN = """## Phase Summary

| Phase | Goal | Requirements | Validation |
| --- | --- | --- | --- |
| P1 | Match lines | REC-001 | `test_match` |
| P2 | Unmatched report | REC-002 | `test_report` |

Integration: children merge into `plc/reconcile`; it merges into `main` when
both phases pass.
"""

CHECKOUTS = [
    ("ledger-wt/reconcile/integration", "plc/reconcile", "integration"),
    ("ledger-wt/reconcile/p1-match", "plc/reconcile-p1", "in progress"),
    ("ledger-wt/reconcile/p2-report", "plc/reconcile-p2", "in progress"),
]

dest = destination()
app = make_repo(dest, "ledger", {"README.md": "# ledger\n"})
integration = add_worktree(app, "reconcile", "integration", "plc/reconcile")
start = git(integration, "rev-parse", "--short", "HEAD")
status = current_work(
    last_updated=f"2026-10-26, `plc/reconcile` at `{start}`",
    rows=[
        ("P1 (REC-001)", "in progress", "p1 child", "none yet"),
        ("P2 (REC-002)", "in progress", "p2 child", "none yet"),
    ],
    checkouts=CHECKOUTS,
    next_action="finish P1 and merge it into `plc/reconcile`",
)
commit(
    integration,
    "docs(plan): add reconcile PLC",
    packet("reconcile", REQUIREMENTS, PLAN, status=status),
)

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
