# Grader: packet in an older shape

The packet in `marina/docs/plans/audit-log/` predates the shared template. Its
README has a `## Status` section with a bare `Status: In progress` line and
older key names, and its summary sits under `## Summary`. Phase state lives in
a Phase Status table in `IMPLEMENTATION_PLAN.md`, and there is no `## Log`.
P1 merged into `main` after that status was written.

The run must first convert the packet to the shared template, following
`plc-planning`'s old-packet migration reference, and then update its status.
Converting changes only the format: it moves lines and renames keys. "Move"
below means moving lines within the packet; the packet folder itself stays
where it is.

Read the agent's final answer, the checker's report, and the packet as the
run left it. Pass only if all of these hold:

1. **Converted first.** The answer says the packet was in an older shape and
   was converted to the shared template before its status was updated. The
   Log shows the conversion before the P1 update.
2. **One Current Work.** Run these from `marina/`:

   ```sh
   grep -c '^## Current Work' docs/plans/audit-log/README.md   # prints 1
   grep -c '^## Status' docs/plans/audit-log/README.md         # prints 0
   ```

   The `## Current Work` block sits directly after the summary under the
   title, and starts with Status, Owner and Last updated, in that order. The
   bare `Status:` line became `- Status:`; `Updated` became `Last updated`,
   `Next step` became `Next action`, `Blockers` became `Blocker`, and
   `Current phase` became `Current state`. A renamed key keeps its value:
   `- Blocker: none` stays `none`. The `Folder:` line is gone. Owner is still
   `@alex`.
3. **Summary.** The first summary paragraph ("Record who changed each berth
   booking ...") sits directly under the title. The second paragraph may stay
   under `## Summary`.
4. **Phases.** The README has a `## Phases` table with the rows from the old
   Phase Status table. `IMPLEMENTATION_PLAN.md` no longer has a phase table
   with a State or Status column, or its `Lifecycle status:` line. Its P1 and
   P2 detail sections stay.
5. **Log.** `## Log` is the last section. Its first line comes from
   `Created: 2026-10-20`. Next is the conversion line the migration reference
   gives, `- <date> Converted to the shared PLC template (format only).`, then
   one dated line for P1's state change that names the merge commit.
6. **Status update.** These changes count as the status update, not the
   conversion: new values for Last updated (the run's date and the current
   `main` commit), Next action and Current state; every template key the old
   block lacked, which here means `Depends on` and `Resume check`; the "Where
   the work lives" table; P1's row; and the Log line for P1. All of these
   must be there at the end. P1's row shows it merged into
   `main` and names the merge commit. It is Verified only if its note names
   the check that passed and where it ran. P2 is Planned, or keeps the older
   word `Not started`.
7. **Format edits only.** Apart from the status update, the conversion only
   moves lines and renames keys. No requirement or plan text is reworded, and
   `SRD.md` is unchanged.
8. **Tidied:** the `p1-record` worktree is removed and the branch
   `plc/audit-log-p1` deleted, as the checker requires.
9. **Format check.** From the skills repository root, this exits 0 and prints
   nothing:

   ```sh
   python3 skills/plc-planning/scripts/format_check.py --packet <dest>/marina/docs/plans/audit-log --strict
   ```

Committing the packet on `main` and leaving it uncommitted both pass here;
the dirty-finished and chat-decision cases grade that rule.

Fail if the README ends with two status blocks (such as `## Status` and
`## Current Work`), if the Phase Status table stays in the implementation
plan, or if the status is updated without converting the packet.
