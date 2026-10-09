---
name: clean-stale-worktrees
description: Safely remove completed local Git branches and linked worktrees after proving delivery to main through history, historical content, verified squash sources, or exact cherry-picked changes. Use for requests to clean stale branches, remove merged worktrees, or preview completed local work. Preserve active, changed, and unresolved work.
---

# Clean Stale Worktrees

Remove only local work whose delivery is proven and whose removal checks pass.
A request to edit this skill does not authorize repository cleanup.

## Rules that govern deletion

- Start cleanup only when the user requests it. A preview or report stops before deletion.
- Preserve primary and current worktrees, current and protected branches, dirty,
  locked, detached, bare, and open-MR/PR worktrees. Preserve branches on a keep list.
- An unreadable status or unavailable open-review lookup blocks deletion. Unknown
  is never clean, closed, or delivered.
- Never stash, reset, switch branches, overwrite work, remove remote refs, unlock
  worktrees, or add `--force` to make cleanup possible.
- A failed content check against current main must trigger historical-main and
  verified merged-source checks automatically. Continue until every branch
  change is accounted for or a concrete unmatched change is identified. Similar
  names, partial matches, and patch IDs alone are insufficient evidence for deletion.
- If required history, objects, permissions, or review access are unavailable,
  keep the work and state the missing evidence. Report **delivery not yet proven**,
  not “unmerged.” Failure to prove delivery does not prove it never happened.

## Preflight and delivery proof

Resolve script paths relative to this skill directory. Requires Python 3 and Git;
review lookup uses existing `gh` or `glab` authentication. No Python packages are
needed. Read [delivery-check details](references/delivery-proof.md) when evaluating
content or review evidence, a failed check, or an unsupported host.

```sh
python3 <skill-dir>/scripts/stale_worktree_preflight.py --path . --fetch
```

Use `--main <branch>` and `--remote <remote>` when needed to select the intended
main ref. Inspect `baseRef` before accepting candidates. Use repeatable
`--keep <branch>` arguments for work the user wants preserved. The script fetches
only when `--fetch` is supplied; it never pulls or switches branches.

The script records branch and main hashes, review lookup results, delivery checks,
worktree protections, and removal readiness. It checks delivery in this order:

1. Current main: ancestry, then the complete net patch since the fork point.
2. Historical main: the same complete patch against earlier snapshots, with
   ancestry proof connecting a matching snapshot to current main.
3. Merged sources: source and squash hashes from merged reviews, squash ancestry
   in main, and exact equality between the reproduced integration tree and squash
   tree. Account separately for local changes beyond the verified source.
4. Cherry-picks: patch IDs find candidates; exact changed bytes and file metadata
   prove matches. Account for every unique change, repeated change, merge
   resolution, and post-merge commit. Keep concrete unmatched changes.

Proof methods are `commitHistory`, `contentMatch`, `historicalMain`, `mergedSource`,
`exactChanges`, and `noFileChanges`. `deliveryNotProven` never permits deletion.
No net file change is a separate result; it does not mean every commit was empty.

Read the reasons and evidence, not just the method name. Failed checks must not
be turned into a successful result by hand. If the script is missing or fails,
keep affected work. Resolve missing evidence and rerun the preflight.

## Removal readiness

Delivery proof and permission to remove a worktree are separate decisions.
Only entries in `cleanupCandidates` have passed both applicable sets of checks.

Before removing any candidate:

- Inspect `removalReadiness`: it includes ignored directories, directory access
  checks, ownership, and blocking paths. Read-only ignored Bazel/build caches must
  be identified before removal begins. Read-only files alone do not prevent unlinking.
- Do not follow cache symlinks into external directories. Preserve nested
  repositories/submodules for separate review. Permission checks cannot guarantee
  removal: ACLs, immutable flags, mounts, and concurrent changes can still block it.
- If a directory is blocked, keep the worktree and branch and report its path.
  Do not silently change permissions, use elevated deletion, or delete it manually.
- Immediately before each removal, recheck its branch hash and main hash against
  the report, its clean status including untracked files/submodules, its lock and
  review status, its registration, and directory access. If a hash or protection
  changed, rerun preflight. Do not reuse earlier proof for a changed branch.

## Remove and verify

Change to the primary worktree or another safe directory outside the target.
For each confirmed candidate, run:

```sh
git worktree remove <worktree-path>
python3 <skill-dir>/scripts/stale_worktree_preflight.py --path <safe-worktree> --verify-removed <worktree-path>
```

Verification must report `removed: true`: **both the directory and its Git
registration must be absent**. Check after a failed removal command too. If either
remains, stop that candidate, retain its branch, and report partial removal.
Do not manually delete directories or prune registration to hide a failure.

Before deleting a branch, verify its recorded hash again and confirm it is no
longer checked out anywhere. Use its preflight `deleteCommand`:

```sh
git branch -d <branch-name> # commitHistory only
git branch -D <branch-name> # other confirmed proof methods only
```

Use `-D` only with current, complete evidence and no protections. If `-d` refuses,
keep the branch; do not substitute `-D`. A non-history proof allows `-D` only after
successful worktree removal verification, when applicable.

Prune stale metadata only after successful removals or separately verified
missing paths. Preserve locked registrations. Never use prune to finish a failed
removal. Finally check `git worktree list --porcelain -z`, branch refs, and current
worktree status. Confirm deleted refs are absent and user work is unchanged.

## Report

State the selected main ref and hash, whether fetch ran, evidence for each
confirmed branch, directories and branches removed, and both removal verification
results. List preserved work with protections, blocking paths, concrete unmatched
changes, or missing evidence. Distinguish “delivered but removal blocked” from
“delivery not yet proven.” Do not claim cleanup succeeded from command exit status alone.
