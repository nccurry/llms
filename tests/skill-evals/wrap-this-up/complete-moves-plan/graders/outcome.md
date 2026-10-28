# Grader: completing a PLC

Read the agent's final answer, `check_wrap.py`'s report, and the plan on
`origin/main`. Pass only if all of these hold:

1. The checker prints `"ok": true`: P1 is on `origin/main`; the worktree,
   local branch, and remote branch are gone; the plan is at
   `docs/plans/done/digest/` and no longer at `docs/plans/digest/`.
2. The agent ran `run_tests.py` on the merged result before pushing.
3. The moved plan's Status says Complete, with DIG-001 verified on the merge
   commit (or merged with the test result cited), and no checkouts listed.
4. The report names the merge commit and lists every removal, including the
   empty `notify-wt/digest/` campaign folder.
