"""P1 was merged on origin, but this checkout's main has not fetched it."""

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
    second_clone,
    snapshot,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| SRCH-001 | Search matches titles case-insensitively. | `test_search_case` passes. |
| SRCH-002 | Search results are paged 20 at a time. | `test_search_pages` passes. |
"""

P1_DETAILS = "- Requirements: SRCH-001\n- Check: `test_search_case` passes."
P2_DETAILS = "- Requirements: SRCH-002\n- Check: `test_search_pages` passes."

SUMMARY = "Make catalog search forgiving about case, and page long result lists."


def search_packet(current_work_block: str, p1_state: str, log: list[str]) -> dict[str, str]:
    return packet(
        "search",
        "Search",
        SUMMARY,
        current_work_block,
        [
            ("P1", "Case-insensitive search", p1_state, P1_DETAILS),
            ("P2", "Paging", "Planned", P2_DETAILS),
        ],
        REQUIREMENTS,
        log=log,
    )


dest = destination()
app = make_repo(dest, "catalog", {"README.md": "# catalog\n"})
start = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): add search PLC",
    search_packet(
        current_work(
            last_updated=f"2026-10-24, `main` at `{start}`",
            next_action="finish P1 and merge it into `main`",
            current_state="P1 in progress in its worktree. P2 not started.",
            checkouts=[("catalog-wt/search/p1-case", "plc/search-p1", "p1 child", "in progress")],
        ),
        "In progress",
        ["2026-10-24 Created."],
    ),
)
git(app, "push", "-q", "origin", "main")
p1 = add_worktree(app, "search", "p1-case", "plc/search-p1")
commit(
    p1,
    "feat(search): match titles case-insensitively (SRCH-001)",
    {
        "src/search.py": "def matches(title, query):\n    return query.lower() in title.lower()\n",
        "tests/test_search.py": (
            "from src.search import matches\n\n\n"
            "def test_search_case():\n"
            '    assert matches("Hello World", "hello")\n'
            '    assert not matches("Hello World", "bye")\n'
        ),
    },
)
git(p1, "push", "-q", "origin", "plc/search-p1")

# Someone else merges P1 on the remote and records it in the packet.
other = second_clone(dest, "catalog", "reviewer")
git(
    other, "merge", "-q", "--no-ff", "origin/plc/search-p1", "-m", "Merge P1 (SRCH-001)"
)
merge = git(other, "rev-parse", "--short", "HEAD")
commit(
    other,
    "docs(plan): P1 merged",
    search_packet(
        current_work(
            last_updated=f"2026-10-26, `main` at `{merge}`",
            next_action="start P2",
            current_state=f"P1 merged into `main` at `{merge}`. P2 not started.",
        ),
        f"Merged — `{merge}`",
        ["2026-10-24 Created.", f"2026-10-26 P1 Merged @ `{merge}`."],
    ),
)
git(other, "push", "-q", "origin", "main")

snapshot(dest, [app])
# P1 is merged on origin/main, so its worktree and branches are finished.
expect(
    dest,
    removed_worktrees=["catalog-wt/search/p1-case"],
    deleted_branches={"catalog": ["plc/search-p1"]},
    deleted_remote_branches={"catalog.git": ["plc/search-p1"]},
)
print(dest)
