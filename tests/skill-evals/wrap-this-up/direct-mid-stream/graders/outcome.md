# Grader: merge mid-stream work

Read the agent's final answer, `check_wrap.py`'s report, and the plan on
`origin/main`. Pass only if all of these hold:

1. The checker prints `"ok": true`: both branches are on `origin/main`, both
   worktrees and local branches are gone, and `plc/digest-p1` is gone from
   the remote. The plan keeps `- Owner: @alex` and does not say Complete.
2. The agent ran `run_tests.py` on the combined result before pushing, and
   the report says it passed.
3. **Plan:** on `origin/main`, P1's row in `## Phases` is Merged, naming the
   merge commit, or Verified with `run_tests.py` and that commit in its
   note. P2's row is Merged but not Verified: its note says the Slack text is
   done and channel posting (`test_slack_channel`) is still missing. A new
   row for that remaining work also passes. The Next action names that work,
   and a dated Log line records the merges. The plan is still in
   `docs/plans/digest/`, not `completed/`.
4. The report names the merge commit(s) and lists every removal.

Fail if P2 is left unmerged or marked Verified, if the plan calls the PLC
complete, or if it moves to `completed/`.
