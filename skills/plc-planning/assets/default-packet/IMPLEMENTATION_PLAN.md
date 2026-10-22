# <Feature> Implementation Plan

## Selected Delivery

Name the authorized requirements and the concrete endpoint for this delivery.
Explain the order and the smallest useful result. Future feature cohorts do
not extend this delivery automatically.

Before expanding the work, check whether narrowing the deliverable, reusing an
existing owner, or deleting a competing path achieves the approved outcome.
Discoveries do not add scope. Significant expansion beyond existing authority
needs user approval; routine choices and repairs within scope can proceed.
Keep pending proposals separate from accepted work.

## Phase Status

Track implementation, verification, delivery, and required records separately.
Use `Not required` where appropriate. A merged change does not imply acceptance;
a missing record does not imply that implementation or testing must be repeated.

| Phase | Requirements | Prerequisites | Implementation | Verification | Delivery | Evidence record |
| --- | --- | --- | --- | --- | --- | --- |
| [1: <name>](#phase-1-name) | REQ-001 | <exact capability or phase, or none> | Planned | Not run | Pending | Missing |

## Phase Details

### Phase 1: Name

- Change: <behavior, interfaces, and relevant code areas>
- Out of scope: <explicit deferrals>
- Prerequisite check: <how to prove the needed capability is available>
- Validation: <exact commands or procedures, relevant environment, expected results>
- Exit criterion: <objective result for the requirements and delivery>
- Rollback or fallback: <how to unwind a failed change>

For difficult hardware, performance, or platform acceptance, prove the checking
method early: run a small representative case, detect a known failure, and
confirm the result is interpretable before relying on that method for delivery.
Do not add a separate qualification phase for ordinary checks that already work.

## Shared Acceptance Ownership

Use this section only when work crosses packets or repositories. Assign each
shared obligation one acceptance owner. Children prove their contributions;
the parent owns the integrated outcome. Require the exact needed capability,
not completion of every phase in a sibling packet. Name the authoritative
contract and accepted decision or revision each consumer follows.

| Obligation | Acceptance owner | Contributors | Required capability or contract | Proving check |
| --- | --- | --- | --- | --- |
| <integrated outcome> | <one packet or role> | <children or repositories> | <exact prerequisite and contract reference> | <check owned here or linked> |

## Verification Evidence

Record each result once here, or link to the repository's existing evidence
store. Other packet files reference these entries. Keep raw logs outside the
plan. Record skipped or unavailable checks as incomplete when they are required.

### CHECK-001: <check name>

- Requirements: <REQ IDs>
- Source: <tested revision; identify any uncommitted changes tested>
- Conditions: <date, relevant dependency revisions, platform/backend, configuration>
- Method: <exact command or procedure, or link to the unchanged phase method>
- Expected: <pass/fail result>
- Actual: <result, material limits, and evidence link when needed; or not run>

## Review And Recheck Rules

Name required review domains and acceptance standards for this work. Keep model
choices, worker counts, and reviewer scheduling in the execution workflow.

Run focused checks during implementation and broader checks at meaningful
integration or delivery boundaries. Repeat a check or review when changed
behavior, dependencies, environment, or a discovered defect invalidates its
evidence. Name the affected evidence and reason. A new commit hash alone does
not invalidate unchanged evidence; repository-required CI and post-merge checks
still apply. Preserve unaffected evidence and the execution workflow's bounded
audit limits. Failures keep dependent acceptance open; fix them before dependent
work proceeds, while independent authorized work may continue.

When only a required record is missing, first reconcile existing valid results
into that record. Repeat execution only when evidence is missing, insufficient,
or invalidated. Do not waive required reviews, checks, or records.

## Readiness And Completion

Before starting:

- [ ] Every selected Must requirement has a phase, proving check, and exit criterion.
- [ ] Prerequisites for the next runnable block are verified; later dependent
      work stays blocked until its prerequisites pass. Open questions name the
      work they block.
- [ ] Required documentation changes are included in the relevant phase.

Before closing selected work:

- [ ] Every selected requirement has current acceptance evidence and required records.
- [ ] Required audits have no supported actionable in-scope findings remaining,
      including P3. Outside-scope follow-ups are identified separately.
- [ ] Authorized delivery is verified. Cleanup is complete or each retained
      checkout has an owner, reason, and release condition.
- [ ] Current instructions agree on scope, design, results, and remaining work.
      The README resume block replaces earlier checkpoints.

Close a whole phase only when all its requirements and exit criteria pass;
whole-PLC completion covers all required scope. Leave unselected phases open.
Optional outside-scope work does not extend execution or reopen completed work
without user authorization. Evidence that an existing requirement fails reopens
its acceptance. Do not weaken requirements or invent deferrals to claim completion.
