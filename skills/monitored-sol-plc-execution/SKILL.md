---
name: monitored-sol-plc-execution
description: "Run selected PLC work with GPT-6 Sol medium child agents and parent review of delivered code. Use when the user requests monitored Sol PLC execution."
---

# Monitored Sol PLC Execution

## Reuse PLC execution

Read and follow [plc-execution](../plc-execution/SKILL.md). This skill adds the
model choices and parent review below. It does not copy or replace that workflow.
If the sibling file is missing, locate the installed `plc-execution` skill. If
neither is available, report the missing dependency before starting execution.

Keep the base skill's PLC selection, completion map, prerequisites, worktree
isolation, audits, merge route, decision handling, and phase-close checks. Use
the user's chosen MR, PR, or local integration target. Keep its authorization
boundaries: choosing this skill does not authorize publishing or a final merge
beyond the user's request.

If a technical decision needs to be made that isn't obvious, the parent or
child must stop and ask. A child sends the facts, options, and question to the
parent and waits. The parent asks the user before work that depends on the
decision continues.

After parent review and merge, follow the base skill's suggestion for each
child to clean up only its own worktree once it is no longer in use.

## Choose child models

The parent keeps its current model and owns review and integration. Start
implementation children with `gpt-6-sol` and reasoning effort `medium`. Keep
that choice across phases and context compaction unless the user asks for a
different model.

Use subagents for bounded work as the base skill describes. Do not split tightly
coupled work just to increase the agent count. The parent can implement small
remaining changes and still applies the same quality checks.

Pass model and effort explicitly to the subagent tool. With
`collaboration.spawn_agent`, set `model`, `reasoning_effort`, and
`fork_turns="none"`; provide the base skill's full assignment in the message.
A full-history fork inherits the parent's model and cannot select this model.
Include the base skill's absolute paths and load instruction for `plain-english`,
`design-for-change`, and `verify-before-claiming` in that message, since this
child does not inherit the parent's loaded skills.
Tell children not to spawn further agents; the parent owns delegation and model
selection. Use subagents rather than creating separate user-facing tasks.
Include this skill's audit and decision rules in every child assignment.

Check the available tool schema before dispatch. If either required model or
effort is unavailable, report the limitation and ask for an alternative before
dispatching affected work. Do not silently inherit a model or claim that a model
was used when the tool did not accept it.

## Require child audits before integration

Each implementation child runs `$audit-codebase` on its own branch diff and
personally applies every specialist listed by that skill, even when the base
workflow would mark one not applicable. Record when a specialist finds no
relevant issue. Also run the base skill's extra audits for UI or dependency
changes.

The child fixes every actionable finding in its assigned work, including
nonblocking findings, and reruns the affected audits and tests. It must reach
`PASS`, not `PASS WITH FOLLOW-UPS`, before either agent opens an MR/PR or the
parent merges its work. If a finding needs work outside its assignment or an
unclear technical decision, stop and ask through the parent. Report findings
that are incorrect with evidence; do not silently discard them.

The parent checks the child's audit evidence and reviews the diff before any
merge. Keep the base skill's combined audit after integration.

## Review the work yourself

Tell every child that its work must pass parent review before integration. Add
its model and effort to the existing work list. Ask it to report the tested
commit, commands and results, audit scope and verdict, and evidence for its
completion-map rows.

At each meaningful handoff, the parent reads the actual diff from the recorded
base through the delivered commit, plus enough surrounding code to judge it.
Do this before merging a local branch or approving an MR/PR for merge. Review
later review fixes as well. A child report, passing CI, or an audit's `PASS`
does not replace this review.

Check whether:

- The implementation meets the named PLC requirements and design goals.
- Logic, failure paths, and state changes work with the surrounding code.
- Tests exercise the changed behavior and relevant failure cases. Tests must
  not hide a regression by weakening assertions or deleting coverage.
- Names, control flow, and responsibility boundaries are clear. Added layers
  and dependencies must solve a need in the selected work.
- Changes stay within the assignment, and test and audit claims match evidence.

Reproduce checks needed to establish correctness against the delivered commit
in its worktree before integration. Run the base skill's integration checks on
the combined code as well. Record concrete findings with files, behavior,
missing criteria, or failing checks in the existing phase notes. Keep rejected
work out of the integration target until repaired and reviewed. Give the child
concrete feedback and review its repair. If a blocking finding remains after
repair and final audit, follow the base skill's stop-and-ask rule.

## Finish

Include the base skill's completion evidence. Also state which model and effort
were used and whether the work passed parent review. Preserve unresolved
findings and open decisions instead of reporting the selected work complete.
