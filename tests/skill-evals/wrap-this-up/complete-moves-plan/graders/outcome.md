# Grader: completing a PLC

Read the agent's final answer, `check_wrap.py`'s report, and the plan on
`origin/main`. Pass only if all of these hold:

1. The checker prints `"ok": true`: P1 is on `origin/main`; the worktree,
   local branch, and remote branch are gone; the plan is at
   `docs/plans/completed/digest/` and no longer at `docs/plans/digest/`. The
   moved README says `- Status: Complete`, keeps `- Owner: @alex`, and has
   the historical-record line.
2. The agent ran `run_tests.py` on the merged result before pushing.
3. **Plan:** the moved plan's Current Work says Complete and adds
   "Historical record as of <commit>; the code is the current truth." P1's
   row is Verified, and its note names `run_tests.py` and the merge commit it
   passed on. No checkouts are listed, and a dated Log line records the
   completion.
4. The report names the merge commit and lists every removal, including the
   empty `notify-wt/digest/` campaign folder.

Fail if the plan stays in `docs/plans/digest/`, or if P1 is Verified with no
evidence in its note.
