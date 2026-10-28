"""A finished PLC with one idle worktree; the user asks to wrap it up, not for status."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import (
    add_worktree,
    commit,
    destination,
    git,
    make_repo,
    packet,
    snapshot,
)

REQUIREMENTS = """| ID | Requirement | Acceptance |
| --- | --- | --- |
| LOG-001 | Log lines include a request ID. | `test_request_id` passes. |
"""

PLAN = """## Phase Summary

| Phase | Goal | Requirements | Validation | Status |
| --- | --- | --- | --- | --- |
| P1 | Request IDs in logs | LOG-001 | `test_request_id` | {state} |
"""

dest = destination()
app = make_repo(
    dest, "gateway", packet("request-ids", REQUIREMENTS, PLAN.format(state="Planned"))
)
p1 = add_worktree(app, "request-ids", "p1-logs", "plc/request-ids-p1")
commit(
    p1,
    "feat(logs): add request IDs (LOG-001)",
    {
        "src/logging.py": "def line(request_id, text):\n    return f'{request_id} {text}'\n",
        "tests/test_logging.py": (
            "from src.logging import line\n\n\n"
            "def test_request_id():\n"
            '    assert line("req-7", "started") == "req-7 started"\n'
        ),
    },
)
git(app, "merge", "-q", "--no-ff", "plc/request-ids-p1", "-m", "Merge P1 request IDs")
commit(
    app,
    "docs(plan): P1 merged",
    packet(
        "request-ids",
        REQUIREMENTS,
        PLAN.format(state="Merged; `test_request_id` passed"),
    ),
)
snapshot(dest, [app])
print(dest)
