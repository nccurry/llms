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
   note.
4. **P2's word:** P2's parts are the Slack text, which merged, and channel
   posting, which never started. While P2 still holds channel posting (it
   was not moved to its own row), P2 is In progress, as `plc-planning`'s
   rule for a phase whose parts differ says. Its note names the merge
   commit, the Slack text as merged, and channel posting as missing; naming
   `test_slack_channel` is optional. Merged, Planned or Verified fails. If
   channel posting moves to its own new row (Planned, since the user said
   P2 continues later), P2's note says `moved to P<n>` for that row, and P2
   is worded from the Slack text alone: Merged naming the merge commit
   passes, and so does Verified naming `run_tests.py` and the commit it
   passed on.
5. The Next action names the channel-posting work. **Log**, by plan-record's
   Log rule: P1's state change needs a dated line. P2 stays In progress, so
   a line about its merge may be there but is not needed. The plan is still
   in `docs/plans/digest/`, not `completed/`.
6. The report names the merge commit(s) and lists every removal.

Fail if P2 is left unmerged, or marked anything but In progress while P2
still holds channel posting, if the plan calls the PLC complete, or if it
moves to `completed/`.
