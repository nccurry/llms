"""Two scope calls made in chat never reached the packet."""

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
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| SHOP-001 | Each shop row shows the item name, cost, and rarity. | `test_shop_row` checks all three fields. |
| SHOP-002 | Players can filter the shop by rarity. | `test_shop_filter` passes. |
"""


def plan(state: str, evidence: str) -> str:
    return f"""## Phase Summary

| Phase | Goal | Requirements | Validation | Status |
| --- | --- | --- | --- | --- |
| P1 | Shop rows and filter | SHOP-001, SHOP-002 | `test_shop_row`, `test_shop_filter` | {state} |

## Decisions

| Decision | Status | Reason |
| --- | --- | --- |
| Rarity uses the existing color palette | accepted | Matches inventory screen |

## Completion map

| Requirement | Evidence | State |
| --- | --- | --- |
| SHOP-001 | {evidence} | {state} |
| SHOP-002 | none | Pending |
"""


dest = destination()
app = make_repo(dest, "tavern", packet("shop", REQUIREMENTS, plan("Planned", "none")))
p1 = add_worktree(app, "shop", "p1-rows", "plc/shop-p1")
commit(
    p1,
    "feat(shop): show name and rarity on shop rows (SHOP-001)",
    {
        "src/shop_row.py": (
            "def render(item):\n"
            "    # Cost is shown in the purchase dialog instead of the row.\n"
            "    return f'{item.name}  [{item.rarity}]'\n"
        ),
        "tests/test_shop.py": (
            "from types import SimpleNamespace\n\n"
            "from src.shop_row import render\n\n\n"
            "def test_shop_row():\n"
            '    item = SimpleNamespace(name="Sword", cost=10, rarity="rare")\n'
            '    assert render(item) == "Sword  [rare]"\n'
        ),
    },
)
git(app, "merge", "-q", "--no-ff", "plc/shop-p1", "-m", "Merge P1 shop rows")
merge = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): record SHOP-001",
    packet(
        "shop",
        REQUIREMENTS,
        plan("In progress", f"merge {merge}; `test_shop_row` passed"),
    ),
)
git(app, "push", "-q", "origin", "main")
git(app, "worktree", "remove", str(p1))
p1.parent.rmdir()
p1.parent.parent.rmdir()
snapshot(dest, [app])
# P1 is merged and its worktree is gone; its leftover local branch is finished.
expect(dest, deleted_branches={"tavern": ["plc/shop-p1"]})
print(dest)
