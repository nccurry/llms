# Grader: morning refresh

Read the agent's final answer, the checker's `tidied` and `packet_changes`,
and the packet on `plc/reconcile`. Pass only if all of these hold:

1. The answer starts from the last Current Work (as of the integration
   branch's first commit) and says what changed since: P1 merged into
   `plc/reconcile`.
2. P1 / REC-001 is reported as merged into the integration branch, not into
   `main`. P2 / REC-002 is in progress with one work-in-progress commit.
3. The next step is concrete: finish P2 in `ledger-wt/reconcile/p2-report`.
4. **Current Work rewritten:** the packet's Current Work block on
   `plc/reconcile` shows P1 merged into integration, a new "Last updated"
   pointing at the current integration commit, and the `p1-match` row gone
   or marked removed. The change is committed on `plc/reconcile` and touches
   only `docs/plans/`.
5. **Owner and links survive the rewrite:** `- Owner: @alex`,
   `- Depends on: None` and the `- Replaces:` line naming
   `docs/plans/archived/bank-match/` are still in the block, unchanged.
6. **Phase and Log:** P1's row in `## Phases` reads `Merged` (its target is
   the integration branch) or `Implemented`, and its note names
   `plc/reconcile` and the merge commit. It reads Verified only if the note
   also names the check that passed and where it ran. The two existing Log
   lines are unchanged, and a new dated line at the end records P1's change.
7. **Tidied:** the `p1-match` worktree is removed and branch
   `plc/reconcile-p1` deleted. The `integration` and `p2-report` worktrees and
   their branches remain. The report lists what was removed and what was kept.
8. Nothing merged into `main`.

Fail if P1 is called merged into `main`, if Current Work keeps yesterday's
"Last updated" or loses its Owner or Replaces line, if no Log line is added,
or if P2's checkout is touched.
