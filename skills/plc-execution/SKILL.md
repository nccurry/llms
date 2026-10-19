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

## Scope changes and planning documents

Record the selected requirement IDs and exit criteria in the existing work list
before execution. Discoveries do not add requirements or phases by themselves.
Significant expansion includes new deliverables, phases for additional work,
unapproved contract or architecture changes, or a materially larger total effort,
including small additions that accumulate. Check existing authorization first.
If it does not cover the expansion, explain the proposed work, why it is needed,
its effect on delivery, and alternatives; obtain user approval before adopting
or implementing it. Continue independent authorized work while waiting. Routine
implementation choices and repairs within approved scope remain authorized.

Keep planning documents coherent for the next agent. Update affected sections
in place, preserve stable requirement IDs and decision rationale, and reconcile
superseded or contradictory instructions across the packet. Requirements and
design describe approved behavior and adopted decisions. Keep current status,
remaining work, and concise validation evidence in the existing work list or
status/evidence sections. Record each result once and link to it elsewhere;
do not restate the skill's general workflow in the packet. Keep raw logs,
repeated handoffs, abandoned attempts, and session narration out of requirements and
design. A new reader must be able to identify approved scope, current design,
and remaining work without reconstructing the conversation. Label pending
proposals as unapproved; do not silently weaken or defer requirements to match
delivered code.

## Prepare the work and integration

Read root/scoped `AGENTS.md`, selected PLC files, source, and relevant product
and design documentation. Use named goals in the owning project documents to
interpret selected requirements; do not guess project facts or silently add
deliverables. Raise material conflicts under the scope-change rule above.

Make one work list containing each selected block, prerequisites, owner, files,
behavior, design goals, tests, audits, exit criteria, and readiness. Run a block
only after its prerequisites pass. Discovery may precede a prerequisite when it
cannot alter that prerequisite.

Map each selected requirement and named design goal to its existing PLC ID,
owner, proving check/review, and state: pending, verified, deferred, or blocked.
Keep this completion map in the existing work list or phase notes; do not create
a second durable plan. Record audit scope, base, and verdict as evidence, not an
uninspected shell command.

Choose and record the integration route, target branch, worktree, and base
before dispatch. Follow the user's choice, then established repository/session
conventions. Ask if a material integration choice remains unresolved.
Distinguish temporary integration from the final delivery branch and record
whether final delivery is local or remote before selecting its cleanup proof ref.

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

## Cleanup during execution

The parent owns cleanup, including after a child exits or is replaced. Invoking
this workflow authorizes removal of temporary local branches and worktrees it
creates once delivery and removal checks pass, unless the user asks to keep them.
Apply existing authorization without another cleanup question. This permission
does not extend to unrelated checkouts, remote branches, or final integration.

Before creating worktrees, read [the cleanup procedure](references/worktree-cleanup.md)
and locate [clean-stale-worktrees](../clean-stale-worktrees/SKILL.md). Track every
temporary child, integration, and combined-verification checkout in the existing
work list, with its owner, absolute path, branch/commit, final delivery target,
and cleanup state. Preserve these facts across handoffs and compaction.

After each verified delivery and its required checks, the parent investigates
whether the exact source reached main or the user's selected final target.
A merge into a temporary integration branch alone is insufficient. Follow the
cleanup skill's full proof sequence, including squash, historical-content, and
cherry-pick checks; lack of ancestry alone is not proof of missing delivery.
Then remove eligible worktrees and local branches after all users and processes
have released them. Children report release; the parent performs cleanup.

Revisit retained work at phase close and before finishing. Each tracked checkout
must be removed with verification or retained with a specific reason and next
condition to check. Never force worktree removal or discard needed files.

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
Record an answer in the affected PLC sections when it changes requirements,
design, or acceptance, following the document-maintenance rule above.

Discovery may trace code, run checks, and make a small reversible experiment in
its own checkout. Separate facts, options, and experiments in its report. Do
not integrate an experiment that commits the user to a material unanswered
product, contract, data, security, or architecture choice.

## Finish

Close the selected work when its approved requirements and required acceptance
checks pass, authorized delivery is verified, and cleanup is completed or each
retained checkout is accounted for under the cleanup rules. Leave unselected
phases open. Record optional discoveries separately as outside-scope follow-ups;
they do not extend this run or reopen completed work without user authorization.
New evidence that an existing requirement fails does reopen its acceptance.
If a genuine acceptance blocker needs significant extra scope, report the
blocker and request a decision; keep that requirement open while waiting.

Write assignments, notes, and reports in plain English using existing product
names. Show representative behavior/command/config examples when they help the
user assess the result.

Report selected work and prerequisites, integration route, child branches and
commits, actual models when prescribed, MR/PRs, audit and check evidence, and
completion-map states. Preserve every open requirement, decision, and missing
check. Final target integration requires existing user authorization and all
required reviews, tests, audits, and CI, except as explicitly authorized by a
bounded exception recorded under [integration safety](references/integration-safety.md).
Include cleanup proof, verified directory/registration and branch removal, and
every retained checkout with its owner and reason. Cleanup still pending must
remain visible even when implementation is complete.
