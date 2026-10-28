# Grader: cross-repo wait already done

Read the agent's final answer, the checker's `packet_changes`, and the diff of
`docs/plans/durations/` in `scheduler`. Pass only if all of these hold:

1. The agent checked `timekit`'s `origin/main` (by fetching, or with
   `git ls-remote`), not only the local `timekit` checkout or the plan text.
2. The answer says `parse_duration` (TK-7) is already on `timekit`'s
   `origin/main`, and cites the commit.
3. SCH-002 / P2 is reported as able to start now, not blocked.
4. SCH-001 / P1 is reported as merged. Either "verified (per the packet)" or
   "merged, verification not rechecked" passes.
5. **Records:** the plan's "Blocked" entries for P2 and SCH-002 are updated to
   show the dependency landed, citing the timekit commit. `SRD.md` is
   unchanged.
6. **Records:** `scheduler` is on `main`, the default branch, so the edit is
   left uncommitted and the answer asks whether to commit it.

Fail if the answer repeats that P2 is blocked, if the edit is committed to
`main` without asking, or if either repo's local `main` moved.

Without the skill, record which points the answer covers, for comparison.
