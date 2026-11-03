# Grader: a small change gets a README-only plan

The fix is one argument check in `harbor.py` and one test. The repository's
`docs/plans/README.md` says where plans go (`planned/` for a new one), but not
what shape they take, so the planning skill's sizing decides.

Run `check_plan.py`, then read the plan and the agent's final answer. Pass
only if all of these hold:

1. **One file.** The checker prints `"ok": true`: the run added one plan,
   `docs/plans/planned/<slug>/README.md` (or a one-file
   `docs/plans/planned/plc-<slug>.md`), and changed nothing else. There is no
   `SRD.md`, `SADD.md`, `IMPLEMENTATION_PLAN.md` or `FIXTURES.md`, and
   `harbor.py` and the tests are unchanged.
2. **Shared shape.** The plan has, in this order: the title; a one- or
   two-sentence summary directly under it; `## Current Work`; `## Phases`;
   `## Done when`; `## Open questions` only if a question is really open;
   and `## Log` last.
3. **Current Work.** It starts with `- Status: Planned`, `- Owner: @alex`,
   and `- Last updated:` with the run's date, `main` and the current commit.
   The Next action is one concrete step, such as writing the failing test.
   The "Where the work lives" table, if present, lists no checkout.
4. **Phases.** The table is `| Phase | Name | Owner | State |`, with one row,
   `P1`, in state Planned. A second phase for work this small is a fail.
5. **Done when.** Each requirement has an ID, says what is true when it is
   done (`--limit 0` and a negative limit exit with an error, and a valid
   limit still works), and names a check that can be run with its expected
   result, such as `python -m unittest` passing with a new test.
6. **Log.** `## Log` has one line: `- <date> Created.`
7. **No filler.** No empty sections, and no `N/A`, `TBD` or `<placeholder>`
   text.
8. The answer says where the plan is and that no code was changed. It does
   not start the fix.

When the planning skill's format check is available, it must agree. From the
skills repository root:

```sh
python skills/plc-planning/scripts/format_check.py --packet <dest>/harbor/<plan path> --strict
```

It must exit 0 and print nothing. Use the plan's folder for a README plan,
or the file for a one-file plan.

Fail if the agent writes the full packet, adds files beside the README,
changes code, or leaves template placeholders in the plan.

Without the skill, record which points the answer covers, for comparison.
