"""The plan says P2 waits on another repo, but that work is already on its origin/main."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import (
    commit,
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

PLAN = """## Phase Summary

| Phase | Goal | Requirements | Validation | Status |
| --- | --- | --- | --- | --- |
| P1 | Start times | SCH-001 | `test_start_time` | Merged |
| P2 | Durations | SCH-002 | `test_duration` | Blocked: waiting on timekit TK-7 |

## Completion map

| Requirement | Evidence | State |
| --- | --- | --- |
| SCH-001 | `test_start_time` passed on main | Verified |
| SCH-002 | none | Blocked on timekit `parse_duration` (TK-7) |
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
app = make_repo(dest, "scheduler", packet("durations", REQUIREMENTS, PLAN))
commit(
    app,
    "feat(jobs): accept a start time (SCH-001)",
    {"src/jobs.py": JOBS, "tests/test_jobs.py": JOBS_TEST},
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
