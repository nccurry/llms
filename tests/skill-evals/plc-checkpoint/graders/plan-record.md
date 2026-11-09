# Grader: plan record rules

These are the shared PLC template's rules for updating a plan, as
[`plc-planning`](../../../../skills/plc-planning/references/shared-format.md)
states them. The plc-checkpoint and plc-wrapup cases that may edit a plan
use this grader. When a run edited no plan, record "not applicable".

Compare the packet as the run left it with the fixture's copy: `git diff` for
an uncommitted edit, or `git diff <before>..<after> -- docs/plans/` for a
commit. Every fixture packet's owner is `@alex`.

Pass only if all of these hold:

1. **One Current Work block.** The README has exactly one `## Current Work`,
   directly after the summary under the title. From the packet folder, this
   prints `1`:

   ```sh
   grep -c '^## Current Work' README.md
   ```

   No other section holds a Status, Owner or Last updated line.
2. **Keys kept.** Status, Owner and Last updated come first, in that order,
   and every other template key is there: Next action, Blocker, Depends on,
   Current state and Resume check, followed by the "Where the work lives"
   table. In a finished packet, the line "Historical record as of <commit>;
   the code is the current truth." comes before them, as a plain line or a
   list item; that is valid. The Owner line is unchanged: `- Owner: @alex`. A
   `Depends on`, `Replaces` or `Superseded by` line in the fixture is still
   there. It may gain a note, such as the commit where a dependency landed.
3. **Last updated** starts with the run's date, and names the branch and
   commit it describes.
4. **Phase notes.** A phase whose state changed shows its new state in the
   README `## Phases` table. The state starts with a phase state word from
   `plc-planning`'s Words list. A merge into an integration branch is still
   Implemented; Merged means on the target branch, usually `main`. The note
   after ` — ` names the merge request or commit, as in `Merged — abc1234`.
   No other file gains a phase table with a State or Status column.
5. **Log.** `## Log` is the last section. Lines it had before the run are
   unchanged, and the run added one dated line for each state change,
   decision or surprise, newest last. A gap (see point 7) that nobody had
   named before this update counts as a surprise. A line about a merge names
   its merge request or commit. A merge that leaves a phase's word
   unchanged, such as one that stays In progress, may have its own line but
   needs none. This is the skill's Log rule, and the one these graders use;
   case graders only say what it means for their case.
6. **Phase words.** A phase's parts are what the Parts rule in
   `plc-planning`'s Words list says they are.
   - A phase marked Verified or Live names, after ` — `, the check that
     passed and where it ran, as in
     `Verified — run_tests.py → 3 passed @ abc1234`.
   - A phase whose parts have all merged, but whose checks did not run,
     stays Merged, its note naming the checks still to pass. A check that
     does not exist because its work was never built marks a part not
     started instead.
   - A phase that still holds a part not started (not moved to its own
     row, and not Deferred or Dropped) beside a merged part is In progress.
     Deferred and Dropped parts are left out and named in the note; a
     Blocked part counts as Planned or In progress, as the skill's steps
     say. Its note names each merged part with its merge request or commit,
     and each part not yet merged, as in
     `In progress — record merged @ abc1234; call from save_booking not started`;
     naming the missing part's check is optional. Merged, Planned or
     Verified fails for it.
   - A part moved to its own row leaves its old phase, whose note says
     `moved to P<n>`. The old phase's word then comes from the parts it
     still holds: when all of them have merged, it must be Merged, naming
     the merge commit, or Verified with its evidence. In progress then
     fails.
7. **Gaps recorded.** A gap is a requirement or planned task that the
   shipped code does not meet, although its phase's work has merged, or the
   plan, a report or the user calls it done. Work that the plan, a commit
   message or the user already said is still to be built is not a gap while
   its phase stays In progress: the phase note names it. Each gap becomes a
   new phase row (Planned, or Deferred only with the user's approval) or an
   `Open question:` line naming what it blocks and whom it waits on, as in
   `(blocks P1; waits on @alex)`. A case grader says when its case has a
   gap, or unfinished work that is not one; a grader that says neither has
   no gap. A requirement is never marked met without evidence, and `SRD.md`
   is not edited to match the code.
8. **Format check.** The planning skill's format check passes on the packet
   in strict mode. From the skills repository root, this exits 0 and prints
   nothing:

   ```sh
   python3 skills/plc-planning/scripts/format_check.py --packet <packet folder> --strict
   ```

Fail on any point, and quote the line that breaks it.
