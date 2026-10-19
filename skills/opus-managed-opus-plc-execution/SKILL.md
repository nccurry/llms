---
name: opus-managed-opus-plc-execution
description: "Execute selected PLC work with an Opus parent and Opus children, strict audits, and parent review. Use when the user requests Opus-managed Opus execution. Requires Claude model selection and subagents."
model: opus
---

# Opus-Managed Opus PLC Execution

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
