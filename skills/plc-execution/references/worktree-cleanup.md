# Cleanup of execution worktrees

Read before creating temporary worktrees and apply after each verified delivery.
The parent owns this work; children release checkouts and supply evidence.

## Record ownership and the destination

Use the existing work list to record each temporary checkout's absolute path,
branch and source commit, owner, purpose, final target ref/hash, and cleanup state.
Include planning, child, integration, repair, replaced-child, review, and
verification checkouts. Record the source of any user keep instruction.
Useful implementation notes and concise validation outcomes belong in the
committed PLC packet. Receipts, raw logs, binaries, caches, and disposable notes
may be discarded after merge or checkout closure; no archive is required.

Use main, or the repository's equivalent final branch, unless the user chose
another final destination. A temporary integration branch is not that destination
merely because children merge into it. If the user explicitly accepts delivery
into another branch, prove delivery to that exact ref and preserve any checkout
still needed for further integration. Use a local ref only for an authorized
local destination; remote delivery requires the actual remote result.

## Investigate delivery before removal

Read and follow [clean-stale-worktrees](../../clean-stale-worktrees/SKILL.md).
Use Git and host review tools directly to inspect current source, history,
local states, and ownership. A squash or rebase can deliver work without
preserving child commit ancestry. Check commits added after the merged source.
An MR title, child's report, or failed ancestry check alone does not settle it.

Select only task-owned candidates. Record the actual final ref/hash and source
tip. Never substitute a temporary branch just to obtain a match. Reconcile
campaigns and successor integrations before individual checkouts: duplicate
snapshots and superseded prototypes are not separate unfinished features.
Inspect each checkout's local edits even when committed trees are identical.
If delivery or source disposition remains uncertain, name the missing fact and
continue independent work.

## Remove, verify, and revisit

After delivery or another allowed source disposition is established, confirm
no agent, test, server, review, or later dependency needs the checkout.
An idle child can resume; obtain its release
and stop using that assignment before removal. Check all staged, disk, untracked,
and ignored states. Preserve unfinished source and consolidate useful notes in
the packet. Decide which task artifacts are expired from their contents and
the user's policy; ignored status alone is not a disposal rule.
Closing a checkout does not prove its source was delivered. Dirty and detached
state alone does not prevent removal once source and local changes are accounted for.
Preserve current, primary, shared, locked, and protected worktrees under the
cleanup skill's rules. Run removal from outside the target after resolving and
checking its absolute path.

For ordinary Git worktrees, use the cleanup skill's removal and verification
steps. Verify both directory and registration absence before deleting a branch;
recheck its hash and that no other checkout uses it. Keep a branch after partial
removal. `git worktree prune` cannot replace removal of a live checkout.
Immediately before removal, recheck the exact source and target, local states,
locks, registration, ownership, and access. Use a single `--force` only when
the remaining local contents are fully accounted for under the cleanup policy.

For Codex-managed worktrees, inspect `list_artifacts` and use `archive_worktree`
when available for that exact task attachment. Apply the same source,
local-change, and ownership checks first; a recovery snapshot is not delivery evidence.
Respect native restrictions on current, pinned, shared, or primary worktrees and
do not make an extra archive of expired ignored artifacts. Do not bypass a
blocked archive through manual deletion. Detached work whose source disposition
remains unresolved stays retained.

After each delivery, at phase close, and before finishing, revisit pending entries.
Record verified removals or the specific reason, owner, and condition for retaining
each checkout. Include current integration checkouts that cannot yet be removed.
The parent performs eligible cleanup now rather than only suggesting it.
Reconcile predecessor checkouts when preparing a successor. Do not leave a
blanket instruction to preserve every draft and receipt. A remaining hold needs
an owner, a concrete source/recovery dependency, and a release condition.
