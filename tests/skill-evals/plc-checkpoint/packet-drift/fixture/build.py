"""Main's packet says nothing has started; the worktree's copy shows P1 implemented."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import (
    add_worktree,
    commit,
    current_work,
    destination,
    git,
    make_repo,
    packet,
    snapshot,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| EXP-001 | `export_csv` writes one CSV row per invoice. | `test_export_csv` passes. |
| EXP-002 | `export --json` writes the same fields as CSV. | `test_export_json` passes. |
"""

SUMMARY = "Export invoices as CSV and JSON, so accounts can load them into a spreadsheet."
BRANCH = "plc/invoice-export-p1"


def plan(evidence: str) -> str:
    return f"""### P1: CSV export

- Requirements: EXP-001
- Check: `test_export_csv` passes.
- Evidence: {evidence}

### P2: JSON export

- Requirements: EXP-002
- Check: `test_export_json` passes.
"""


def planned_packet(start: str) -> dict[str, str]:
    """The packet as written on main, before any work started."""
    return packet(
        "invoice-export",
        "Invoice export",
        SUMMARY,
        current_work(
            last_updated=f"2026-10-24, `main` at `{start}`",
            next_action="start P1 in a worktree",
            current_state="Nothing started.",
            status="Planned",
        ),
        [("P1", "CSV export", "Planned"), ("P2", "JSON export", "Planned")],
        REQUIREMENTS,
        plan("none yet."),
    )


def implemented_packet(feature: str) -> dict[str, str]:
    """The worktree's copy, after P1 was implemented on its branch."""
    return packet(
        "invoice-export",
        "Invoice export",
        SUMMARY,
        current_work(
            last_updated=f"2026-10-25, `{BRANCH}` at `{feature}`",
            next_action="merge P1 into `main`",
            current_state=(
                f"P1 implemented on `{BRANCH}`; `test_export_csv` passed locally"
                " on that branch. P2 not started."
            ),
            checkouts=[("billing-wt/invoice-export/p1-csv", BRANCH, "p1 child", "in progress")],
        ),
        [
            (
                "P1",
                "CSV export",
                f"Implemented — `{feature}` on `{BRANCH}`; `test_export_csv` passed locally",
            ),
            ("P2", "JSON export", "Planned"),
        ],
        REQUIREMENTS,
        plan(f"`test_export_csv` passed locally on `{BRANCH}` at `{feature}`."),
        log=["2026-10-24 Created.", f"2026-10-25 P1 Implemented on `{BRANCH}` @ `{feature}`."],
    )


EXPORT_CODE = """import csv
import io


def export_csv(invoices):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    for invoice in invoices:
        writer.writerow([invoice["id"], invoice["total"]])
    return out.getvalue()
"""

EXPORT_TEST = """from src.export import export_csv


def test_export_csv():
    invoices = [{"id": 1, "total": 5}, {"id": 2, "total": 7}]
    assert export_csv(invoices).splitlines() == ["1,5", "2,7"]
"""

dest = destination()
app = make_repo(dest, "billing", {"README.md": "# billing\n"})
start = git(app, "rev-parse", "--short", "HEAD")
commit(app, "docs(plan): add invoice export PLC", planned_packet(start))
git(app, "push", "-q", "origin", "main")
p1 = add_worktree(app, "invoice-export", "p1-csv", BRANCH)
feature = commit(
    p1,
    "feat(export): write invoices as CSV (EXP-001)",
    {
        "src/export.py": EXPORT_CODE,
        "tests/test_export.py": EXPORT_TEST,
    },
)
commit(p1, "docs(plan): record P1 progress", implemented_packet(feature))
snapshot(dest, [app])
print(dest)
