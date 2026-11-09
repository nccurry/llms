# PLC-1 Reject invalid berth limits

Reject berth limits below one with a clear argument error while keeping valid
limits unchanged. This invented example is a bounded bug fix.

## Current Work

- Status: Planned
- Owner: @alex
- Last updated: 2026-11-01, `main` at `abc1234`
- Next action: Add a failing argument test for limit zero in `tests/test_harbor.py`
- Blocker: None
- Depends on: None
- Current state: Argument validation is planned; no implementation has started.
- Resume check: `python -m unittest` → existing tests pass

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | Validate berth limits | @alex | Planned |

## Done when

- REQ-001: Zero and negative limits produce an argument error. Check: `python -m unittest` exercises both inputs and asserts exit 2 and a clear error.
- REQ-002: Valid limits retain their result. Check: the same suite asserts that limit two returns the first two berths.

## Log

- 2026-11-01 Created.
