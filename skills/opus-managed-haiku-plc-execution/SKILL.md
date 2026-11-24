---
name: opus-managed-haiku-plc-execution
description: "Opus manages Haiku for bounded PLC changes with explicit checks. Use when the user requests Opus-managed Haiku PLC execution."
model: opus
---

# Opus Managed Haiku PLC Execution

Apply the [worker guidance for Haiku](../plc-execution/references/worker-profiles.md#bounded-workers).

Read and follow [PLC execution](../plc-execution/SKILL.md) and the
[Claude management rules](../plc-execution/references/claude-management.md).
Resolve missing sibling files from the installed `plc-execution` skill; report
missing dependencies before dispatch.

Use `opus` as the manager and explicitly select `haiku` for
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
