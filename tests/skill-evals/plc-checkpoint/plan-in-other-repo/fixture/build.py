"""The plan for the api repo lives in a separate plans repo; its Current Work is stale."""

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
| SYN-001 | `GET /sync` returns changes since a cursor. | `test_sync_since` passes. |
| SYN-002 | The cursor expires after 24 hours. | `test_cursor_expiry` passes. |
"""

P1_DETAILS = "- Requirements: SYN-001\n- Check: `test_sync_since` passes."
P2_DETAILS = "- Requirements: SYN-002\n- Check: `test_cursor_expiry` passes."

AGENTS = """# api

## Plans

Plans for this repository live in the `plans` repository (sibling folder
`../plans`), under `docs/plans/<slug>/`. Commit plan updates there, on its
`main`. Do not push the plans repository; the owner pushes it.
"""

dest = destination()
api = make_repo(
    dest,
    "api",
    {"AGENTS.md": AGENTS, "src/app.py": "ROUTES = {}\n"},
)
plans = make_repo(dest, "plans", {"README.md": "# plans\n"})
api_start = git(api, "rev-parse", "--short", "HEAD")
commit(
    plans,
    "docs(plan): add sync-api PLC",
    packet(
        "sync-api",
        "Sync API",
        "Let clients fetch only the changes since their last sync,"
        " with a cursor that expires.",
        current_work(
            last_updated=f"2026-10-24, api `main` at `{api_start}`",
            next_action="start P1 in an api worktree",
            current_state="Nothing started.",
            status="Planned",
        ),
        [
            ("P1", "Sync endpoint", "Planned", P1_DETAILS),
            ("P2", "Cursor expiry", "Planned", P2_DETAILS),
        ],
        REQUIREMENTS,
        log=["2026-10-24 Created."],
    ),
)
git(plans, "push", "-q", "origin", "main")

p1 = add_worktree(api, "sync-api", "p1-endpoint", "plc/sync-api-p1")
commit(
    p1,
    "feat(sync): return changes since a cursor (SYN-001)",
    {
        "src/sync.py": (
            "def since(changes, cursor):\n"
            "    return [c for c in changes if c['seq'] > cursor]\n"
        ),
        "tests/test_sync.py": (
            "from src.sync import since\n\n\n"
            "def test_sync_since():\n"
            "    changes = [{'seq': 1}, {'seq': 2}]\n"
            "    assert since(changes, 1) == [{'seq': 2}]\n"
        ),
    },
)

snapshot(dest, [api, plans])
expect(dest)
print(dest)
