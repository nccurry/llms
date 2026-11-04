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
4. **P2's word:** P2's plan section lists no tasks, only DIG-002, which
   names two pieces of work that can be built separately, so by
   `plc-planning`'s Parts rule P2 has two parts: the Slack text, which
   merged, and channel posting, which never started. While P2 still holds
   channel posting (it was not moved to its own row), P2 is In progress, as
   `plc-planning`'s rule for a phase whose parts differ says. Its note names
   the Slack text with the merge commit and channel posting as not yet
   merged; naming `test_slack_channel` is optional. Merged, Planned or
   Verified fails. If channel posting moves to its own new row (Planned,
   since the user said P2 continues later), P2's note says `moved to P<n>`
   for that row, and P2's word then comes from the Slack text alone: it
   must be Merged, naming the merge commit, or Verified, naming
   `run_tests.py` and the commit it passed on. In progress then fails.
5. The Next action names the channel-posting work. Channel posting is
   unfinished work that is not a gap: the user and P2's commit message
   ("channel posting still to do") already said it is still to be built,
   and P2 stays In progress. So plan-record point 7 does not apply: P2's
   note names it, and an `Open question:` line about it is allowed but not
   required. **Log**, by
   plan-record's Log rule: P1's state change needs a dated line. When P2
   stays In progress, a line about its merge may be there but is not
   needed. When channel posting moves to its own row, P2's changed word
   gets its own dated line. The plan is still in `docs/plans/digest/`, not
   `completed/`.
6. The report names the merge commit(s) and lists every removal.

Fail if P2 is left unmerged, or marked anything but In progress while P2
still holds channel posting, if the plan calls the PLC complete, or if it
moves to `completed/`.
