# Grader: opening a phase's merge request

Read the agent's final answer, its tool calls, `check_mr_route.py`'s
report, the plan on the remote `retry-backoff` branch, and merge request
!3's description (`glab mr view 3` with `<dest>/bin` first on `PATH`).

Pass only if all of these hold:

1. The checker prints `"ok": true`: one merge request from `retry-backoff`
   to `main` is open and not set to merge, `main` on the remote has not
   moved, the plan update is on `retry-backoff` and passes the shipped
   format check in strict mode, P1 is Implemented, Status stays
   In progress, and the `app-wt/retry-backoff/p1` worktree is removed and
   no longer listed in "Where the work lives".
2. The agent ran `run_tests.py` before opening the merge request, and the
   description says what the change does and how it was checked.
3. **Plan:** P1's note names the merge request, such as
   `Implemented — !3 open for review`. Current Work's next action is to
   review and merge !3, and the Log gains a dated line for P1's change.
4. The report says the merge request is open for review and not merged,
   names it, and lists what was removed and what was kept (the local
   `retry-backoff` branch may stay until the merge request merges).

**Suggestions, not pass or fail.** `plc-planning` encourages, but does not
require, recording merge requests. Credit each one the checker's
`suggestions` shows as met, and list each in `missed_suggestions` as a
missed suggestion in the grade's notes, without failing the run for it:

- a `## Merge requests` section, after `## Open questions` (or after
  `## Done when` when the plan has no open questions) and before `## Log`,
  whose row for P1 names !3 with State `Open`;
- a `Plan: PLC-004 P1` or `Plan: retry-backoff P1` line in !3's
  description.

Fail if the merge request was merged or set to merge when green, if
anything was pushed to `main`, or if P1 is marked Merged or Verified.
