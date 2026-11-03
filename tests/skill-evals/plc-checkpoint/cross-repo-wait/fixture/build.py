"""The plan says P2 waits on another repo, but that work is already on its origin/main."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import (
    commit,
    current_work,
    destination,
    git,
    make_repo,
    packet,
    second_clone,
    snapshot,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| SCH-001 | Jobs accept a start time. | `test_start_time` passes. |
| SCH-002 | Jobs accept a duration such as `1h30m`. | `test_duration` passes. |

## Dependencies

- SCH-002 needs `parse_duration` from the `timekit` repository (sibling
  folder `../timekit`), tracked there as TK-7.
"""

PLAN = """### P1: Start times

- Requirements: SCH-001
- Check: `test_start_time` passes.

### P2: Durations

- Requirements: SCH-002
- Check: `test_duration` passes.
- Needs: `parse_duration` from timekit (TK-7).
"""

PARSE_TIME = """from datetime import time


def parse_time(text):
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))
"""

PARSE_DURATION = """

def parse_duration(text):
    hours, _, rest = text.partition("h")
    minutes = rest.removesuffix("m") or "0"
    return int(hours or 0) * 60 + int(minutes)
"""

JOBS = """from timekit import parse_time


def schedule(start):
    return {"start": parse_time(start)}
"""

JOBS_TEST = """from datetime import time

from src.jobs import schedule


def test_start_time():
    assert schedule("09:30")["start"] == time(9, 30)
"""

dest = destination()
lib = make_repo(dest, "timekit", {"timekit/__init__.py": PARSE_TIME})
app = make_repo(dest, "scheduler", {"README.md": "# scheduler\n"})
p1 = commit(
    app,
    "feat(jobs): accept a start time (SCH-001)",
    {"src/jobs.py": JOBS, "tests/test_jobs.py": JOBS_TEST},
)
commit(
    app,
    "docs(plan): add durations PLC",
    packet(
        "durations",
        "Durations",
        "Let jobs take a start time and a duration, so a schedule can say when a job ends.",
        current_work(
            last_updated=f"2026-10-25, `main` at `{p1}`",
            next_action="start P2 once timekit TK-7 lands",
            current_state="P1 verified on `main`. P2 waits on timekit TK-7.",
            status="Blocked",
            blocker="P2 needs `parse_duration` from timekit (TK-7); the timekit maintainers own it",
            depends_on="timekit TK-7 (`parse_duration`, sibling folder `../timekit`)",
        ),
        [
            ("P1", "Start times", f"Verified — `test_start_time` passed on `main` @ `{p1}`"),
            ("P2", "Durations", "Blocked — waits on timekit TK-7 (`parse_duration`)"),
        ],
        REQUIREMENTS,
        PLAN,
        log=[
            "2026-10-22 Created.",
            f"2026-10-25 P1 Verified: `test_start_time` passed on `main` @ `{p1}`.",
            "2026-10-25 P2 Blocked on timekit TK-7.",
        ],
    ),
)
git(app, "push", "-q", "origin", "main")

# TK-7 lands on timekit's remote; the local timekit checkout has not fetched it.
other = second_clone(dest, "timekit", "timekit-maintainer")
commit(
    other,
    "feat: add parse_duration (TK-7)",
    {"timekit/__init__.py": PARSE_TIME + PARSE_DURATION},
)
git(other, "push", "-q", "origin", "main")

snapshot(dest, [app, lib])
print(dest)
