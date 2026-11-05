# Skill workflows

[Back to the README](../README.md#use-the-skills).

Use this guide to write a change plan, choose implementation agents, and take a
feature through review and delivery. A PLC (Plan-Led Change) records requirements,
design, delivery steps, and checks.

- [Write a change plan](#write-a-change-plan)
- [Choose an execution model](#choose-an-execution-model)
- [Example: take a feature through delivery](#example-take-a-feature-through-delivery)
- [Keep these habits throughout](#keep-these-habits-throughout)
- [Run the Claude workflows](#run-the-claude-workflows)

## Write a change plan

Every plan uses the shared template. A project's own planning format adds its
file names, location, and extra sections before `## Log`. A plan starts as one
README: the [default packet](../skills/plc-planning/assets/default-packet/README.md),
or the [compact plan](../skills/plc-planning/assets/compact-plan.md) for the same
README as a single file. Add SRD.md, SADD.md, or IMPLEMENTATION_PLAN.md only
when the plan has information that belongs there, such as a new public
contract for SRD.md. The planning skill's
[Adding files](../skills/plc-planning/SKILL.md#adding-files) rule lists the
triggers, and its
[Growing a packet](../skills/plc-planning/SKILL.md#growing-a-packet) rule
turns a one-file plan into a folder when one holds. The files of a packet:

![PLC packet: README.md holds the summary, Current Work, the Phases table, Done when, open questions, and the Log. SRD.md defines requirements and their checks; SADD.md explains the design; IMPLEMENTATION_PLAN.md holds phase details and evidence. Add them only when needed. Optional FIXTURES.md holds stable examples and test cases.](images/plc-packet.svg)

This example is trimmed: the other Current Work keys and the "Where the work
lives" table are left out.

```text
# Config reload

Reload the config without a restart, keeping the old config if the new one is invalid.

## Current Work

- Status: In progress
- Owner: @alex
- Last updated: 2026-11-03, `plc/reload` at `abc1234`
- Next action: Finish required PR reviews.

## Phases

| Phase | Name   | Owner | State                                          |
| ----- | ------ | ----- | ---------------------------------------------- |
| P1    | Reload | @alex | Implemented — PR #12 open; local checks passed |

## Done when

- REQ-001: Invalid config leaves the running config unchanged.
  Check: `task test -- reload` → passes

## Log

- 2026-11-02 Created.
- 2026-11-03 P1 Implemented in PR #12.
```

Keep requirement and phase IDs stable. Replace Current Work as work changes,
and add a dated Log line for each change. A phase is Verified only when its
check passed on the merged code. Record each result once and link to it. If a
record is missing, check existing results before running checks again. A
finished plan moves to `completed/`; plans finished earlier into another folder
stay where they are. The full rules and the format check are in
[plc-planning](../skills/plc-planning/SKILL.md#shared-template).

## Choose an execution model

All four monitored workflows reuse [plc-execution](../skills/plc-execution/SKILL.md).
The main agent assigns work, reviews the code, and combines the changes.

| Skill | Main agent | Implementation agents | After a verified serious delivery failure |
|---|---|---|---|
| [monitored-luna-plc-execution](../skills/monitored-luna-plc-execution/SKILL.md) | Current model | GPT-6 Luna, max | Switch repairs and new implementation agents to GPT-6.1 Sol, medium. |
| [monitored-sol-plc-execution](../skills/monitored-sol-plc-execution/SKILL.md) | Current model | GPT-6.1 Sol, medium | Repair with Sol. |
| [monitored-sonnet-plc-execution](../skills/monitored-sonnet-plc-execution/SKILL.md) | Opus | Sonnet | Switch repairs and new implementation agents to Opus. |
| [monitored-opus-plc-execution](../skills/monitored-opus-plc-execution/SKILL.md) | Opus | Opus | Repair with Opus. |

Your agent app must support the selected models and subagents. Ordinary bugs and review
corrections stay with the assigned model.

## Example: take a feature through delivery

```text
$plc-planning Plan config reloads. Show expected behavior, failure cases,
phases, and how each requirement will be verified.

$monitored-sol-plc-execution Implement P1 only. Include tests and docs.
Use an isolated worktree and open a PR to main. Do not merge it.

$plc-checkpoint Record P1's checks, PR state, and remaining work.
```

`plc-planning` has a subagent review a new plan, and any later change to its
scope, with `review-and-fix-plc` before handing it off. Ask for
`$review-and-fix-plc` yourself only for an extra review.

After approval to merge:

```text
$wrap-this-up Complete the agreed PR delivery after required checks pass.
Verify main, update the PLC, and remove eligible task-owned worktrees.
```

## Keep these habits throughout

| Skill | What it looks like |
|---|---|
| [plain-english](../skills/plain-english/SKILL.md) | “Reload keeps the old config if validation fails.” |
| [design-for-change](../skills/design-for-change/SKILL.md) | “Keep parsing separate from applying the config.” |
| [verify-before-claiming](../skills/verify-before-claiming/SKILL.md) | “Local checks passed; CI is pending; the PR is unmerged.” |

Use focused specialists for focused questions: [audit-tests](../skills/audit-tests/SKILL.md)
for missing coverage, [test-quality-audit](../skills/test-quality-audit/SKILL.md) for weak
tests, and [docs-sync](../skills/docs-sync/SKILL.md) for documentation drift.
During authorized implementation, the combined audit uses specialist reviewers and
fixes confirmed problems within the agreed scope. Repeat an audit only after a
serious finding or substantial change; stop after three consecutive passes.

## Run the Claude workflows

The main agent arranges independent audits, fixes confirmed problems within the
agreed scope, and reviews the code before combining changes. Both workflows keep
Claude’s configured effort unless you choose another setting. Model names such as
`opus` use the family alias; a version you explicitly request takes precedence.

Invoke them in Claude Code as `/monitored-sonnet-plc-execution` or
`/monitored-opus-plc-execution` with the selected PLC work. Their `model: opus`
setting requests Opus for the current turn. Use `/model opus` or start with
`claude --model opus` to keep the session on Opus across follow-up turns. Other
agent apps must support the requested Claude models and subagent model selection
to run these workflows.
