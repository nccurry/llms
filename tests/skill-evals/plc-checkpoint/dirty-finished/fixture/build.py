"""P1 is merged into main, but its worktree still holds untracked notes."""

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
    write,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| FLT-001 | Messages can be filtered by sender. | `test_sender_filter` passes. |
| FLT-002 | Filters can be combined with AND. | `test_and_filter` passes. |
"""

P1_DETAILS = "- Requirements: FLT-001\n- Check: `test_sender_filter` passes."
P2_DETAILS = "- Requirements: FLT-002\n- Check: `test_and_filter` passes."

dest = destination()
app = make_repo(dest, "inbox", {"README.md": "# inbox\n"})
start = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): add filters PLC",
    packet(
        "filters",
        "Filters",
        "Let people filter their inbox by sender, and combine filters.",
        current_work(
            last_updated=f"2026-10-25, `main` at `{start}`",
            next_action="finish P1",
            current_state="P1 in progress in its worktree. P2 not started.",
            checkouts=[("inbox-wt/filters/p1-sender", "plc/filters-p1", "p1 child", "in progress")],
        ),
        [
            ("P1", "Sender filter", "In progress", P1_DETAILS),
            ("P2", "Combined filters", "Planned", P2_DETAILS),
        ],
        REQUIREMENTS,
        log=["2026-10-25 Created."],
    ),
)
git(app, "push", "-q", "origin", "main")
p1 = add_worktree(app, "filters", "p1-sender", "plc/filters-p1")
commit(
    p1,
    "feat(filters): filter by sender (FLT-001)",
    {
        "src/filters.py": (
            "def by_sender(messages, sender):\n"
            "    return [m for m in messages if m['from'] == sender]\n"
        ),
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
