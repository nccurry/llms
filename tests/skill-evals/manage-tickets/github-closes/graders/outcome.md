# Grader: `Closes #42` in the PR body

Read the agent's final answer, its tool calls, and `check_tickets.py`'s
report. Pass only if all of these hold:

1. The checker prints `"ok": true`: one open PR from `retry-backoff` into
   `main`, its body holds `Closes #42`, no other issue reference, issue #42
   still open, and no issue created, commented on or closed.
2. The agent followed the PR template, with the `Closes #` line completed.
3. The agent left closing #42 to the merge into the default branch, and the
   report says so.
4. The report gives the PR's link.

Fail if the agent closed #42 itself, created an issue, or used a reference
that does not close it, such as `Refs #42`, for this full fix.
