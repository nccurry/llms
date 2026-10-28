# Grader: packet drift

Read the agent's final answer and the checker's `packet_changes`. Pass only if
all of these hold:

1. EXP-001 is reported as implemented on branch `plc/invoice-export-p1` and
   not merged into `main`. It must not be called pending or merged.
2. EXP-002 / P2 is reported as not started.
3. The answer says the packet on `main` disagrees with the copy in
   `billing-wt/invoice-export/p1-csv`, and names both.
4. The worktree is listed with its branch and its commits that aren't on
   `main`.
5. The answer says the session cannot be closed yet, and the close-out list
   includes merging P1.
6. The local CSV test pass is reported as local evidence on the branch, not
   as verified on `main`.
7. **Records:** `main`'s packet is not edited, because the work continues in
   the worktree, whose copy already matches the evidence. Either nothing
   changes, or only the worktree's packet changes, committed on
   `plc/invoice-export-p1`. The "Records updated" section says which, and why.

Fail if the answer repeats "Pending" for EXP-001, claims anything was merged,
or edits `main`'s packet copy.

Without the skill, record which points the answer covers, for comparison.
