# Grader: merge mid-stream work

Read the agent's final answer, `check_wrap.py`'s report, and the plan on
`origin/main`. Pass only if all of these hold:

1. The checker prints `"ok": true`: both branches are on `origin/main`, both
   worktrees and local branches are gone, and `plc/digest-p1` is gone from
   the remote.
2. The agent ran `run_tests.py` on the combined result before pushing, and
   the report says it passed.
3. **Plan:** the Current Work block on `origin/main` shows P1 (DIG-001) merged, and P2
   (DIG-002) merged but not complete: Slack text done, channel posting
   (`test_slack_channel`) still to do. The next step names that work. The
   plan is still in `docs/plans/digest/`, not `done/`.
4. The report names the merge commit(s) and lists every removal.

Fail if P2 is left unmerged, the plan calls the PLC complete, or it moves to
`done/`.
