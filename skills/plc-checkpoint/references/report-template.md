# plc-checkpoint report template

Use these sections in this order. Write "None" for an empty section. Tables
show the shape; use prose when a table would hold one row.

```markdown
## <Plan name>: <one-sentence headline>

<Counts by state, e.g. "3 of 5 requirements merged, 1 verified, 1 not started.">
Since the last update (<Last updated date and commit>): <what changed, or "nothing">.
Next step: <one concrete action and where it happens>.

### Where we are
Current phase, the work happening now, and who or which session owns it.

### Done
| Requirement / phase | State | Evidence |
| --- | --- | --- |
| EXP-001 / P1 | merged | PR #12, merge a1b2c3d; `test_export_csv` passed in CI on a1b2c3d |

### In progress
| Checkout | Branch | Ahead / behind target | Uncommitted | Lock | PR | Owner |
| --- | --- | --- | --- | --- | --- | --- |

### Left
**Can start now:** ordered list, each with its requirement IDs.
**Waiting on:** each item with what it waits for and how you checked that.

### Scope added since the plan started
Requirements or phases added after execution began (with the commit), branch
work that maps to no requirement, and proposals not yet approved.

### Decisions since the work started
| Decision | When / where | In plan |
| --- | --- | --- |
| <decision> | <commit, or "this conversation"> | recorded / added now as accepted / added now as proposed / not added (report only) |

### Open questions and blockers
Questions that need the user's answer first, then other blockers.

### What you can try now
Commands, app flows, or URLs that show delivered behavior, with the branch or
build they need.

### Tidied
**Removed:** each worktree, local branch, remote branch, or output folder,
with the proof it was finished (merged into which ref, at which commit).
**Kept:** each finished-looking item left in place, and why: untracked files,
a lock, another agent, or missing proof.

### Drift and blind spots
- Where plan copies disagree with each other or the evidence, and which copy
  was left alone.
- What could not be checked, and the check that would settle it.

### Records updated
File, repo, branch, and commit, with a one-line list of what changed. Or why
nothing changed: report only, already current, another agent writing there,
or waiting for the user's go-ahead to commit on the default branch.
```

When everything selected is done, or the user sounds ready to stop, offer
`wrap-this-up`.

## Filled example

```markdown
## Reconcile: P1 merged into integration overnight; P2 is half built.

1 of 2 requirements merged into `plc/reconcile`, 0 on `main`.
Since the last status (2026-10-26, `plc/reconcile` at 3c1d2e4): P1 merged into `plc/reconcile` in 9a8b7c6.
Next step: finish the unmatched report (REC-002) in `ledger-wt/reconcile/p2-report`.

### Where we are
Phase 2 is in progress in `ledger-wt/reconcile/p2-report`. Its one commit
stubs `report`; nothing is uncommitted.

### Done
| Requirement / phase | State | Evidence |
| --- | --- | --- |
| REC-001 / P1 | merged into integration | merge 9a8b7c6 on `plc/reconcile`; `test_match` not yet run there |

### In progress
| Checkout | Branch | Ahead / behind target | Uncommitted | Lock | PR | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| ledger-wt/reconcile/p2-report | plc/reconcile-p2 | 1 / 2 behind `plc/reconcile` | none | none | none | p2 child |
| ledger-wt/reconcile/integration | plc/reconcile | 4 / 0 vs `main` | none | none | none | parent |

### Left
**Can start now:** implement `report` and `test_report` (REC-002); run `test_match` on `plc/reconcile`.
**Waiting on:** None.

### Scope added since the plan started
None.

### Decisions since the work started
None.

### Open questions and blockers
None.

### What you can try now
On `plc/reconcile`: `python -c "from src.reconcile import match"`.

### Tidied
**Removed:** worktree `ledger-wt/reconcile/p1-match` and branch
`plc/reconcile-p1`, merged into `plc/reconcile` at 9a8b7c6.
**Kept:** `p2-report` (in progress) and `integration` (the campaign is open).

### Drift and blind spots
- `main` has no copy of the plan yet; it travels with `plc/reconcile`.
- No PR host is configured, so PR state was not checked.

### Records updated
`docs/plans/reconcile/README.md` on `plc/reconcile`, commit 5d6e7f8: Current Work
and Phase Status rewritten (P1 merged into integration, p1 checkout removed,
new Last updated and next action).
```
