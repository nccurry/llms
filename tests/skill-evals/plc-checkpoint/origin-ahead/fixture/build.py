"""P1 was merged on origin, but this checkout's main has not fetched it."""

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
    second_clone,
    snapshot,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| SRCH-001 | Search matches titles case-insensitively. | `test_search_case` passes. |
| SRCH-002 | Search results are paged 20 at a time. | `test_search_pages` passes. |
"""


def plan(p1_state: str, evidence: str) -> str:
    return f"""## Phase Summary

| Phase | Goal | Requirements | Validation | Status |
| --- | --- | --- | --- | --- |
| P1 | Case-insensitive search | SRCH-001 | `test_search_case` | {p1_state} |
| P2 | Paging | SRCH-002 | `test_search_pages` | Planned |

## Completion map

| Requirement | Evidence | State |
| --- | --- | --- |
| SRCH-001 | {evidence} | {p1_state} |
| SRCH-002 | none | Pending |
"""


dest = destination()
app = make_repo(
    dest, "catalog", packet("search", REQUIREMENTS, plan("In progress", "none"))
)
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
    packet(
        "search",
        REQUIREMENTS,
        plan("Merged", f"merge {merge}; `test_search_case` passed in CI on {merge}"),
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
