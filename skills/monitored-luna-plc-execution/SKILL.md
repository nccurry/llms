---
name: monitored-luna-plc-execution
description: "Run selected PLC work with GPT-6 Luna max child agents, parent review of delivered code, and escalation to GPT-6 Sol medium when quality falls short. Use when the user requests monitored Luna PLC execution."
---

# Monitored Luna PLC Execution

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

## Choose child models

The parent keeps its current model and owns review and integration. Start
implementation children with `gpt-6-luna` and reasoning effort `max`. After a
quality escalation, use `gpt-6-sol` with reasoning effort `medium` for repairs
and all new children for the rest of the selected work. Keep that choice across
phases and context compaction. Do not switch back unless the user asks.

Use subagents for bounded work as the base skill describes. Do not split tightly
coupled work just to increase the agent count. The parent can implement small
remaining changes and still applies the same quality checks.

Pass model and effort explicitly to the subagent tool. With
`collaboration.spawn_agent`, set `model`, `reasoning_effort`, and
`fork_turns="none"`; provide the base skill's full assignment in the message.
A full-history fork inherits the parent's model and cannot select these models.
Tell children not to spawn further agents; the parent owns delegation and model
selection. Use subagents rather than creating separate user-facing tasks.

Check the available tool schema before dispatch. If either required model or
effort is unavailable, report the limitation and ask for an alternative before
dispatching affected work. Do not silently inherit a model or claim that a model
was used when the tool did not accept it.

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
work out of the integration target until repaired and reviewed.

## Escalate on evidence

Escalate immediately when the parent confirms a serious delivery problem: a
material correctness or security defect, missing core acceptance behavior,
bypassed checks, unsupported claims that tests passed, or a design that needs
substantial rework to meet the PLC. Findings from integration tests or external
review count once the parent verifies them and attributes them to the delivery.

For smaller, bounded issues, give the Luna child specific feedback and one
repair attempt. Escalate if the repair still leaves a material issue, or if
the same quality problem recurs in another delivery after feedback. A child
finding and fixing a bug during implementation is normal; judge what it hands
off as ready. A wording correction or formatting fix alone is not an escalation.

Do not treat unavailable tools, credentials, broken infrastructure, a known
baseline failure, or an unanswered product decision as poor code quality.
Handle those through the base workflow. Explain the evidence before attributing
a failure to a child's work.

When escalation is warranted:

1. Notify the user in the current task immediately. State the old and new model
   and effort, the concrete problem and evidence, and what work will switch.
   Do not request fresh permission for the model change this skill authorizes.
2. Record the reason, affected branch or commit, and new model choice in the
   existing work list or phase notes.
3. Stop assigning work to Luna. Let unrelated Luna children already running
   finish, then review their output under the same rules. Pause the affected
   child before handing its files to a replacement; never allow two writers
   to own the same worktree. Preserve its changes and evidence.
4. Spawn a Sol medium repair child with the rejected diff, findings, acceptance
   criteria, and required checks. Record its worktree, branch, and base. If a
   defect is already integrated, start from the latest integration commit as
   the base skill requires.
5. Review the repair and rerun affected tests and audits before accepting it.
   Sol work must meet the same standard. If a blocking finding remains after
   repair and final audit, follow the base skill's stop-and-ask rule; do not
   lower the standard or invent another automatic model tier.

For example: "I switched from GPT-6 Luna (max) to GPT-6 Sol (medium). The phase 2
delivery loses queued writes on retry, and the regression test reproduces it.
Sol will repair this branch and handle new assignments for the remaining work."

## Finish

Include the base skill's completion evidence. Also state which models and
efforts were used, whether escalation occurred, why, and whether the affected
work passed parent review after repair. Preserve unresolved findings and open
decisions instead of reporting the selected work complete.
