# Grader: an approved contract grows the plan

`tides/docs/plans/in-progress/plc-tide-cache.md` is a one-file plan in the
shared template. Its P1, the feed cache, is merged and Verified, and its one
requirement, TIDE-001, is internal. In the conversation, the user approved a
new public CLI flag, `tides show --max-age SECONDS`, with its error
behavior. A new flag is a public contract, so `plc-planning`'s Adding files
rule calls for SRD.md, and its Growing a packet rule says how to add it.

Run `check_state.py`, then read the packet as the run left it and the
agent's final answer. Pass only if all of these hold:

1. **A folder now.** The checker prints `"ok": true`. Besides the usual
   state rules, it checks the move, parts of points 2 to 4, and point 7:
   the plan is now `docs/plans/in-progress/tide-cache/README.md`, in the
   same lifecycle folder, and `plc-tide-cache.md` is gone, not left beside
   the folder.
2. **SRD.md.** `tide-cache/SRD.md` starts from the default packet's SRD.md,
   with the sections that do not apply deleted. Its requirements table,
   `| ID | Priority | Requirement | Check |`, holds TIDE-001 moved with its
   ID, text and check unchanged, with Priority `Must`. The flag is in one or
   more new requirements with the next IDs, starting at TIDE-002, whose
   row names `--max-age`: together they say the default is 60 seconds,
   `--max-age 0` turns the cache off, and a bad value exits with status 2
   and `tides: --max-age must be 0 or more seconds`. Each new requirement
   has its own check, a command or test with its expected result. As a
   public contract, the flag also has its definition, including the error
   for a bad value, in Public Contracts; a row in User Experience And
   Public Surface; and examples in Expected Experience.
3. **Done when.** `## Done when` sits directly after `## Phases` and holds
   only `The requirements and their checks are in [SRD.md](SRD.md).` No
   requirement is left there.
4. **Log.** After the existing lines, which are unchanged, the run added a
   dated `Decision:` line for the approved flag, and a dated line that
   names SRD.md and why it was added, such as
   `- <date> Added SRD.md: the new --max-age flag is a public contract.`
5. **Phases.** The flag is new work the user approved, not a gap. Either
   of these passes: a new phase row, P2, Planned (not Deferred: the user
   will build it tomorrow), holding the new requirements, with P1 still
   Verified with its evidence; or the new requirements added to P1, with
   P1 back to In progress and a note naming them as not started, such as
   `In progress — cache verified @ <commit>; TIDE-002 not started`, as
   `plc-planning`'s Words rules say for a phase whose parts differ. P1
   left Verified while it holds TIDE-002 fails.
6. **Current Work.** Last updated has the run's date, `main` and its
   commit. Status stays In progress, and the plan stays in `in-progress/`.
   Next action is a first step for the flag, such as a failing test for
   `--max-age -1`, not "wrap up".
7. **Format check.** The checker runs the planning skill's format check in
   strict mode; by hand, from the skills repository root, this exits 0 and
   prints nothing:

   ```sh
   python3 skills/plc-planning/scripts/format_check.py --packet <dest>/tides/docs/plans/in-progress/tide-cache --strict
   ```

8. **Records.** `tides` is on `main`, the default branch, and nothing says
   plan updates go there, so the edit is left uncommitted and the answer
   asks whether to commit it. The rename `git mv` staged is fine. No code
   changes: the flag is not built.
9. **Review.** The flag is added scope, so the agent ran
   `review-and-fix-plc` on it, naming the change, or said that subagents
   were unavailable. Fixes from that review are fine if points 1 to 7 still
   hold.
10. The answer reports P1 as done and verified, names TIDE-002 and its
   phase, and says the plan became a folder with SRD.md because the flag is
   a public contract.

Fail if the new requirement lives only in a Log line or the README, if the
plan stays one file, or if a requirement ID is in both `## Done when` and
SRD.md.

Without the skill, record which points the answer covers, for comparison.
