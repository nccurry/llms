"""P1 is merged into main, but its worktree still holds untracked notes."""

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
    write,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| FLT-001 | Messages can be filtered by sender. | `test_sender_filter` passes. |
| FLT-002 | Filters can be combined with AND. | `test_and_filter` passes. |
"""

PLAN = """## Phase Summary

| Phase | Goal | Requirements | Validation |
| --- | --- | --- | --- |
| P1 | Sender filter | FLT-001 | `test_sender_filter` |
| P2 | Combined filters | FLT-002 | `test_and_filter` |
"""

dest = destination()
app = make_repo(dest, "inbox", {"README.md": "# inbox\n"})
start = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): add filters PLC",
    packet(
        "filters",
        REQUIREMENTS,
        PLAN,
        status=current_work(
            last_updated=f"2026-10-25, `main` at `{start}`",
            rows=[
                ("P1 (FLT-001)", "in progress", "p1 child", "none yet"),
                ("P2 (FLT-002)", "planned", "unassigned", "none"),
            ],
            checkouts=[("inbox-wt/filters/p1-sender", "plc/filters-p1", "in progress")],
            next_action="finish P1",
        ),
    ),
)
git(app, "push", "-q", "origin", "main")
p1 = add_worktree(app, "filters", "p1-sender", "plc/filters-p1")
commit(
    p1,
    "feat(filters): filter by sender (FLT-001)",
    {
        "src/filters.py": "def by_sender(messages, sender):\n    return [m for m in messages if m['from'] == sender]\n",
        "tests/test_filters.py": (
            "from src.filters import by_sender\n\n\n"
            "def test_sender_filter():\n"
            "    msgs = [{'from': 'a'}, {'from': 'b'}]\n"
            "    assert by_sender(msgs, 'a') == [{'from': 'a'}]\n"
        ),
    },
)
git(app, "merge", "-q", "--no-ff", "plc/filters-p1", "-m", "Merge P1 sender filter")
git(app, "push", "-q", "origin", "main")
# The child left notes that exist nowhere else.
write(
    p1,
    {
        "NOTES.md": (
            "# P1 notes\n\n"
            "- P2: an empty filter list must return every message, not none.\n"
            "  Product confirmed this in review.\n"
        )
    },
)
snapshot(dest, [app])
expect(dest)
print(dest)
