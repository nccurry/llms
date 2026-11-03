"""A finished PLC with one idle worktree; the user asks to wrap it up, not for status."""

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
| LOG-001 | Log lines include a request ID. | `test_request_id` passes. |
"""

PLAN = """### P1: Request IDs in logs

- Requirements: LOG-001
- Check: `test_request_id` passes.
"""

SUMMARY = "Put the request ID on every gateway log line, so one request can be traced end to end."


def request_ids_packet(status: str, p1_state: str, log: list[str]) -> dict[str, str]:
    return packet(
        "request-ids",
        "Request IDs",
        SUMMARY,
        status,
        [("P1", "Request IDs in logs", p1_state)],
        REQUIREMENTS,
        PLAN,
        log=log,
    )


dest = destination()
app = make_repo(dest, "gateway", {"README.md": "# gateway\n"})
start = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): add request IDs PLC",
    request_ids_packet(
        current_work(
            last_updated=f"2026-10-24, `main` at `{start}`",
            next_action="start P1 in a worktree",
            current_state="Nothing started.",
            status="Planned",
        ),
        "Planned",
        ["2026-10-24 Created."],
    ),
)
p1 = add_worktree(app, "request-ids", "p1-logs", "plc/request-ids-p1")
commit(
    p1,
    "feat(logs): add request IDs (LOG-001)",
    {
        "src/logging.py": "def line(request_id, text):\n    return f'{request_id} {text}'\n",
        "tests/test_logging.py": (
            "from src.logging import line\n\n\n"
            "def test_request_id():\n"
            '    assert line("req-7", "started") == "req-7 started"\n'
        ),
    },
)
git(app, "merge", "-q", "--no-ff", "plc/request-ids-p1", "-m", "Merge P1 request IDs")
merge = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): P1 merged",
    request_ids_packet(
        current_work(
            last_updated=f"2026-10-26, `main` at `{merge}`",
            next_action="wrap up the PLC",
            current_state=f"P1 merged into `main` at `{merge}`.",
            checkouts=[("gateway-wt/request-ids/p1-logs", "plc/request-ids-p1", "p1 child", "idle")],
        ),
        f"Merged — `{merge}`",
        ["2026-10-24 Created.", f"2026-10-26 P1 Merged @ `{merge}`."],
    ),
)
snapshot(dest, [app])
print(dest)
