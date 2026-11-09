# Harbor reload implementation

This invented excerpt shows phase detail. Its packet's README owns phase state.

## Phase details

### P1: Replace configuration safely

Validate a candidate before replacing the active configuration. Invalid input
leaves readers on the last complete version. Requirements: REQ-001, REQ-002.

#### Prerequisite

The service owns the active configuration and exposes a reload entrypoint.
Check: the existing command test can start the service and read its version.

#### Steps

1. Add tests for invalid input and concurrent readers.
2. Validate the candidate and publish one complete version.
3. Connect the command and document its success and failure output.

#### Validation

| Check | Expected result |
| --- | --- |
| `python -m unittest tests.test_reload` | Invalid input retains the prior version |
| Command scenario | A successful reload reports the newly active version |

#### Evidence

##### Parser checks — 2026-11-02

REQ-001, source `def5678`, Linux. Method: `python -m unittest tests.test_reload`.
Expected: rejected input retains the prior version. Actual: 15 tests passed.
Limit: command behavior has not been checked, so REQ-002 remains pending.

#### Rollback

Revert reload wiring and restore startup-only loading. Do not rewrite the
operator's configuration file to restore process state.
