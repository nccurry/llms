# Check cleanup after delivery or handoff

Use this check for the assignment or campaign in scope after accepting work,
after verifying a merge, and when resuming or replacing work. Use Git and the
existing plan's Current Work block, work list, or handoff to track the work.

1. **Find what is pending.** Match recorded paths and local branches against
   Git, including detached checkouts and branches with no checkout. Read each
   named PR or MR and check its target and source revision. Check later local
   commits separately. Recheck who or what uses each held checkout and whether
   its release condition has been met.
2. **Act on each eligible item.** Follow the
   [cleanup rules](../SKILL.md) for delivery, successor proof, local changes
   (including ignored files), active users, and access failures. Release
   satisfied task-owned holds and remove eligible checkouts. Decide branch
   deletion separately. Use the caller's authorization for any remote change.
3. **Verify and record the result.** From a remaining checkout of the same
   repository, run the report helper with Python 3.10 or later. Use the exact
   absolute path from Git's worktree listing and the short local branch name. Set
   `cleanup_skill_dir` to the directory containing `clean-stale-worktrees/SKILL.md`.

   ```sh
   python3 "$cleanup_skill_dir/scripts/worktree_report.py" \
     --path "<remaining checkout>" --removed-checkout "<removed checkout>"
   ```

   Verify the checkout before deleting its branch. For a branch already
   deleted, use `--removed-branch "<local branch>"`. Repeat either flag to
   check several removals. The command prints JSON and exits nonzero if
   anything remains or Git cannot be read. It makes no removals. Without
   Python, check the directory, `git worktree list --porcelain`, and
   `git show-ref --verify refs/heads/<branch>` directly.

Record verified removals and carry forward what is still pending, even if
delivery succeeded. For each pending item, keep its exact path or branch,
source commit, owner, and the next check or release condition. For delivery
pending on a review, also record the PR or MR and target. For example:

- Checkout removed. Local branch `alice/collector` at `<source SHA>` is
  pending. Alice will check MR !42 against `origin/main` on resume.
- Checkout held. The staged edits are in the successor, but the patch in
  `target/qualification/source.patch` still needs the owner's review.

Use the same work record on resume. If there is no plan, include pending
entries in the handoff for the next session.
