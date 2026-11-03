# Harbor retry cap

Stop retries after three attempts so a failing upstream cannot pile up work.

## Current Work

- Status: Planned
- Owner: @alex
- Last updated: 2026-11-03, `main` at `abc1234`
- Next action: Write the failing test.
- Blocker: None
- Depends on: None
- Current state: Planned.
- Resume check: `task test` → 0 failures

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | Cap retries | @alex | Planned |
| P0 | Old idea | | Dropped — superseded by P1 |

## Done when

- REQ-001: A fourth retry never starts. Check: `task test -- retry` → passes

## Open questions

- Open question: Should the cap be configurable? (waits on @sam)

## Log

- 2026-11-03 Created.
