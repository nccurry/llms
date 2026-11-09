# <Feature> Implementation Plan

Phase state lives in the README's [Phases](README.md#phases) table. This file
holds the steps, checks and evidence that need more detail.

## Selected Delivery

<Authorized outcome and requirement IDs, the smallest useful endpoint and why the phases have this order.>

<!-- Keep only sections that apply. Use paragraphs for explanations, numbered
steps for sequences and tables for comparisons or short repeated records.
Use deeper headings under each ### P<n> boundary. When duplicate headings are
 disallowed, qualify them with the phase or topic. Remove all authoring notes.
Generic execution/review policy stays in skills; name only this work's required
checks, constraints and exceptions here. -->

## Phase Details

### P1: <name>

<Scope paragraph: behavior, affected interfaces and code areas.>

Requirements: <REQ IDs>. Out of scope: <explicit deferrals, when relevant>.

#### P1 Prerequisites

<Required capability, owner, availability check and work it blocks. Delete when unnecessary.>

#### P1 Steps

1. <First action and its observable result.>
2. <Next action, including the relevant tests and docs.>

#### P1 Validation

| Check | Expected result |
| --- | --- |
| `<command or procedure>` | <pass/fail outcome and relevant conditions> |

Exit criterion: <result that proves the phase's requirements>.

#### P1 Evidence

<!-- Add actual results only after checks run, or clearly attribute supplied
results. Use a short table or headed records according to the context needed.
Record a result once and link to it elsewhere. Unrun required checks stay open.
Keep raw logs outside the packet. Delete this section until results exist. -->

##### <YYYY-MM-DD> — <check or requirement IDs>

Source: `<revision and relevant uncommitted changes>`. Environment: <relevant conditions>.
Method: `<exact command or procedure>`. Expected: <result>.
Actual: <observed result>. Limits: <what this result does not establish>.

#### P1 Rollback Or Fallback

<Action to unwind a failed change, when one is needed.>

## Shared Acceptance Ownership

<!-- Keep only for work across packets/repositories. Name the exact required
capability and accepted contract, not every phase of a sibling packet. -->

| Obligation | Acceptance owner | Contributors | Required capability or contract | Proving check |
| --- | --- | --- | --- | --- |
| <integrated outcome> | <one packet or role> | <contributors> | <contract reference> | <check owned here or linked> |
