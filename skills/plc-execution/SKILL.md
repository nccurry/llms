---
name: plc-execution
disable-model-invocation: true
description: "Execute selected PLC work when called as $plc-execution or by a monitored PLC execution skill. Supports isolated children, strict audits, and direct or MR integration."
---

# PLC Execution

## Invocation and selected work

Use only when the user calls `$plc-execution` or requests
`monitored-luna-plc-execution` or `monitored-sol-plc-execution`.

Execute the named PLC, phases, sub-phases, related phases, or concrete block.
A user-defined block is the scope even if it crosses phase boundaries. Phase
names mentioned as context do not expand that block. Locate the PLC from the
request and repository; ask when the selected scope cannot be established or
materially conflicts with it. Use `plc-planning` to create or repair the packet.
Discovery can run within an existing PLC.

Before dispatch, read [plain-english](../plain-english/SKILL.md),
[design-for-change](../design-for-change/SKILL.md), and
[verify-before-claiming](../verify-before-claiming/SKILL.md). Resolve their absolute
paths. Give every child those paths and explicit load instructions; inherited
context is not proof that it read them. Report missing dependencies before
assigning affected work.

## Prepare the work and integration

Read root/scoped `AGENTS.md`, selected PLC files, source, and relevant product
and design documentation. Discover named goals in the owning project documents
and use them as acceptance criteria; do not guess project facts.

Make one work list containing each selected block, prerequisites, owner, files,
behavior, design goals, tests, audits, and readiness. Run a block only after its
prerequisites pass. Discovery may precede a prerequisite when it cannot alter
that prerequisite.

Map each selected requirement and named design goal to its existing PLC ID,
owner, proving check/review, and state: pending, verified, deferred, or blocked.
Keep this completion map in the existing work list or phase notes; do not create
a second durable plan. Record audit scope, base, and verdict as evidence, not an
uninspected shell command.

Choose and record the integration route, target branch, worktree, and base
before dispatch. Follow the user's choice, then established repository/session
conventions. Ask if a material integration choice remains unresolved.

- Direct integration: the parent merges child branches into the chosen target.
- MR/PR integration: branches receive host review and CI. Read
  [the MR procedure](references/merge-request-integration.md) when this route
  applies, including its review, comment-resolution, and CI gates.

Prefer a separate non-default integration branch/worktree for isolation. Use
`main`, another default branch, or the source checkout only when the user chose
it as the clean target. Do not alter or stash a dirty user checkout.

Before final-target integration, use the applicable parts of
[integration safety](references/integration-safety.md) for concurrent updates,
combined-source verification, platform evidence, or existing failures.

Locate `audit-codebase` and its required specialists before dispatch. For MR
work, verify authenticated host tools can read reviews and CI. Missing required
tools leave the dependent step incomplete; continue independent work.

## Children and worktrees

Assign at least one implementation or discovery child, including for a single
tightly coupled block. Use more only for independent file ownership and
contracts. Do not parallelize writers that share an API, schema, data format, or
unresolved design choice.

The parent creates and checks each child worktree; spawning may reuse the
caller folder. Use a distinct branch and sibling folder outside other worktrees.
Record the immutable base and read status in that exact checkout:

```text
git worktree add -b <child-branch> <absolute-child-path> <integration-commit>
git -C <absolute-child-path> status --short --branch
```

Read [the child assignment requirements](references/child-assignment.md) before
dispatch. Include the absolute worktree and skill paths, scope, prerequisites,
acceptance, ownership, integration route, check plan, reporting requirements,
and authorization limits. Children do not spawn agents: the parent owns all
implementation and audit delegation.

Children edit only their assigned checkout and files, run focused checks,
request audit of stabilized work, fix supported findings, and deliver a clean
commit with current evidence. They do not merge/rebase shared branches. Pushes
and MR creation require the assigned authorized route.

## Strict independent audits

After a meaningful block, the implementation child pauses edits and requests
review from the parent with its exact base, revision/diff, and evidence. The
parent follows `audit-codebase`: one read-only reviewer per required specialist,
at most three concurrently, with no recursive delegation. Give implementation
children time to yield slots. Review the combined diff after meaningful
integration or at a work-item boundary even when handoff audits passed.

Assess every listed domain and run required specialists. Add rendered UI review
or dependency review when relevant; include the security gate when applicable.
A discovery-only task or tiny no-code edit can wait for the next meaningful
block; group related small corrections and record the reason.

Fix every supported actionable in-scope finding, including P3. The parent owns
the ledger, deduplication, evidence checks, fix ownership, and expensive tests.
The assigned writer makes repairs after reviewers finish. Refresh invalidated
reviews/checks against stabilized changes; preserve unaffected evidence.
Only `PASS` permits integration. `REWORK REQUIRED`, `INCOMPLETE`, or recorded
in-scope follow-ups do not satisfy strict acceptance.
A user's explicit bounded integration exception can permit only its named
merge under [integration safety](references/integration-safety.md); retain the
actual failed/incomplete verdict and unresolved acceptance.

Read `git status --short` in the exact worktree at each handoff/integration.
Source review, passing CI, and a child's report are distinct evidence; none
replaces parent inspection of the delivered diff and relevant surrounding code.

## Parent review and phase close

Read [the parent review requirements](references/parent-review.md) before the
first delivery. Verify checks against the actual child commit in its checkout
before integration; tests on the old integration tree do not prove that change.
Verify the child combined with the current target before its final-target merge.
Reuse a checked child/integration tree when it already represents that source;
prepare an isolated combined candidate when needed. Integrate one child at a
time; afterward verify the delivered tree and required post-merge checks.

Before accepting a work item or dependency group into its final target, using
the prepared combined source:

1. Run its required checks against the combined integration tree.
2. Run the combined strict audit. For UI changes inspect the rendered behavior
   against the design goals.
3. Assign any needed repair to a child based on the latest integration commit;
   review and verify it before accepting it.
4. Reconcile the completion map with current source and the user request.
   Selected requirements need owners and current proof.
5. Update PLC results only after their checks pass. Mark a whole phase complete
   only when all its requirements passed, even if the selected block was smaller.

Use `audit-codebase`'s bounded convergence: one initial pass and at most one final
aggregate verification, refreshing affected evidence. If work remains, report
the exact repair, missing proof, or material decision rather than repeating an
unchanged full audit or declaring completion.

After confirming delivery and checks, suggest removing only that child's
worktree when no process needs it. Check the exact path and preserve needed
modified, untracked, or ignored files first. Never force removal, remove another
worktree, or delete branches without cleanup authorization.

## Resolve decisions without needless interruptions

Inspect the PLC, source, project conventions, and existing user authorization
before raising a question. Make routine reversible implementation choices
within those constraints; unfamiliarity or several reasonable options alone
does not require user input.

A child brings unresolved facts/options to the parent and pauses only dependent
work. The parent resolves implementation details and asks the user only when
the remaining choice materially affects:

- Requirements or acceptance, including a consequential conflict between the
  PLC and current behavior.
- Public contracts, stored data, migrations, security, or architectural
  boundaries beyond what was authorized.
- Scope, integration authorization, or a recovery step that risks user work.
- A genuine product/design tradeoff or required validation that cannot safely
  be satisfied within the current task.

Continue independent work while waiting. Explain the concrete consequence and
ask a focused question; do not ask again about an already settled choice.
Record an answer in the PLC when it changes requirements, design, or acceptance.

Discovery may trace code, run checks, and make a small reversible experiment in
its own checkout. Separate facts, options, and experiments in its report. Do
not integrate an experiment that commits the user to a material unanswered
product, contract, data, security, or architecture choice.

## Finish

Write assignments, notes, and reports in plain English using existing product
names. Show representative behavior/command/config examples when they help the
user assess the result.

Report selected work and prerequisites, integration route, child branches and
commits, actual models when prescribed, MR/PRs, audit and check evidence, and
completion-map states. Preserve every open requirement, decision, and missing
check. Final target integration requires existing user authorization and all
required reviews, tests, audits, and CI, except as explicitly authorized by a
bounded exception recorded under [integration safety](references/integration-safety.md).
