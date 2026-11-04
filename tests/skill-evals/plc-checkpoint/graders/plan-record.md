# Grader: plan record rules

These are the shared PLC template's rules for updating a plan, as
[`plc-planning`](../../../../skills/plc-planning/SKILL.md#shared-template)
states them. The plc-checkpoint and wrap-this-up cases that may edit a plan
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
2. **Keys kept.** Status, Owner and Last updated come first, in that order.
   In a finished packet, the plain line "Historical record as of <commit>;
   the code is the current truth." comes before them; that is valid. The
   Owner line is unchanged: `- Owner: @alex`. A `Depends on`, `Replaces` or
   `Superseded by` line in the fixture is still there. It may gain a note,
   such as the commit where a dependency landed.
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
   decision or surprise, newest last.
6. **Evidence for Verified.** A phase marked Verified or Live names, after
   ` — `, the check that passed and where it ran, as in
   `Verified — run_tests.py → 3 passed @ abc1234`. A merged phase whose check
   did not run, or does not exist yet, stays Merged, with what is missing in
   its note.
7. **Gaps recorded.** When the shipped code does not meet a requirement, the
   gap becomes a new phase row (Planned, or Deferred only with the user's
   approval) or an `Open question:` line naming whom it waits on. A
   requirement is never marked met without evidence, and `SRD.md` is not
   edited to match the code.
8. **Format check.** The planning skill's format check passes on the packet
   in strict mode. From the skills repository root, this exits 0 and prints
   nothing:

   ```sh
   python3 skills/plc-planning/scripts/format_check.py --packet <packet folder> --strict
   ```

Fail on any point, and quote the line that breaks it.
