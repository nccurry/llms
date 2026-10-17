# Cleanup of execution worktrees

Read before creating temporary worktrees and apply after each verified delivery.
The parent owns this work; children release checkouts and supply evidence.

## Record ownership and the destination

Use the existing work list to record each temporary checkout's absolute path,
branch and source commit, owner, purpose, final target ref/hash, and cleanup state.
Include integration, repair, replaced-child, and combined-verification checkouts.
Record the source of any user keep instruction. Keep needed logs and artifacts
outside a checkout before removing it.

Use main, or the repository's equivalent final branch, unless the user chose
another final destination. A temporary integration branch is not that destination
merely because children merge into it. If the user explicitly accepts delivery
into another branch, prove delivery to that exact ref and preserve any checkout
still needed for further integration. Use a local ref only for an authorized
local destination; remote delivery requires the actual remote result.

## Investigate delivery before removal

Read and follow [clean-stale-worktrees](../../clean-stale-worktrees/SKILL.md).
Use its script and complete proof sequence, not only `git branch --merged`,
an ancestry check, a PR title, or a child's report. Inspect current source,
history, and host review evidence as needed. A squash or rebase can deliver work
without preserving child commit ancestry. Account for every change, including
merge resolutions and commits added after the merged source.

Select only task-owned candidates with repeatable `--branch` and `--worktree`
arguments. The default target follows the cleanup skill's main-ref selection:

```text
python <cleanup-skill>/scripts/stale_worktree_preflight.py --path <safe-checkout> --fetch --branch <child-branch>
```

For an explicitly chosen local final destination, use
`--target-ref refs/heads/<target>`; for an explicit remote destination, use
`--target-ref refs/remotes/<remote>/<target>` with the matching `--remote`.
Inspect `baseRef`, `mainHash`, the source hash, every proof attempt, and protection
results. These legacy main fields describe the selected target. Never substitute
a temporary branch just to obtain a successful proof. Missing evidence retains
the checkout as **delivery not yet proven**; continue safe independent work.

## Remove, verify, and revisit

After required delivery checks pass, confirm no agent, test, server, review, or
later dependency needs the checkout. An idle child can resume; obtain its release
and stop using that assignment before removal. Preserve needed modified,
untracked, and ignored files. Preserve current, primary, shared, locked, and
protected worktrees under the cleanup skill's rules. Run removal from outside
the target after resolving and checking its absolute path.

For ordinary Git worktrees, use the cleanup skill's removal and verification
steps. Verify both directory and registration absence before deleting a branch;
recheck its hash and that no other checkout uses it. Keep a branch after partial
removal. `git worktree prune` cannot replace removal of a live checkout.

For Codex-managed worktrees, inspect `list_artifacts` and use `archive_worktree`
when available for that exact task attachment. Require the same delivery proof
and preservation checks first; a recovery snapshot is not delivery evidence.
Respect native restrictions on current, pinned, shared, or primary worktrees and
preserve needed ignored files separately. Do not bypass a blocked archive through
manual deletion. Detached work without complete source proof stays retained.

After each delivery, at phase close, and before finishing, revisit pending entries.
Record verified removals or the specific reason, owner, and condition for retaining
each checkout. Include current integration checkouts that cannot yet be removed.
The parent performs eligible cleanup now rather than only suggesting it.
