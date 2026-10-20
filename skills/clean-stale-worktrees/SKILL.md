---
name: clean-stale-worktrees
description: Remove local branches and worktrees, including detached or dirty checkouts, after proving their committed and local content reached main. Use for stale-work cleanup or previews. Preserve work absent from main and unresolved evidence.
---

# Clean Stale Worktrees

Remove only local work whose delivery is proven and whose removal checks pass.
A request to edit this skill does not authorize repository cleanup.
Dirty status or detached HEAD alone does not justify retention. Anything absent
from main stays; do not discard files because they look like garbage.

## Rules that govern deletion

- Start cleanup when the user requests it or an explicitly invoked execution
  workflow authorizes cleanup of its own temporary local work. Honor user keep
  instructions. A preview, report, or skill edit stops before deletion.
- Preserve primary and current worktrees, current and protected branches, locked
  and bare worktrees, active users/processes, and explicit keep instructions.
  Release an auxiliary checkout and run cleanup outside it before reconsidering it.
- Unreadable status or incomplete content proof blocks deletion. Review metadata
  supplies evidence when needed; an open review or unavailable lookup does not
  invalidate a complete independent Git proof. Check actual users/processes separately.
- Never stash, reset, switch branches, overwrite work, remove remote refs, unlock
  worktrees. Use a single `git worktree remove --force` only for an eligible dirty
  candidate with fresh complete local-content proof. Never use force to bypass
  missing evidence, locks, nested repositories, or access failures.
- A failed content check against current main must trigger historical-main and
  verified merged-source checks automatically. Continue until every branch
  change is accounted for or a concrete unmatched change is identified. Similar
  names, partial matches, and patch IDs alone are insufficient evidence for deletion.
- Investigate actual delivery; do not stop at failed ancestry or label a squash
  merge unmerged because commit IDs differ. Account for the exact current tip,
  including changes made after the reviewed or merged source.
- If required history, objects, permissions, or review access are unavailable,
  keep the work and state the missing evidence. Report **delivery not yet proven**,
  not “unmerged.” Failure to prove delivery does not prove it never happened.

## Preflight and delivery proof

Resolve script paths relative to this skill directory. Requires
[uv](https://docs.astral.sh/uv/) and Git; uv supplies a suitable Python, and no
Python packages are needed. Review lookup uses existing `gh` or `glab`
authentication. Read [delivery-check details](references/delivery-proof.md) when
evaluating content or review evidence, a failed check, or an unsupported host.

```sh
uv run --script <skill-dir>/scripts/stale_worktree_preflight.py --path . --fetch
```

Always launch the script with `uv run --script`, not `python` or `python3`, so
the same command works on every platform. If `uv --version` fails, ask the user
before installing it, then use the first command that fits the platform:

- Windows: `winget install --id astral-sh.uv -e`
- macOS: `brew install uv`
- Linux or any other platform: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Open a new shell or add the installer's bin directory (usually `~/.local/bin`)
to `PATH`, then confirm with `uv --version`. If the user declines or installation
fails, keep all work and report that preflight could not run because uv is
missing. Never run the script's checks by hand as a substitute.

Use `--main <branch>` and `--remote <remote>` when needed to select the intended
main ref. Inspect `baseRef` before accepting candidates. Use repeatable
`--keep <branch>` arguments for work the user wants preserved. The script fetches
only when `--fetch` is supplied; it never pulls or switches branches. With no
selectors, inspect every local branch and registered worktree in the repository.

For execution cleanup, use repeatable `--branch <name>` and/or
`--worktree <absolute-path>` arguments to select only the workflow's candidates.
They form a union; selecting a worktree also checks its branch. Unselected work
does not become a cleanup candidate and its delivery is not scanned. `--keep`
protects deletion but does not narrow scanning. Unknown selections stop preflight.

Main remains the default delivery destination. When the user explicitly chose a
different final destination, use `--target-ref refs/heads/<branch>` for a local
target or `--target-ref refs/remotes/<remote>/<branch>` with matching `--remote`
for a remote target. This is an alternative to `--main`; inspect `baseRef` and
`mainHash`, which describe the selected target. A temporary staging merge alone
does not prove delivery to main. Keep the final destination explicit in the report.

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

Detached worktrees use the same proof checks against their exact HEAD commit.
For every eligible checkout, `localContentCheck` separately checks the index,
working files, and untracked/ignored files. Each changed state must match main
or a verified main snapshot after the source's delivery. A staged version hidden
by a later unstaged edit still needs proof. Check complete bytes, file types,
and applicable Git modes; a filename, ignore rule, or age is not evidence.
`unmatched` names the exact paths and layers that must remain. Ordinary unchanged
files are covered by committed-source proof. The script does not stage local
files, commit them, or write their contents into Git objects.

Read the reasons and evidence, not just the method name. Failed checks must not
be turned into a successful result by hand. If the script is missing or fails,
keep affected work. Resolve missing evidence and rerun the preflight.

## Removal readiness

Delivery proof and permission to remove a worktree are separate decisions.
Only entries in `cleanupCandidates` have passed both applicable sets of checks.

Before removing any candidate:

- Confirm all agents and processes have released it. Require both committed-source
  and `localContentCheck.confirmed` proof, including untracked and ignored files.
  Preserve unique content; being ignored or apparently temporary does not waive proof.
- Inspect `removalReadiness`: it includes ignored directories, directory access
  checks, ownership, and blocking paths. Read-only ignored Bazel/build caches must
  be identified before removal begins. Read-only files alone do not prevent unlinking.
- Do not follow cache symlinks into external directories. Preserve nested
  repositories/submodules for separate review. Permission checks cannot guarantee
  removal: ACLs, immutable flags, mounts, and concurrent changes can still block it.
- If a directory is blocked, keep the worktree and branch and report its path.
  Do not silently change permissions, use elevated deletion, or delete it manually.
- Immediately before each removal, rerun the selected preflight. Require the same
  source/main hashes and `localContentCheck.fingerprint`, renewed confirmation,
  registration, lock/release state, and directory access. The fingerprint covers
  HEAD, the real index, and raw working-file hashes, including ignored files.
  Any changed source, index, file, or protection invalidates the earlier proof.

## Remove and verify

Change to the primary worktree or another safe directory outside the target.
For each confirmed candidate, run:

```sh
git worktree remove <worktree-path>
uv run --script <skill-dir>/scripts/stale_worktree_preflight.py --path <safe-worktree> --verify-removed <worktree-path>
```

If the freshly confirmed candidate has `requiresForce: true`, use
`git worktree remove --force <worktree-path>` instead. Dirty-but-delivered content
is eligible; unknown content is not. For Codex-managed checkouts, use the native
archive capability when available and respect its restrictions after the same
delivery and local-content checks.

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
