---
name: astra-managed-luna-plc-execution
description: "Astra manages Luna for bounded PLC changes with explicit checks. Use when the user requests Astra-managed Luna PLC execution."
---

# Astra Managed Luna PLC Execution

Apply the [worker guidance for Luna](../plc-execution/references/worker-profiles.md#bounded-workers).
Use the [manager guidance for Astra and Fable](../plc-execution/references/worker-profiles.md#astra-and-fable-managers).

Read and follow [PLC execution](../plc-execution/SKILL.md) and the
[Codex management rules](../plc-execution/references/codex-management.md).
Resolve missing sibling files from the installed `plc-execution` skill; report
missing dependencies before dispatch.

Use `gpt-6.2-astra` as the manager and `gpt-6-luna` with reasoning
effort `max` for implementation and repair children. Verify the newest
available IDs in these families from the dispatch schema before starting.

Keep this pair throughout the selected work unless the user changes it. Repair
serious failures with the same worker model; this variant has no automatic
escalation. A replacement agent may use that model when needed.
The manager owns delegation, independent review of actual code and repairs,
and integration. Audit reviewers use the manager's model unless separately
specified. Require the shared strict audit gates and preserve the selected
scope, merge route, authorization, and cleanup rules.
