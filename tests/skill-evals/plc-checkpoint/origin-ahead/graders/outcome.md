# Grader: origin ahead of local main

Read the agent's final answer and the checker's `packet_changes`. Pass only if
all of these hold:

1. The agent fetched, or otherwise read `origin/main`, before judging state.
2. SRCH-001 / P1 is reported as merged on `origin/main`, citing the merge
   commit.
3. The answer says local `main` is behind `origin/main`, and that the local
   packet copy still says "In progress".
4. SRCH-002 / P2 is reported as not started.
5. **Tidied:** the worktree `catalog-wt/search/p1-case` is removed, and the
   branch `plc/search-p1` is deleted locally and on `origin`, because its work
   is on `origin/main`. The report lists these removals.
6. **Records:** the newest packet copy is only on `origin/main`, so no local
   copy is edited. The answer says to pull local `main` instead. It does not
   pull, merge, or fast-forward.

Fail if SRCH-001 is reported as in progress or unmerged, if a stale local
packet copy is edited, or if local `main` moved.

Without the skill, record which points the answer covers, for comparison.
