# <Change> Plan

Use this single-document form for bounded work when the repository does not
require a full packet. Remove these instructions and sections that do not apply.

## Current Work

- Owner: <person, team, or role>
- Last updated: <YYYY-MM-DD>
- Selected work and endpoint: <authorized scope and concrete finish>
- State: <implementation; verification; delivery; required records>
- Next action and blocker: <one concrete step; blocker and owner, or none>
- Resume check: <command or inspection and expected result>

Replace this block as work changes; do not append successive checkpoints.

## Outcome And Requirements

State the problem, in-scope outcome, non-goals, and constraints.

| ID | Required behavior | Acceptance criteria |
| --- | --- | --- |
| REQ-001 | <observable behavior> | <objective result> |

## Current System And Design

Record the source revision inspected and relevant code/tests. Verify needed
prerequisites in source or runtime evidence. Explain the chosen approach,
tradeoffs, fixed contracts and ownership; leave routine internal choices open.
Include public input/output and failure examples when behavior changes.

## Steps And Verification

List the delivery order, affected areas, prerequisite checks, exact validation
commands or procedures, expected results, and rollback when needed. Include
required documentation changes and review standards. For shared work, name one
acceptance owner and the exact capability needed from each contributor.
Prove difficult measurement methods early. Before expanding scope, consider
reuse, deletion, or a narrower deliverable; material expansion needs existing
user authority or approval.

## Risks And Open Questions

For each material item, name the affected work, owner, whether it blocks that
work, and the resolving check or permitted temporary assumption.

## Evidence And Completion

Record each result once: requirement ID, tested source, date, relevant environment
and dependencies, method, expected result, actual result, and material limits.
A command may link to the unchanged method above. Keep required skipped checks
incomplete. Separate implementation, verification, delivery, and missing records.

Run focused checks while working and broader checks at delivery boundaries.
Repeat invalidated checks or reviews with a reason; preserve unaffected evidence
and bounded audit limits. Repository-required CI and post-merge checks still apply.
Complete missing records from valid evidence before repeating execution.
Close only when selected acceptance, required reviews and records, and authorized
delivery are verified. Cleanup must also be complete, or each retained checkout
must have an owner, reason, and release condition.
Keep unresolved requirements open; do not weaken acceptance to finish. Replace
superseded instructions in place and keep optional future work outside this delivery.
