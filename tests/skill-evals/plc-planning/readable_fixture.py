"""Invented inputs for the readable-plan evaluations; no agent runs here."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture_lib import destination, make_repo, snapshot

BRIEF = """# Harbor reload

Add configuration reloads to the harbor service. Invalid input must leave the
active configuration unchanged. Valid input replaces it atomically. The command
prints whether the reload succeeded. Concurrent readers see one complete version.
Keep the current startup configuration format. Compare validating in memory with
writing a temporary file. The process owns configuration; disk remains operator
input. Tests use invented berth names. Changes need unit and command checks.
Do not implement the feature. Owner: @alex.
"""

README = """# PLC-1 Harbor reload

Reload harbor configuration without losing the last valid version.

## Current Work

- Status: In progress
- Owner: @alex
- Last updated: 2026-11-01, `main`
- Next action: Record the supplied reload test results
- Blocker: Browser acceptance has not run
- Depends on: None
- Current state: Parser checks passed; browser acceptance is pending.
- Resume check: `python -m unittest` → passes

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | Reload safely | @alex | In progress |

## Done when

- REQ-001: Invalid input preserves active configuration.
  Check: parser tests → prior version retained.
- REQ-002: Reload outcome is visible. Check: browser inspection → success or failure visible.

## Log

- 2026-11-01 Created.
"""

PLAN = """# Reload implementation

## Phase details

### P1: Reload safely

Keep readers on a complete configuration while reload validates new input.

#### Steps

1. Validate before replacing active configuration.
2. Show the reload outcome.

#### Evidence

##### Parser checks

REQ-001: `python -m unittest`, expected prior configuration retained;
actual: 12 tests passed on Linux at source abc1234 on 2026-11-01.
Limit: browser behavior was not checked. REQ-002 remains pending.
"""

RECEIPTS = """# Results to record

These are supplied fixture facts, not commands to execute again.
On 2026-11-02, source def5678, Linux: parser checks via `python -m unittest`
expected rejection to preserve the prior configuration; actual: 15 tests passed.
On 2026-11-02, source def5678, Linux: command check via `python harbor.py reload bad.yaml`
expected exit 2 and the old configuration; actual: exit 2, old configuration retained.
Browser inspection has NOT run. REQ-002 remains pending. Do not mark P1 Verified
or the packet Complete. Keep the existing abc1234 result and its browser limit.
"""


def build(case: str) -> None:
    dest = destination()
    files = {
        "README.md": "# Harbor\n\nConfiguration is loaded once at startup.\n",
        "harbor.py": "def active_config():\n    return {'berth': 'Fern'}\n",
        "docs/plans/README.md": "# Plans\n\nUse planned/, in-progress/ and completed/.\n",
        "brief.md": BRIEF,
    }
    if case == "growing-evidence":
        files.update(
            {
                "docs/plans/in-progress/reload/README.md": README,
                "docs/plans/in-progress/reload/IMPLEMENTATION_PLAN.md": PLAN,
                "receipts.md": RECEIPTS,
            }
        )
    app = make_repo(dest, "harbor", files)
    snapshot(dest, [app])
    print(dest)


if __name__ == "__main__":
    case_name = sys.argv.pop(1)
    build(case_name)
