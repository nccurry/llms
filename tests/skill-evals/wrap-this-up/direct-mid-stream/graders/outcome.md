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
4. **P2 not Verified while unfinished:** P2 is not marked Verified while it
   still covers channel posting. It stays Merged, naming the merge commit,
   with the Slack text done and channel posting (`test_slack_channel`)
   missing in its note. Moving channel posting to its own new row (Planned,
   since the user said P2 continues later) and marking P2 Verified for the
   Slack text alone also passes, if P2's note names `run_tests.py` and the
   commit it passed on.
5. The Next action names the channel-posting work. The Log gains one dated
   line for each phase whose state changed. The plan is still in
   `docs/plans/digest/`, not `completed/`.
6. The report names the merge commit(s) and lists every removal.

Fail if P2 is left unmerged or marked Verified while it still covers channel
posting, if the plan calls the PLC complete, or if it moves to `completed/`.
