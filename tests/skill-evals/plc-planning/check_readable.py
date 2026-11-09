"""Check readable-plan eval scope and evidence preservation; prose needs grading."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture_lib import git, packet_shape_problems


def check(dest: Path) -> dict:
    app = dest / "harbor"
    snap = json.loads((dest / "_snapshot.json").read_text())
    start = snap["checkouts"]["harbor"]["worktrees"]["harbor"]["head"]
    problems = []
    changed = git(app, "diff", start, "--name-only").splitlines()
    changed += git(app, "ls-files", "--others", "--exclude-standard").splitlines()
    if any(not path.startswith("docs/plans/") for path in changed):
        problems.append("changed files outside docs/plans")
    packets = [
        path
        for path in (app / "docs/plans").rglob("*.md")
        if path.name == "README.md" and path.parent.name != "plans"
    ]
    packets += list((app / "docs/plans/planned").glob("plc-*.md"))
    if len(packets) != 1:
        problems.append(f"expected one packet, found {len(packets)}")
    else:
        problems += packet_shape_problems(packets[0], owner="@alex")
        if (app / "receipts.md").exists():
            text = "\n".join(p.read_text() for p in packets[0].parent.glob("*.md"))
            for fact in (
                "abc1234",
                "def5678",
                "12",
                "15",
                "2026-11-01",
                "2026-11-02",
                "Linux",
                "REQ-001",
                "REQ-002",
                "python -m unittest",
            ):
                if fact not in text:
                    problems.append(f"missing evidence fact: {fact}")
            if "browser" not in text.lower():
                problems.append("missing browser limitation")
            evidence = re.sub(r"(?m)^- Next action:.*$", "", text).lower()
            if not any(marker in evidence for marker in ("supplied", "receipts.md")):
                problems.append("missing supplied-result attribution")
            if "- Status: Complete" in text:
                problems.append("completed with unrun acceptance")
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    report = check(Path(sys.argv[1]))
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)
