---
name: monitored-opus-plc-execution
description: "Use when the user requests monitored Opus execution for complex PLC phases with linked implementation decisions."
model: opus
---

# Monitored Opus PLC Execution

Apply the [worker guidance for Opus](../plc-execution/references/worker-profiles.md#coherent-phases).

Read and follow both [PLC execution](../plc-execution/SKILL.md) and the
[Opus management rules](../plc-execution/references/opus-management.md).
Resolve missing sibling files from the installed `plc-execution` skill. Report
a missing dependency before dispatching work that needs it.

Use Opus for the parent and `opus` for implementation children. Keep that
choice across phases, follow-up turns, and context compaction unless the user
asks for a change. Repair findings with Opus under the same strict audit and
parent review rules. This variant has no automatic escalation to another
model family.

The parent owns review and integration. An Opus child's report still needs
independent parent review. Preserve the user's selected PLC scope, merge route,
integration target, and authorization boundaries.
