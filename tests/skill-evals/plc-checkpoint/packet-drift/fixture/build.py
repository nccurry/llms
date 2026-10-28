"""Main's packet says everything is pending; the worktree's copy shows P1 done."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import add_worktree, commit, destination, make_repo, packet, snapshot

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| EXP-001 | `export_csv` writes one CSV row per invoice. | `test_export_csv` passes. |
| EXP-002 | `export --json` writes the same fields as CSV. | `test_export_json` passes. |
"""


def plan(p1_state: str) -> str:
    started = p1_state != "Planned"
    evidence = "`test_export_csv` passed locally on this branch" if started else "none"
    state = "Implemented; awaiting merge" if started else "Pending"
    return f"""## Phase Summary

| Phase | Goal | Requirements | Validation | Status |
| --- | --- | --- | --- | --- |
| P1 | CSV export | EXP-001 | `test_export_csv` | {p1_state} |
| P2 | JSON export | EXP-002 | `test_export_json` | Planned |

## Completion map

| Requirement | Owner | Evidence | State |
| --- | --- | --- | --- |
| EXP-001 | p1 child | {evidence} | {state} |
| EXP-002 | unassigned | none | Pending |
"""


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
app = make_repo(
    dest, "billing", packet("invoice-export", REQUIREMENTS, plan("Planned"))
)
p1 = add_worktree(app, "invoice-export", "p1-csv", "plc/invoice-export-p1")
commit(
    p1,
    "feat(export): write invoices as CSV (EXP-001)",
    {
        "src/export.py": EXPORT_CODE,
        "tests/test_export.py": EXPORT_TEST,
    },
)
commit(
    p1,
    "docs(plan): record P1 progress",
    packet("invoice-export", REQUIREMENTS, plan("Implemented")),
)
snapshot(dest, [app])
print(dest)
