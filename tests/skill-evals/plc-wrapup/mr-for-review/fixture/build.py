"""The `app` repository with an in-progress plan whose only phase, P1, is
done on the pushed `retry-backoff` branch, a worktree for it, and a fake
GitLab host with no merge request yet. The repository delivers through
merge requests, so wrapping up opens one and leaves it for review."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import OWNER, current_work, destination, git, packet  # noqa: E402
from host_fixture import BRANCH, build_app, install_host  # noqa: E402

PLAN = "docs/plans/in-progress/retry-backoff"
WORKTREE = "app-wt/retry-backoff/p1"
# The number the fake host gives the first merge request it opens.
FIRST_MR = 3

AGENTS = f"""# app

## Delivery

Every change reaches `main` through a GitLab merge request, opened with
`glab`. Open one per branch, targeting `main`, and leave it for review
unless the user asks to merge it. Never push to `main` directly. Plan
updates travel in the merge request with the code.

## Checks

From the repository root:

```sh
"{sys.executable}" run_tests.py
```

CI runs the same tests on every merge request.

## Worktrees

Root: `../app-wt/<campaign>/<checkout>`.

## Plans

The retry backoff plan is [{PLAN}/README.md]({PLAN}/README.md).
"""

REQUIREMENTS = """| ID | Priority | Requirement | Check |
| --- | --- | --- | --- |
| RB-001 | Must | `backoff_delay(attempt)` doubles with each attempt, starting at `base` seconds. | `test_delay_doubles` passes. |
| RB-002 | Must | `backoff_delay` never returns more than `max_delay` seconds. | `test_delay_is_capped` passes. |
"""

dest = destination()
plan = packet(
    PLAN.removeprefix("docs/plans/"),
    "PLC-004 Retry backoff",
    "A `backoff_delay` helper that gives the wait before each retry: doubling, up to a cap. Calling it from `call_with_retry` is a later plan.",
    current_work(
        last_updated="2026-11-04, `retry-backoff` at its first commit",
        next_action="open the merge request for P1",
        current_state="P1 is done on `retry-backoff` and pushed; no merge request yet.",
        checkouts=[(WORKTREE, BRANCH, "p1 child", "in progress")],
        resume_check="`python run_tests.py` → every test passes",
    ),
    [
        (
            "P1",
            "Backoff delay",
            "In progress",
            "- Requirements: RB-001, RB-002\n- Check: `python run_tests.py` passes.",
        )
    ],
    REQUIREMENTS,
    log=["2026-11-04 Created."],
)
app = build_app(dest, {"AGENTS.md": AGENTS, **plan})
git(app, "worktree", "add", "-q", str(dest / WORKTREE), BRANCH)
install_host(dest, "gitlab", ("glab",), {"next_mr": FIRST_MR})
(dest / "_expect.json").write_text(
    json.dumps(
        {
            "branch": BRANCH,
            "target": "main",
            "main": git(app, "rev-parse", "origin/main"),
            "branch_start": git(app, "rev-parse", f"origin/{BRANCH}"),
            "plan": PLAN,
            "plan_names": ["PLC-004", "retry-backoff"],
            "phase": "P1",
            "phase_states": ["Implemented"],
            "statuses": ["In progress"],
            "owner": OWNER,
            "removed_worktrees": [WORKTREE],
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(dest)
