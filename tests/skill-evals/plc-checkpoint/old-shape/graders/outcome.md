# Grader: packet in an older shape

The packet in `marina/docs/plans/audit-log/` predates the shared template. Its
README has a `## Status` section with a bare `Status: In progress` line and
older key names, and its summary sits under `## Summary`. Phase state lives in
a Phase Status table in `IMPLEMENTATION_PLAN.md`, and there is no `## Log`.
P1 merged into `main` after that status was written.

Read the agent's final answer, the checker's report, and the packet as the
run left it. Pass only if all of these hold:

1. **Moved first.** The answer says the packet was in an older shape and was
   moved to the shared template before its status was updated. The Log shows
   the move before the P1 update.
2. **One Current Work.** Run these from `marina/`:

   ```sh
   grep -c '^## Current Work' docs/plans/audit-log/README.md   # prints 1
   grep -c '^## Status' docs/plans/audit-log/README.md         # prints 0
   ```

   The `## Current Work` block sits directly after the summary under the
   title, and starts with Status, Owner and Last updated, in that order. The
   bare `Status:` line became `- Status:`; `Updated` became `Last updated`,
   `Next step` became `Next action`, `Blockers` became `Blocker`, and
   `Current phase` became `Current state`. The `Folder:` line is gone. Owner
   is still `@alex`.
3. **Summary.** The first summary paragraph ("Record who changed each berth
   booking ...") sits directly under the title. The second paragraph may stay
   under `## Summary`.
4. **Phases.** The README has a `## Phases` table with the rows from the old
   Phase Status table. `IMPLEMENTATION_PLAN.md` no longer has a phase table
   with a State or Status column, or its `Lifecycle status:` line. Its P1 and
   P2 detail sections stay.
5. **Log.** `## Log` is the last section. Its first line comes from
   `Created: 2026-10-20`. Next is a dated line for the move to the shared
   template (format only), then a dated line for P1's change that names the
   merge commit.
6. **Status update.** P1's row shows it merged into `main` and names the merge
   commit. It is Verified only if its note names the check that passed and
   where it ran. P2 is Planned, or keeps the older word `Not started`. Last
   updated has the run's date and the current `main` commit.
7. **Format edits only.** Apart from the status update, the move only moves
   lines and renames keys. No requirement or plan text is reworded, and
   `SRD.md` is unchanged.
8. **Tidied:** the `p1-record` worktree is removed and the branch
   `plc/audit-log-p1` deleted, as the checker requires.

Committing the packet on `main` and leaving it uncommitted both pass here;
the dirty-finished and chat-decision cases grade that rule.

When the planning skill's format check is available, it must agree. From the
skills repository root:

```sh
python skills/plc-planning/scripts/format_check.py --packet <dest>/marina/docs/plans/audit-log --strict
```

It must exit 0 and print nothing.

Fail if the README ends with two status blocks (such as `## Status` and
`## Current Work`), if the Phase Status table stays in the implementation
plan, or if the status is updated without moving the packet.
