# Grader: a small change gets a one-file plan

The fix is one argument check in `harbor.py` and one test. The repository's
`docs/plans/README.md` says where plans go (`planned/` for a new one) and that
a plan for small work is one file, `plc-<slug>.md`. The planning skill
agrees: it chooses a one-file plan when no trigger in its Adding files rule
holds. None holds here: the error for a limit below 1 is a bug fix in the
existing `--limit` flag, not a contract change. This case grades that one
shape.

Run `check_plan.py`, then read the plan and the agent's final answer. Pass
only if all of these hold:

1. **One file.** The checker prints `"ok": true`: the run added one plan,
   `docs/plans/planned/plc-<slug>.md`, and changed nothing else. There is no
   packet folder, no side file such as `plc-<slug>-srd.md`, and no `SRD.md`,
   `SADD.md`, `IMPLEMENTATION_PLAN.md` or `FIXTURES.md`; `harbor.py` and the
   tests are unchanged.
2. **Shared shape.** The plan has, in this order: the title; a one- or
   two-sentence summary directly under it; `## Current Work`; `## Phases`;
   `## Done when`; `## Open questions` only if a question is really open;
   and `## Log` last.
3. **Current Work.** It starts with `- Status: Planned`, `- Owner: @alex`,
   and `- Last updated:` with the run's date, `main` and the current commit.
   It has every other template key: Next action, Blocker, Depends on,
   Current state and Resume check. The Next action is one concrete step:
   it says what to do first and where, naming a file to change or a command
   to run, so the next person can start without choosing, as in
   `Write a failing test for --limit 0 in tests/test_harbor.py`. A Next
   action that names the whole phase, such as `Implement P1`, is not
   concrete. The "Where the work lives" table is there, and lists no
   checkout.
4. **Phases.** The table is `| Phase | Name | Owner | State |`, with one row,
   `P1`, in state Planned. A second phase for work this small is a fail.
5. **Done when.** Each requirement has an ID, says what is true when it is
   done (`--limit 0` and a negative limit exit with an error, and a valid
   limit still works), and names a check that can be run with its expected
   result, such as `python -m unittest` passing with a new test.
6. **Log.** `## Log` starts with `- <date> Created.` It may also hold dated
   `Decision:` or surprise lines, one per decision or surprise, as the
   skill's Log rule allows ("one dated line per state change, decision or
   surprise").
7. **No filler.** No empty sections, and no `N/A`, `TBD` or `<placeholder>`
   text.
8. The answer says where the plan is and that no code was changed. It does
   not start the fix.
9. **Format check.** The planning skill's format check passes in strict
   mode. From the skills repository root, this exits 0 and prints nothing:

   ```sh
   python3 skills/plc-planning/scripts/format_check.py --packet <dest>/harbor/docs/plans/planned/plc-<slug>.md --strict
   ```

10. **Review.** The plan is new, so the agent ran `review-and-fix-plc` on
    it, or said that subagents were unavailable. Fixes from that review are
    fine if the other points still hold.

11. **No padding with diagrams.** The skill encourages diagrams but never
    requires them, and a one-file plan this small needs none. A plan with no
    diagram passes this point; do not ask for one. One small diagram that
    fits what it explains, such as a plain-text tree of the two files the fix
    touches, also passes. Fail a plan with two or more diagrams, or one
    diagram that shows parts the change does not touch.

Fail if the agent writes a packet folder or the full packet, adds files
beside the plan, changes code, or leaves template placeholders in the plan.

Without the skill, record which points the answer covers, for comparison.
