---
name: opus-managed-sonnet-plc-execution
description: "Execute selected PLC work with an Opus parent, Sonnet children, strict audits, and parent review. Use when the user requests Opus-managed Sonnet execution. Escalate only serious delivery failures to Opus. Requires Claude model selection and subagents."
model: opus
---

# Opus-Managed Sonnet PLC Execution

Read and follow both [PLC execution](../plc-execution/SKILL.md) and the
[Opus management rules](../plc-execution/references/opus-management.md).
Resolve missing sibling files from the installed `plc-execution` skill. Report
a missing dependency before dispatching work that needs it.

Use Opus for the parent and `sonnet` for implementation children. Keep Sonnet
through ordinary repairs. After a verified serious delivery failure, use `opus`
for the repair and all new implementation children for the rest of the selected
work. Record that choice across phases, follow-up turns, and context compaction.
Do not switch back unless the user asks.

The parent owns review and integration. The shared strict audit and review
rules apply equally before and after escalation. Preserve the user's selected
PLC scope, merge route, integration target, and authorization boundaries.

## Escalate only for serious failures

Ordinary bugs, audit findings, missing edge-case tests, naming feedback, and
repeated minor repairs stay with Sonnet. A finding count, severity label, or
failed audit alone does not justify a model change.

Escalate only when the parent verifies a serious problem in work handed off as
ready, such as:

- A major architectural mismatch requiring substantial redesign to meet the PLC.
- A large plan omission or a claimed core workflow that is absent or
  fundamentally wrong.
- Invented APIs, implementation, or test results that materially undermine
  delivery.
- A severe correctness or security failure, supported by concrete evidence.

Inspect the code or requirement evidence and explain why targeted Sonnet
repair is inadequate. Missing logs alone do not prove invented validation.
Unavailable tools, credentials, infrastructure failures, known baseline
failures, and open product decisions are blockers, not poor delivery. If the
severity is unclear, investigate and keep Sonnet. A child finding and fixing a
problem during implementation is ordinary work.

When a serious failure is verified, notify the user immediately with the old
and new model choices, the evidence, and affected work. This skill authorizes
the switch; do not request fresh approval for it. Record the reason and rejected
branch or commit in the existing phase notes. Stop new Sonnet
assignments. Let unrelated running Sonnet children finish, then review them.

Stop the affected writer before handing its work to an Opus repair child.
Preserve its changes and evidence. Give the replacement the rejected diff,
findings, acceptance criteria, checks, and a verified worktree, branch, and
base. For an already integrated defect, use the latest integration commit.
Review the repair and rerun affected checks. Keep Opus for new implementation
children through the remaining selected work; do not add another model tier.
