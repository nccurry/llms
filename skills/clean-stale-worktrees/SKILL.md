---
name: clean-stale-worktrees
description: Assess and remove stale local branches and worktrees. Reconcile campaigns, delivery, superseded drafts, and local changes; discard expired task artifacts and preserve unfinished source. Use for cleanup or previews.
---

# Clean Stale Worktrees

Use Git and host review tools directly. The agent decides what is delivered,
superseded, disposable, or still needed from the source, PLC packet, history,
and current user instructions. A skill edit, preview, or report stops before
deletion. A cleanup request authorizes eligible local removals within its scope;
do not ask again for an already authorized action.

## Establish the scope and current state

Read applicable repository instructions and user keep requests. Inspect the
registered worktrees, local branches, and current checkout. Fetch the intended
remote target before judging delivery; record its exact ref and commit. Main
is the default unless the user chose another final destination. Local delivery
and a merge into temporary integration do not establish remote main delivery.

Use commands such as:

```sh
git worktree list --porcelain
git branch -vv
git fetch --prune <remote>
git rev-parse <target-ref>
git -C <checkout> status --short --untracked-files=all --ignored
git -C <checkout> diff --cached
git -C <checkout> diff
```

Inspect staged contents and disk files separately, including untracked and
ignored locations that may contain source or useful notes. A restored disk file
can hide a different staged version. Handle unresolved merge stages explicitly.
Respect primary/current/shared checkouts, protected branches, active writers and
processes, locks, and user keep instructions. Release a task-owned checkout and
run removal from outside it. Investigate a lock's owner and purpose; do not
bypass an unresolved lock or access failure.

## Reconcile campaigns before individual checkouts

For a large backlog, group checkouts by feature or campaign and identify the
current integration, its owners, and actual unfinished requirements. Separate
duplicate snapshots, review/rebuild copies, superseded prototypes, and unique
unfinished work. Count campaigns and checkouts separately in the report.

Identical committed trees establish only committed duplication; inspect each
checkout's local states before removal. A shared base or similar name is only
a lead. Compare the branch's own changes, not all differences from a newer main.
Do not merge old stacks just to make cleanup possible.

Trace squash merges, rebases, successor MRs, rewritten implementations, and
current PLC decisions. An unmatched diff hunk may be an old status statement or
an obsolete implementation. It does not establish a new file or unfinished
feature. Conversely, an associated or closed-but-unmerged MR does not prove
delivery. Read [delivery checks](references/delivery-proof.md) when ancestry or
current bytes do not settle the question.

Account for meaningful remaining source changes: delivered to the final target,
retained in a verified successor, superseded by adopted behavior, explicitly
abandoned under the user's instructions, or unresolved. Check post-merge local
commits too. Show concrete reasons for a supersession decision; names, commit
counts, patch IDs, or similar behavior alone are insufficient. Preserve needed
source and unresolved work. If proof is unavailable, report what is missing;
do not call the work unmerged merely because delivery is not yet proven.

## Notes and disposable artifacts

Useful implementation decisions, remaining work, and concise validation
outcomes belong in the committed PLC packet or established project work record.
Do not leave the only useful notes as dirty files in temporary checkouts. Delete
temporary notes when no longer useful. Cleanup permission alone does not
authorize a new push or merge to deliver missing notes.

Decide output retention separately from source retention. In an owned checkout,
remove builds, staging copies, release caches, and experiment output when no
longer needed for active work, even before merge or checkout closure. A failed
source check does not require keeping its build output. Inspect these locations
for unique source and useful notes first; a directory called a cache or an
experiment archive may contain either. Do not remove output in use or shared
caches outside the task's scope. Verify the selected output is gone and source
changes remain intact.

After an MR merges or a checkout closes, task receipts, raw logs, binaries,
caches, and disposable notes may be deleted without an archive or recovery
bundle. Closing means its work is delivered, transferred, or explicitly
abandoned, not merely inactive. An ignore rule or filename alone is not enough:
inspect what would be lost, especially scripts, configuration, and local edits.
Expired artifacts do not need byte matches in main or reconstruction proof.

Apply the user's current policy to old handoffs. An agent's instruction to
preserve every checkout and receipt is not a permanent user keep request.
Retain a checkout only for a concrete source or active recovery dependency,
with an owner and release condition. If particular output is still needed,
name it and its use; keeping a checkout does not keep all its output.
Creating a fresh successor does not renew predecessor holds.

## Remove and verify

Decide checkout removal and branch deletion separately. A verified published
MR or successor can preserve committed work while its local branch remains;
use that route only within the user's chosen cleanup policy. Verify the exact
revision and all local changes before removing the checkout.

Immediately before removal, recheck HEAD, branch and target commits, staged and
disk changes, ownership, locks, registration, and directory access. Reassess
anything that changed. Do not stash, reset, switch branches, or clean files to
manufacture eligibility. Inspect nested repositories/submodules separately and
do not follow cache symlinks outside the checkout.

Use `git worktree remove <path>`. Use a single `--force` only when remaining
local changes are fully understood as delivered, superseded, explicitly
abandoned, or disposable. It must not bypass unknown content, locks, nested
repositories, or permissions. For Codex-managed checkouts, use the native
archive tool when available for the exact task attachment and respect its
restrictions. Its recovery snapshot does not require an extra evidence archive.

After removal, verify both the directory and its Git registration are absent,
including after a failed command. If either remains, stop that candidate,
retain its branch, and report partial removal. Do not manually delete remnants
or prune registration to hide failure. Resolve permission blockers separately.

Before deleting a local branch, recheck its exact commit and ensure no checkout
uses it. Prefer `git branch -d <name>` for history-merged branches. Use `-D` only
after independently confirming delivery or an authorized source disposition;
never escalate a refusal without understanding it. A recovery copy alone is not
proof of delivery. Remote branch deletion needs separate authorization.

Finish by checking registrations, refs, and the original checkout's status.
Report removals, verification, discarded artifacts, campaign-level unfinished
work, and every retained checkout with its owner, concrete reason, and next
action. A command's successful exit alone does not prove cleanup succeeded.
