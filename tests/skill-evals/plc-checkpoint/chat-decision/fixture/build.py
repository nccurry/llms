"""Two scope calls made in chat never reached the packet, and the merged code
no longer meets SHOP-001 as written."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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
| SHOP-001 | Each shop row shows the item name, cost, and rarity. | `test_shop_row` checks all three fields. |
| SHOP-002 | Players can filter the shop by rarity. | `test_shop_filter` passes. |
"""

PLAN = """### P1: Shop rows and filter

- Requirements: SHOP-001, SHOP-002
- Checks: `test_shop_row`, `test_shop_filter`
"""

DECISION = "2026-10-21 Decision: rarity uses the existing color palette, to match the inventory screen."


def shop_packet(status: str, p1_state: str, log: list[str]) -> dict[str, str]:
    return packet(
        "shop",
        "Shop",
        "Add a shop screen where players see what is for sale and filter it by rarity.",
        status,
        [("P1", "Shop rows and filter", p1_state)],
        REQUIREMENTS,
        PLAN,
        log=log,
    )


dest = destination()
app = make_repo(dest, "tavern", {"README.md": "# tavern\n"})
start = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): add shop PLC",
    shop_packet(
        current_work(
            last_updated=f"2026-10-21, `main` at `{start}`",
            next_action="start P1 in a worktree",
            current_state="Nothing started.",
            status="Planned",
        ),
        "Planned",
        ["2026-10-20 Created.", DECISION],
    ),
)
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
    shop_packet(
        current_work(
            last_updated=f"2026-10-27, `main` at `{merge}`",
            next_action="add the rarity filter (SHOP-002)",
            current_state=f"Shop rows merged into `main` at `{merge}`. The rarity filter is not started.",
        ),
        f"In progress — shop rows merged @ `{merge}`; `test_shop_row` passed",
        ["2026-10-20 Created.", DECISION, f"2026-10-27 P1 shop rows merged @ `{merge}`."],
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
