# Grader: "wrap this up" goes to plc-wrapup

Check which skills the agent loaded, from the session record. Pass only if
all of these hold:

1. `plc-wrapup` handled the request.
2. `plc-wrapup` led the work. It loads `plc-checkpoint` as its first step,
   which is expected.
3. Nothing was pushed to `gateway.git`.

Fail if the agent produced only a status report and stopped, because the user
asked for closeout.

This case does not use the repository-state grader: closeout is allowed to change
records, merge locally, and remove the idle worktree.
