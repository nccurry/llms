"""Grade label reuse independently of GitLab scoped-label enforcement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture_lib import git, status_paths
from host_fixture import host_calls, host_state


def problems(dest: Path) -> list[str]:
    state = host_state(dest)
    expected = json.loads((dest / "_tag_expect.json").read_text(encoding="utf-8"))
    found = []
    for mr in state["mrs"]:
        wanted = expected[str(mr["number"])]
        if sorted(mr.get("labels", [])) != sorted(wanted):
            found.append(f"MR {mr['number']} labels differ: expected {wanted}")
        if mr["body"].strip().startswith("Plan:") and len(mr["body"].splitlines()) == 1:
            found.append(f"MR {mr['number']} description was not updated")
        if mr["state"] != "opened" or mr["auto_merge"]:
            found.append(f"MR {mr['number']} was merged or set to merge")
    available = [
        "release::1.0.0",
        "release::0.9.0",
        "kind::feature",
        "area::web",
        "keep",
        "plc::PLC-100",
        "plc::PLC-999",
        "phase::9",
    ]
    if state["labels"] != available:
        found.append("repository labels changed")
    phases = {21: " P1", 22: " P2", 23: " P2 P3", 24: " P2", 25: ""}
    found.extend(
        f"MR {mr['number']} lost its Plan line"
        for mr in state["mrs"]
        if f"Plan: PLC-100{phases[mr['number']]}" not in mr["body"].splitlines()
    )
    snap = json.loads((dest / "_snapshot.json").read_text(encoding="utf-8"))
    start = snap["checkouts"]["app"]["worktrees"]["app"]["head"]
    app = dest / "app"
    if git(app, "diff", "--name-only", start) or status_paths(app):
        found.append("plan or repository files changed")
    found.extend(
        "attempted to create or remove a label"
        for call in host_calls(dest)
        if call[1:3] in (["label", "create"], ["label", "delete"])
    )
    return found


def main() -> int:
    found = problems(Path(sys.argv[1]).resolve())
    print(json.dumps({"ok": not found, "failures": found}, indent=2))
    return int(bool(found))


if __name__ == "__main__":
    sys.exit(main())
