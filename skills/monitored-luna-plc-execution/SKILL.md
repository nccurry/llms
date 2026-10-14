---
name: monitored-luna-plc-execution
description: "Run selected PLC work with GPT-6 Luna max child agents, parent review of delivered code, and escalation to GPT-6.1 Sol medium only for serious delivery failures. Use when the user requests monitored Luna PLC execution."
---

# Monitored Luna PLC Execution

## Reuse PLC execution

Read and follow [plc-execution](../plc-execution/SKILL.md). Resolve it from the
installed skills if the sibling path is absent; report a missing dependency
before execution. This wrapper adds model choices and monitored acceptance,
not a second execution workflow.

Preserve the base's scope, prerequisites, completion map, worktrees, integration
route, authorization, decisions, and phase-close checks. Resolve routine local
choices from evidence and conventions. A child raises only material unresolved
requirements, contracts, scope, architecture, authorization, or recovery risks
to the parent and pauses dependent work; independent work continues. The parent
asks the user only when the existing request and evidence cannot settle them.

The parent reads [parent review](../plc-execution/references/parent-review.md)
before the first handoff and reviews actual delivered code and repairs before
integration. A reported PASS or passing CI does not replace that review.

## Choose child models

The parent keeps its current model and owns review/integration. Begin
implementation children with `gpt-6-luna`, reasoning effort `max`.
After verified quality escalation, use `gpt-6.1-sol`, effort `medium`, for
repair and new implementation children throughout the remaining selected work.
Preserve the choice across phases/compaction; do not switch back unless asked.

Use bounded subagents rather than user-facing tasks. Keep tightly coupled work
together. The parent owns delegation and may finish small remaining changes
under the same checks. Tell children not to spawn further agents.

With `collaboration.spawn_agent`, set the prescribed `model`,
`reasoning_effort`, and `fork_turns="none"`; a full-history fork inherits the
parent's model. Supply the base skill's complete assignment, absolute working
skill paths and load instructions, audit coverage, and decision rules because
the child has no inherited history.

Check the dispatch schema. If the required model/effort is unavailable, report
it and ask for an alternative before affected dispatch. Do not silently use a
different model or claim unsupported settings. These prescriptions apply to
implementation and repair children; audit reviewers inherit the parent's
current model unless the user separately prescribes a reviewer model.

## Strict handoff audit

The parent coordinates the child's audit through `audit-codebase`: one read-only
reviewer per specialist, no more than three concurrently, against the same
stabilized base and revision. Implementation children request review and do not
spawn agents.

Preserve the monitored workflow's coverage: every standing specialist listed
by `audit-codebase` returns a result, even when it finds no relevant concern.
Require the conditional security, UI, and dependency gates when applicable.
The parent checks evidence and records any justified inapplicability; missing
review or validation is `INCOMPLETE`.

The assigned writer fixes every supported actionable in-scope finding, including
P3; reviewers do not edit. Require `PASS` before MR/PR creation or integration.
Apply an explicit user-approved integration exception only within the limits
recorded by the base skill; it does not turn a failed/incomplete gate into PASS.
Outside-scope findings and material unresolved decisions go through the parent.
Reject incorrect findings with evidence. Keep the base skill's independent
parent diff review and combined audit on the prepared candidate before its
final-target merge, followed by required post-merge checks.

## Escalate only for serious delivery failures

Keep Luna for normal naming feedback, local bugs, missing edge-case tests,
ordinary refactoring, and further repair rounds. Finding counts, a failed audit,
or severity labels alone do not justify changing models. Never accept open
findings to avoid escalation.

Switch only after the parent verifies a serious defect in work presented as
ready: major architecture mismatch, a core PLC workflow absent or fundamentally
wrong, material invented APIs/code/test claims, or demonstrated severe
correctness/security failure such as data loss or a broken trust boundary.
Inspect substance and impact; missing logs alone are not hallucinated results.
If seriousness remains uncertain, investigate and retain Luna.

Unavailable tools/credentials, network or infrastructure failures, known
baseline defects, and unresolved product choices are not delivery quality.
A child catching and fixing its own defect during work is normal.

Read [the escalation procedure](references/escalation.md) when a serious
delivery failure is verified. It requires an immediate user-visible explanation,
recorded evidence, exclusive writer ownership, Sol repair, and renewed review.
This explicitly invoked skill authorizes that model change without another
permission question. Keep all strict gates; do not add another automatic tier.

## Finish

Include the base's completion evidence, actual models/effort, any escalation
and its evidence, parent review after repair, and unresolved work/decisions.
Suggest removal only of each delivered child's unused worktree under the
base's preservation and authorization rules.
