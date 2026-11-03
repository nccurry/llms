# Grader: plan record rules

These are the shared PLC template's rules for updating a plan. The
plc-checkpoint and wrap-this-up cases that may edit a plan use this grader.
When a run edited no plan, record "not applicable".

Compare the packet as the run left it with the fixture's copy: `git diff` for
an uncommitted edit, or `git diff <before>..<after> -- docs/plans/` for a
commit. Every fixture packet's owner is `@alex`.

Pass only if all of these hold:

1. **One Current Work block.** The README has exactly one `## Current Work`,
   directly after the summary under the title. `grep -c '^## Current Work'
   README.md` prints `1`. No other section holds a Status, Owner or Last
   updated line.
2. **Keys kept.** Status, Owner and Last updated come first, in that order.
   The Owner line is unchanged: `- Owner: @alex`. A `Depends on`, `Replaces`
   or `Superseded by` line in the fixture is still there. It may gain a note,
   such as the commit where a dependency landed.
3. **Last updated** starts with the run's date, and names the branch and
   commit it describes.
4. **Phase notes.** A phase whose state changed shows its new state in the
   README `## Phases` table. The state starts with one of these words:
   Planned, In progress, Implemented, Merged, Verified, Live, Blocked,
   Deferred or Dropped. The note after ` — ` names the merge request or
   commit, as in `Merged — abc1234`. No other file gains a phase table with a
   State or Status column.
5. **Log.** `## Log` is the last section. Lines it had before the run are
   unchanged, and the run added one dated line for each state change or
   decision it recorded, newest last.
6. **Evidence for Verified.** A phase marked Verified or Live names, after
   ` — `, the check that passed and where it ran, as in
   `Verified — run_tests.py → 3 passed @ abc1234`. A merged phase whose check
   did not run, or does not exist yet, stays Merged, with what is missing in
   its note.
7. **Gaps recorded.** When the shipped code does not meet a requirement, the
   gap becomes a new phase row, a Deferred phase, or an `Open question:` line
   that names whom it waits on. It is never ticked off silently, and
   `SRD.md` is not edited to match the code.

Fail on any point, and quote the line that breaks it.

When the planning skill's format check is available, run it on the packet
from the skills repository root. It must exit 0 and print nothing:

```sh
python skills/plc-planning/scripts/format_check.py --packet <packet folder> --strict
```
