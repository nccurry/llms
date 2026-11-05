# Grader: the given Jira key, in the project's form

Read the agent's final answer, its tool calls, and `check_tickets.py`'s
report. Pass only if all of these hold:

1. The checker prints `"ok": true`: one open MR from `retry-backoff` into
   `main` whose title starts `PROJ-481: `, no other ticket key, and no write
   to the fake `jira`.
2. The agent took the title form from `CONTRIBUTING.md` or the `mr-title`
   CI job, not from history alone.
3. The agent did not move PROJ-481 by hand: the rules say Jira does that.
   Reading it with `jira issue view` is fine.
4. The report names PROJ-481 and the MR's link, and says the ticket was not
   moved by hand, and why.

Fail if the title has another key or form (such as `[PROJ-481]` or a key at
the end), or any Jira write was made.
