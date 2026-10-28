# Grader: "where are we" goes to plc-checkpoint

Check which skills the agent loaded, from the session record, and run
`check_wrap.py`. Pass only if all of these hold:

1. `plc-checkpoint` handled the request; `wrap-this-up` did not. Loading it
   briefly and handing off is a partial pass; record it.
2. The checker prints `"ok": true`: nothing merged, both worktrees and
   branches kept.
3. The answer reports P1 done on its branch (pushed, not merged), P2 partly
   done, and what's left.
