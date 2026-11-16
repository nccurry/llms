"""Invented linked MRs for exact existing-label reuse on both hosts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture_lib import snapshot
from host_fixture import BRANCH, build_app, install_host

PLAN = "docs/plans/planned/plc-harbor.md"
TEXT = """# PLC-100 Harbor

Read metadata and filter plans.

## Current Work

- Status: Planned
- Owner: @alex
- Last updated: 2026-11-16
- Tags: release: 1.0.0; kind: feature

## Phases

| Phase | Name | Owner | State | Tags |
| --- | --- | --- | --- | --- |
| P1 | Read metadata | @alex | Planned | area: reader |
| P2 | Filter plans | @sam | Planned | area: web |
| P3 | Later polish | @sam | Planned | release: 1.1.0; area: web |

## Merge requests

| Phase | Merge request | State | Note |
| --- | --- | --- | --- |
| P1 | #21 | Open | |
| P2 | #22 | Open | |
| P2 | #23 | Open | Also P3 |
| P3 | #23 | Open | Also P2 |
| P2 | #24 | Open | |

## Log

- 2026-11-16 Created.
"""


def build(dest: Path, host: str, scoped: bool = False) -> None:
    """MR21 misses area; MR22 conflicts; MR23 spans phases; MR24 denies writes."""
    dest.mkdir(parents=True, exist_ok=True)
    build_app(dest, {PLAN: TEXT, "AGENTS.md": "Reuse existing plan-tag labels; create none.\n"})
    labels = ["release::1.0.0", "release::0.9.0", "kind::feature", "area::web", "keep"]
    mrs = []
    for number in range(21, 26):
        phases = {21: " P2", 22: " P2", 23: " P2 P3", 24: " P2", 25: ""}[number]
        mrs.append(
            {
                "number": number,
                "title": "Harbor work",
                "body": f"Plan: PLC-100{phases}",
                "source": BRANCH,
                "target": "main",
                "state": "opened",
                "auto_merge": False,
                "discussions": [],
                "labels": ["keep"] + (["release::0.9.0"] if number == 22 else []),
            }
        )
    # MR21's phase uses area reader, whose label is absent. Other MRs use P2.
    mrs[0]["body"] = "Plan: PLC-100 P1"
    install_host(
        dest,
        host,
        ("gh", "glab"),
        {
            "mrs": mrs,
            "labels": labels,
            "scoped_labels": scoped,
            "deny_label_writes": [24],
            "next_mr": 26,
        },
    )
    expected = {
        "21": ["keep", "release::1.0.0", "kind::feature"],
        "22": ["keep", "release::0.9.0", "kind::feature", "area::web"],
        "23": ["keep", "kind::feature", "area::web"],
        "24": ["keep"],
        "25": ["keep", "release::1.0.0", "kind::feature"],
    }
    (dest / "_tag_expect.json").write_text(json.dumps(expected), encoding="utf-8")
    snapshot(dest, [dest / "app"])
