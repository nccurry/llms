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
   `| ID | Priority | Requirement | Check |`, holds TIDE-001 with its check,
   meaning unchanged, and a new requirement with the next ID, TIDE-002, for
   `--max-age`: the default of 60 seconds, `--max-age 0` turning the cache
   off, and the error, exit status 2 with
   `tides: --max-age must be 0 or more seconds`. Its check names a command
   or test and its expected result. The flag is also in SRD.md's public
   surface or expected experience section.
3. **Done when.** `## Done when` sits directly after `## Phases` and holds
   only `The requirements and their checks are in [SRD.md](SRD.md).` No
   requirement is left there.
4. **Log.** After the existing lines, which are unchanged, the run added a
   dated `Decision:` line for the approved flag, and a dated line that
   names SRD.md and why it was added, such as
   `- <date> Added SRD.md: the new --max-age flag is a public contract.`
5. **Phases.** P1 stays Verified with its evidence. The flag is new work
   the user approved, not a gap: TIDE-002 belongs to a new phase row, P2,
   Planned, since the user will build it tomorrow. Adding TIDE-002 to P1
   instead fails, because P1's work is finished and verified.
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
9. The answer reports P1 as done and verified, names TIDE-002 and its
   phase, and says the plan became a folder with SRD.md because the flag is
   a public contract.

Fail if the new requirement lives only in a Log line or the README, if the
plan stays one file, or if a requirement ID is in both `## Done when` and
SRD.md.

Without the skill, record which points the answer covers, for comparison.
