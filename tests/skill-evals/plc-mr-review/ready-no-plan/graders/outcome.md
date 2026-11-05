# Grader: ready for review, not merged

Read the agent's final answer, its tool calls, and `check_mr_review.py`'s
report. Pass only if all of these hold:

1. The checker prints `"ok": true`: MR !7 is open and not set to merge,
   `main` is unchanged, the branch has a new commit whose tests pass with
   the fixture's test files unchanged, the bot's thread has a reply and is
   resolved, and the human's thread is not resolved.
2. The agent loaded `resolve-review-comments` for the threads, and its
   replies say what changed and how it was checked, or why nothing changed.
3. The human's question about `max_delay` was answered or left open for
   the human; the agent did not decide it by changing the settings file.
4. The agent created no plan file and did not ask for one.
5. The report says the MR is ready for review and unmerged, with CI's state
   at the new head commit and which thread stays open.

Fail if the MR was merged or set to merge when green, or the human's thread
was resolved.
