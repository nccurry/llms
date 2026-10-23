---
name: wrap-this-up
description: "Checkpoint PLC/work tracking, close out completed work through its agreed direct or PR/MR route, and clean up task-owned local branches and worktrees. Use to update progress records, 'wrap this up', or finish delivery/cleanup after PLC, Luna, or Sol execution."
---

# Wrap This Up

Reconcile the selected work with current evidence, then complete the requested
delivery and cleanup. Continue from the existing workflow and authorization.

## Choose the mode and scope

- **Checkpoint:** Update existing work records. Leave unfinished work open.
  This does not authorize merging, pushing, or deleting branches/worktrees.
- **Closeout:** Reconcile records, verify readiness, complete the agreed delivery
  route, and remove eligible temporary local resources. Preserve explicit holds
  and narrower instructions such as "open the PR but do not merge it."
- **Cleanup only:** Update cleanup records and remove eligible local resources.
  Preserve undelivered changes unless their delivery is already authorized.
  Cleanup permission does not authorize a new remote integration.

Recover the selected block from the request, conversation, and existing work
list. Include its accepted prerequisites, not every related phase or checkout.
A completed block may belong to an unfinished phase or PLC. If scope remains
materially ambiguous, update known records and ask before dependent actions.

## Reuse the owning workflow

Resolve named skills from the installed catalog. Apply `plain-english` and
`verify-before-claiming`; apply `design-for-change` when repairing implementation.

For PLC execution work, read the applicable `plc-execution` procedures for
completion mapping, parent review, integration safety, PR/MR delivery, and
cleanup. Resume their recorded gates without redispatching completed work.
Preserve the active monitored Luna/Sol workflow's model choices, escalation
state, strict acceptance, and parent ownership when repairs require children.

Use `plc-planning` for planning format/lifecycle, `docs-sync` for affected
maintained documentation, and `clean-stale-worktrees` for cleanup proof and
removal. Missing guidance blocks its affected operation, not independent updates.
Without a PLC, use the task and repository's acceptance/checks; do not create a
planning packet or impose the full PLC audit workflow solely for closeout.

## Recover current state

Read applicable `AGENTS.md`, tracking documents, and validation/review evidence.
Inspect current source, Git refs/status, worktrees, and applicable PR/MR state.
Verify checked boxes and child reports against the sources that prove them.

Refresh the existing work list/completion map rather than creating another ledger:

- Selected requirements, owners, prerequisites, acceptance, and open work.
- Required checks/reviews and the source/environment each result establishes.
- Direct or PR/MR route, final target/ref, local or remote delivery, authorization,
  and merge convention. Distinguish temporary integration from final delivery.
- Every task-owned child, repair, replaced-child, integration, and verification
  checkout: absolute path, branch/commit, owner, purpose, and cleanup state.
  Recover omitted candidates from task artifacts and Git evidence.

Inspect and attribute dirty files; expected task edits are normal. Stage only
understood task changes. Preserve other work without stashing, resetting, or
overwriting it. Obtain release from writers before final integration or removal;
a checkpoint records active ownership without interrupting implementation.

## Reconcile records and documentation

Update the records actually used: planning overview, requirements, design,
implementation steps, completion map, findings, and relevant status/index pages.
Preserve repository formats, IDs, decisions, and meaningful history. Update
maintained product documentation where behavior changed.
Move useful implementation notes into those records and commit them with the
work. Delete temporary notes when no longer useful; do not leave the only
current notes as dirty files in an old checkout.

- Distinguish implemented, verified, delivered, and cleanup pending using existing
  fields or brief notes. Record actual outcomes, not intended merges or removals.
- Complete a requirement only after its acceptance passes; complete a phase only
  after all its requirements pass. Complete a whole PLC only after its required
  scope and lifecycle gates pass. Leave future phases open.
- Keep missing proof, supported in-scope findings, incomplete variants, and
  material decisions visible with an owner and next action. Preserve approved
  deferrals and revisit conditions; do not invent deferrals to close work.
- Reconcile design notes with adopted behavior. Surface material requirement/code
  conflicts rather than rewriting requirements to make the code appear complete.

Run applicable documentation checks and inspect the diff. Commit updates when
the existing workflow calls for it. For a checkpoint, report progress and stop here.
For cleanup-only requests, continue to cleanup within the existing authorization.

## Complete an authorized closeout

1. **Settle the route.** Follow the current user choice, then the recorded route
   and repository/session conventions. Closeout authorizes that known route,
   including necessary pushes to its stated remote destination, within explicit
   user limits. If target or authorization remains unresolved, prepare the
   reviewable result and ask only about that choice.

2. **Establish readiness.** Run missing required checks and satisfy the owning
   workflow's parent review, audit, CI, and host review gates. Inspect delivered
   code. Reuse evidence only while its source, relevant dependencies,
   platform/backend, and configuration remain applicable. Refresh affected
   evidence after changes; preserve unaffected results and bounded audit limits.
   Resolve routine closeout repairs/conflicts within scope. Substantive unfinished
   implementation or unavailable required proof keeps closeout pending. Continue
   previously authorized work under its execution workflow without adding phases.
   An existing bounded integration exception permits only its named merge and
   retains actual failed/incomplete acceptance; it does not complete the PLC.

3. **Deliver the prepared source.** Include reconciled documents. Inspect the full
   diff and isolate unrelated or unfinished changes. Follow the owning direct or
   PR/MR integration procedure. Verify combined source and recheck target
   identity/status immediately before merging. A moved target requires
   reconciliation and refreshed affected checks. Preserve required PR/MR routes,
   reviews, CI, and actionable-comment gates. Reuse the task's existing PR/MR when
   appropriate and attach created PRs through available host task tools. Use
   `create-mr-description` to draft or refresh its description before opening it
   and after source, target, or validation changes, including work without a PLC.
   Recheck the description before final merge readiness.

4. **Verify delivery and acceptance.** Inspect the actual final target and required
   post-merge checks, including remote identity for remote delivery. A temporary
   branch merge or unmerged PR/MR leaves final delivery pending. A post-merge
   failure leaves acceptance open even though delivery happened; record it and
   keep only resources needed for the active repair, with an owner and release
   condition. Raw receipts do not require indefinite retention after merge.

5. **Finish the records.** Record observed outcomes under repository lifecycle
   rules. Deliver final tracked documentation edits through the same route,
   refreshing affected checks. Keep the packet in a surviving committed
   location. After merge or checkout closure, discard task receipts, raw logs,
   binaries, caches, and disposable notes without an archive or recovery bundle.

## Clean up task-owned local work

Revisit every task-owned temporary resource, including abandoned/replaced
children and unused output in retained checkouts. A source or delivery blocker
does not require keeping build directories, staging copies, or caches that are
no longer needed. Remove eligible resources now, following
`clean-stale-worktrees` for every proof, removal, and verification step and,
when applicable, `plc-execution`'s cleanup procedure:

- Work through the task's campaign folder (see `start-this-up`'s worktree
  layout reference) and any task-owned checkouts outside it. Select only
  task-owned candidates.
- Remove clean, unlocked, idle checkouts and keep their branches. Delete a
  branch or discard local changes only with the proof the cleanup skill
  requires against the actual final target.
- Honor worktree locks and current user keep instructions. Reconcile old
  blanket handoff holds with the user's current policy.
- When the campaign is closed, delete its untracked output folder and remove
  the empty campaign folder.

Update the existing cleanup record: each resource is verified removed, or
retained with its owner, concrete reason, and next condition to check. Keep final
records in a surviving location; deliver tracked cleanup-status edits when
repository rules require them. Remote branch deletion, chat archival, and
unrelated cleanup require separate authorization.

## Report the result

State mode/scope, records updated, acceptance and evidence, actual delivery
target/result, verified removals, and every retained resource or open item with
its next action. Keep acceptance, delivery, and cleanup outcomes separate.

Call closeout complete only after required acceptance and delivery succeed and
every eligible temporary resource is removed. Explain protected or explicitly
retained resources; unfinished eligible cleanup remains pending.
