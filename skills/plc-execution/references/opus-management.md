# Opus management rules

Read this with the selected Opus-managed skill and `plc-execution`. These rules
add Claude model selection and the existing monitored skills' strict acceptance
standard. Keep the base workflow's completion map, prerequisites, assignments,
isolation, integration checks, decision handling, and cleanup rules.

## Keep the parent on Opus

Use a session with an Opus parent and tools that can select Claude child models.
In Claude Code, the wrapper's `model: opus` requests Opus for the current turn;
it does not save the session's model. Other hosts must select Opus through their
own supported controls; the frontmatter does not add that capability.
Before dispatching work or accepting a delivery, check the active parent model
from the runtime information available to you. Recheck on follow-up turns and
after recovery. A frontmatter value or a model requested in a prompt is not
proof of the model that actually ran.

If the parent is not Opus, ask the user to select Opus through the host's model
controls, such as `/model opus` or `claude --model opus` in Claude Code, then
continue. If the runtime does not expose enough information to establish the
parent or child model, report that limit before dependent dispatch or
acceptance. Do not claim that a Codex session became Opus or launch a separate
CLI session to bypass a missing
model-selection capability. Keep this workflow in the main conversation so
the parent can delegate and ask the user about unresolved choices.

Use the wrapper's child family explicitly. In Claude Code, pass
`model: "sonnet"` or `model: "opus"` to the writable general-purpose Agent tool
when its schema supports that field. Other hosts may require a provider and
full model ID instead of a Claude Code alias. Use their supported selectors or
an already available writable subagent configured for the family, and verify
its selection. Do not rely on model inheritance for Sonnet children under an
Opus parent. Read-only research agents cannot take implementation assignments.

Check the actual tool schema and model access before dispatch. Respect a
user-pinned model version within the requested family. Otherwise use family
aliases; do not hardcode today's release IDs. Model policies, environment
overrides, or provider mappings can change what runs. If selection fails or
resolves to a different family, report it and ask for an alternative before
dispatching more affected work. Preserve any existing delivery for review.

Keep the configured Claude effort unless the user requests one. GPT reasoning
levels do not define a Claude effort setting. Apply an explicit user choice
only through controls this runtime supports. Record the requested model and,
when exposed, the resolved model and effort. Label unknown values as unknown.

## Give children complete assignments

Dispatch at least one child as the base workflow requires. Keep tightly coupled
work with one child and use parallel children only for independent ownership.
The parent can finish small remaining changes under the same checks.

Use the base skill's full assignment, including the absolute paths and load
instructions for `plain-english`, `design-for-change`, and
`verify-before-claiming`. Ordinary Claude subagents start with fresh context;
they do not inherit the parent's conversation or loaded skills. Also give them
the resolved audit skill paths, strict acceptance rules below, and any selected
escalation policy. A configured subagent's `skills` field may preload working
skills, but each child must still confirm which files it loaded.

Tell children they are not alone in the repository. They must preserve other
agents' changes and edit only their assigned worktree and files. Do not assume
that dispatch creates a worktree: use the base workflow's parent-created,
checked worktrees from the recorded integration commit. In Claude Code, shell
directory changes do not persist between calls; use absolute paths or enter
the assigned worktree in each command. Record each child's ID, model choice,
worktree, branch, and base so repairs reach the same delivery.

Tell implementation children not to delegate further. The parent owns all
implementation and audit delegation and model selection. A child with a
material unresolved choice reports the facts, options, and question to the parent and waits or
returns a blocked handoff. It must not guess because it lacks a user-question
tool. The parent follows the base workflow's stop-and-ask rules and can keep
independent work moving while that choice is pending.

## Require strict audits and parent review

Read [parent review](parent-review.md) before the first delivery. Follow the
base's independent audit process: the implementation child pauses edits and
requests review; the parent coordinates one read-only reviewer per specialist,
at most three concurrently, against the same stabilized base and revision.
Implementation children do not spawn reviewers or substitute self-review for
this gate. Audit reviewers use the Opus parent's model unless the user separately
prescribes their model; the wrapper's worker choice applies to implementation
and repairs.

Preserve the monitored workflows' coverage: every standing specialist listed
by `audit-codebase` returns a result, including when it finds no relevant issue.
Apply conditional security, UI, and dependency gates when required. The parent
checks evidence and records justified inapplicability. Missing review or
validation is `INCOMPLETE`.

Fix every actionable finding in scope, including nonblocking findings. Verify
repairs with diff inspection and affected tests; repeat audits only for serious
findings or substantial changes under `audit-codebase`'s three-pass limit.
Require `PASS` before either agent opens an MR/PR or the parent integrates the
delivery. `PASS WITH FOLLOW-UPS` does not meet this
standard. If a finding needs work outside the assignment or an unresolved
decision, report it through the parent. Explain rejected findings with evidence.
Apply an explicit user-approved integration exception only within the base's
recorded limits; it does not change a failed or incomplete verdict into `PASS`.

Before integration, the parent reads the actual diff from the recorded base
through the delivered commit and enough surrounding code to judge it. Review
the PLC requirements, behavior and failure paths, tests, names, responsibility
boundaries, scope, and audit evidence. Verify relevant checks against that
commit in the child's worktree. A child's model, claimed audit pass, or green
CI cannot replace this review.

Keep rejected work out of the integration target. Give the child concrete
findings and review the repair, including later review fixes. Keep the base
workflow's checks and combined audit after integration. Stop under its rules
if a blocking finding remains after repair and final audit.

## Finish with evidence

Include the base workflow's completion evidence, actual model information
available from the runtime, any escalation and its reason, and the parent's
review result. Keep deferred or blocked requirements and open decisions visible.
The parent performs the base's cleanup throughout execution, including replaced
Sonnet checkouts, and reports verified removals and every retained checkout with
its reason and owner. Publishing and final integration keep the base workflow's
authorization boundaries.

Claude runtime references: [skills](https://code.claude.com/docs/en/skills),
[subagents](https://code.claude.com/docs/en/sub-agents), and
[model configuration](https://code.claude.com/docs/en/model-config).
