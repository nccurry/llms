---
name: monitored-sol-plc-execution
description: "Run selected PLC work with GPT-6.1 Sol medium child agents and parent review of delivered code. Use when the user requests monitored Sol PLC execution."
---

# Monitored Sol PLC Execution

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

The parent keeps its current model and owns review/integration. Use
`gpt-6.1-sol` with reasoning effort `medium` for implementation and repairs.
Preserve these settings across phases and compaction unless the user changes
them. Serious defects receive evidence-based repair and renewed parent review
under the same model; do not invent an automatic model tier.

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

Follow the base skill's independent audit and parent-review requirements.
`audit-codebase` owns specialist selection, applicability decisions, reviewer
dispatch, and the shared ledger. Implementation children request review and
make assigned repairs; they do not spawn reviewers.

Fix every supported actionable in-scope finding, including P3. Require `PASS`
before MR/PR creation or integration, subject only to the base's explicit
user-approved integration exception. Preserve the actual verdict, independent
parent diff review, and required checks before and after final-target merge.

## Finish

Include the base's completion evidence, actual child models/effort, parent
review outcome, and remaining requirements, decisions, or missing checks.
The parent performs the base skill's cleanup throughout execution and reports
verified removals and every retained checkout with its reason and owner.
