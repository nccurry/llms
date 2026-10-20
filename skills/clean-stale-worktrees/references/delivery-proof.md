# Delivery checks

Use the checks that resolve the candidate's actual uncertainty. These are
investigation methods, not a required script or a fixed search sequence. Keep
the final target, source revision, and current user policy explicit.

## Fix the comparison

Fetch the intended remote and resolve its actual main/master or user-selected
target ref. A cached remote HEAD or stale local main may name the wrong target.
Record the source tip and target commit so later changes are visible.

Compare the branch's own changes from its established fork point. A diff of an
old checkout against current main also includes later main work that was never
part of that branch. Unique commit counts do not measure unfinished features.

For a large campaign, find its current integration and successor MRs first.
Shared tree IDs help locate repeated committed snapshots; local index, disk,
untracked, and ignored states still need inspection in every checkout.

## History, squash merges, and later rewrites

Ancestry in the final target is straightforward delivery evidence. If ancestry
fails, inspect the actual MR and source/integration commits, main history, and
the affected source. A squash or rebase changes commit IDs without necessarily
leaving work undelivered. Later edits can also defeat a current-byte comparison.

Check the complete relevant change, including binaries, modes, deletions, and
merge resolutions. Historical main snapshots and verified merged source trees
can establish delivery before a later edit. Stable patch IDs and matching
fragments help find candidates but are not complete proof. Distinguish an old
delivered occurrence from a new change made after it was reverted.

Use available authenticated GitHub/GitLab tools for exact MR state, revisions,
target, and merge results when needed. A title, source branch name, or MR link
does not prove the local tip was included. Check commits added after the merged
source separately. Continue with independent Git evidence if review lookup is
unavailable; state missing facts rather than inventing an MR result.

When useful for a squash, inspect the integration parent and source with
`git merge-tree --write-tree <integration-parent> <source>` and compare its
conflict-free tree with the actual squash tree. This is one available check,
not a reason to reconstruct every historical draft before making a decision.

A successor may implement the same accepted requirement through different
source. Inspect that implementation, its tests and adopted PLC decisions, then
identify any still-useful delta in the old branch. Old ledger wording, failed
prototypes, and temporary diagnostics do not all need to reach main. Record
why a change is superseded or abandoned; preserve source whose disposition
remains uncertain. A closed-but-unmerged MR alone does not settle that question.

## Local states and notes

Review `git diff --cached` and `git diff` separately. Inspect untracked files,
ignored locations, and unresolved index stages as well. Do not treat a clean
ordinary status as proof that a checkout contains no local work. Read symlink
targets without following them; inspect embedded repositories separately.

Decide what each difference means. Useful notes belong in the committed PLC
packet. Raw receipts and generated artifacts may be discarded after merge or
checkout closure without matching them to main, preserving their exact test
executables, or building an archive. An ignored source edit or capture helper
does not become disposable just because it sits beside test output.

An obsolete planning snapshot may be reconciled with the current packet rather
than merged back. Verify that unfinished requirements and useful decisions
remain recorded before discarding it. Closing a checkout does not authorize
silently abandoning unique source or publishing missing notes.

## Removal checks

Confirm agents and processes have released the exact checkout. Check write and
search access to directories, ownership, nested repositories, and symlinks;
read-only build directories can block removal even when source is delivered.
Read-only files alone do not prevent unlinking. Do not change permissions or
use elevated deletion merely to force a cleanup result.

Recheck source, target, local states, registration, locks, and ownership just
before acting. Concurrent changes invalidate an earlier decision. Remove from
outside the checkout, then inspect the filesystem and `git worktree list`
independently. Delete a branch only after checking its current commit and use
by all remaining checkouts; verify the ref is absent afterward.
