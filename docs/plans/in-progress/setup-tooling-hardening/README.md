# Setup tooling: lint, Windows checks, and host and tool structure

Give the Python outside `piw/` its own lint, format and type checks, check the
Windows setup path as far as a Linux host can, and restructure
`scripts/manage_agent_tools.py` so each agent host and each tool is described
in one place.

## Current Work

- Status: In progress
- Owner: @nccurry
- Last updated: 2026-11-06, `main` at `beb4a06` (P1 to P4 merged)
- Selected work: P1 to P5 — REQ-001 to REQ-020 and REQ-022; delivered by direct merges into `main`, each phase closing when its requirements' checks pass on `main`.
- Next action: Run the REQ-020 preview comparison from `main`, then reconfigure this machine and run `doctor`.
- Blocker: None
- Depends on: None
- Current state: P1 to P4 Verified on `main`; P5 merged, its REQ-020 check and the final reconfigure pending.
- Resume check: `./bootstrap.sh deps:dev-tools && ./bootstrap.sh lint:python` → 0 errors; `./bootstrap.sh test` → piw 185 passed, setup-script tests 143 OK, launcher tests 6 pass.

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| [P1](IMPLEMENTATION_PLAN.md#p1-separate-lint-and-type-checks-for-python-outside-piw) | Separate lint and type checks for Python outside piw | | Verified — lint:python 0 findings, test and check pass @ 1ea0b4b; merged by fast-forward |
| [P2](IMPLEMENTATION_PLAN.md#p2-windows-checks-from-linux) | Windows checks from Linux | | Verified — check (lint:shell, lint:powershell, 23 Pester tests, repo tests) and test:tooling 70 OK on the merged source @ fecb474 |
| [P3](IMPLEMENTATION_PLAN.md#p3-end-to-end-configure-test) | End-to-end configure test | | Verified — test:tooling 48 OK with pinned tools required, fresh-clone run OK @ d0c60a9; merged by fast-forward |
| [P4](IMPLEMENTATION_PLAN.md#p4-host-adapters-and-a-split-configure) | Host adapters and a split configure | | Verified — check and test:tooling 83 OK, old-vs-new harness 15/15 same; REQ-020 preview from `main` identical to the pre-P4 baseline @ beb4a06 |
| [P5](IMPLEMENTATION_PLAN.md#p5-tools-described-by-the-manifest) | Tools described by the manifest | | Merged — REQ-016, REQ-018, REQ-019, REQ-022 pass (test:tooling 143 OK, lint:python with C901 and strict, check, harnesses same) @ 4104078; REQ-020 preview from `main` and the final reconfigure still to run |

## Done when

The requirements and their checks are in [SRD.md](SRD.md).

## Log

- 2026-11-06 Created from the setup-tooling audit follow-ups; baseline measured at `284290e`.
- 2026-11-06 Independent review: moved pyright's config into `lint/` (a root file overrode piw's), enforced hashes through `uv pip install --require-hashes`, kept development-only tools out of `mise.toml`, limited C901 to `manage_agent_tools.py`, and made the golden test and grep checks reliable.
- 2026-11-06 Decision: P2 fixes the two Windows defects (REQ-009 CRLF part, REQ-012); shellcheck stays (REQ-007); hosted Windows CI not now; pyright strict for the setup script added as REQ-022 in P5 ([SADD](SADD.md#decisions-and-alternatives)).
- 2026-11-06 Decision: removed the commit-scan requirement (formerly REQ-021) at the owner's request.
- 2026-11-06 Started execution: Opus parent, Sonnet implementation children, direct merges into `main`.
- 2026-11-06 P1 merged by fast-forward and verified: strict audit (six domains) PASS after one repair batch; decisions on targets, Node for pyright and test ignores recorded in [SADD](SADD.md#decisions-and-alternatives).
- 2026-11-06 P3 merged by fast-forward and verified: strict audit (correctness, test quality, plan alignment, code quality) PASS after one repair batch, which committed a golden file `.gitignore` had hidden, added host scenarios (FIX-010) and made `check` and `ci` really require the pinned tools.
- 2026-11-06 P2 merged and verified: strict audit PASS after two passes; the second replaced reshim-after-install with a rule that a checkout sharing another's mise data never installs into it, and kept `task.cmd` files that differ only in line endings ([SADD](SADD.md#decisions-and-alternatives)).
- 2026-11-06 P4 merged: strict audit PASS after one repair batch; P2's quoting helper folded into the adapter-based hook helpers during integration. REQ-017's check is scoped to `manage_agent_tools.py`, and REQ-020 is checked from `main` after merge.
- 2026-11-06 P4 verified: the preview from `main` after the merge is identical to the baseline saved before P4.
- 2026-11-06 P5 merged: strict audit PASS after two passes (security re-audit of the `TOOL` quoting and manifest validation); installers became records of functions and tool entries a typed record ([SADD](SADD.md#decisions-and-alternatives)).
