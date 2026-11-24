---
name: fable-managed-opus-plc-execution
description: "Fable manages Opus for complex PLC phases with linked implementation decisions. Use when the user requests Fable-managed Opus PLC execution."
model: fable
---

# Fable Managed Opus PLC Execution

Apply the [worker guidance for Opus](../plc-execution/references/worker-profiles.md#coherent-phases).
Use the [manager guidance for Astra and Fable](../plc-execution/references/worker-profiles.md#astra-and-fable-managers).

Read and follow [PLC execution](../plc-execution/SKILL.md) and the
[Claude management rules](../plc-execution/references/claude-management.md).
Resolve missing sibling files from the installed `plc-execution` skill; report
missing dependencies before dispatch.

Use `fable` as the manager and explicitly select `opus` for
implementation and repair children. Use the latest available versions in those
families through the host's supported aliases or selectors, and verify the
resolved models when the runtime exposes them.

Keep this pair throughout the selected work unless the user changes it. Repair
serious failures with the same worker model; this variant has no automatic
escalation. A replacement agent may use that model when needed.
The manager owns delegation, independent review of actual code and repairs,
and integration. Audit reviewers use the manager's model unless separately
specified. Require the shared strict audit gates and preserve the selected
scope, merge route, authorization, and cleanup rules.
