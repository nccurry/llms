# <Feature> Implementation Plan

## Strategy

Explain the delivery order, the smallest useful result, and why the order
reduces risk.

Discoveries do not automatically add requirements or phases. Obtain user
approval before adopting or implementing significant expansion beyond existing
authorization, including new deliverables, contract/architecture changes, or a
substantial increase in cumulative work. Continue independent authorized work
while waiting; routine repairs within approved scope can proceed.

Update affected planning sections in place. Preserve requirement IDs and
decision rationale, and reconcile superseded text. Keep current status and
evidence concise in their existing sections; record each result once and link
to it elsewhere. Keep general agent workflow, raw logs, and session narration out
of requirements and design; distinguish unapproved proposals from accepted work.

## Phase Summary

| Phase | Goal | Requirements | Code areas | Validation | Exit criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | <smallest useful result> | REQ-001 | <areas> | <checks> | <result> | Planned |

## Phase Details

### Phase 1: <Name>

- Change: <files, behavior, and interfaces>
- Requirements: <REQ IDs>
- Out of scope: <explicit deferrals>
- Validation: <tests, commands, reviews, or inspections>
- Exit criterion: <objective result>
- Rollback or fallback: <how to unwind a failed change>

## Cross-Phase Risks

| Risk | Affected phases | Mitigation | Owner |
| --- | --- | --- | --- |
| <risk> | <phases> | <mitigation> | <owner> |

## Plan Readiness

- [ ] Every Must requirement appears in at least one phase.
- [ ] Dependencies between phases are explicit.
- [ ] Every phase has validation and an exit criterion.
- [ ] Required documentation changes are included in the relevant phase.

## Completion Criteria

- [ ] Every selected requirement has current acceptance evidence; unselected
      phases remain open. Whole-PLC completion covers all required scope.
- [ ] Required audits have no supported actionable in-scope findings remaining,
      including P3. Outside-scope follow-ups are identified separately.
- [ ] Required specialists reviewed the same stabilized revision read-only,
      in waves of at most three; the parent checked evidence and combined findings.
- [ ] Affected checks were rerun after fixes; the final audit verdict uses
      current evidence and no required check remains incomplete.
- [ ] Authorized final delivery is verified. Cleanup is complete or each retained
      checkout has an owner, reason, and next condition to check.
- [ ] Planning documents show current scope, design, results, and remaining work
      without contradictory instructions or a need to reconstruct session history.

Stop when the selected work meets these criteria. Optional outside-scope
follow-ups do not extend execution or reopen completed work without user
authorization. Evidence that an existing requirement fails reopens its
acceptance. Keep genuine blockers visible; do not weaken or invent deferrals
for required work to declare completion.
