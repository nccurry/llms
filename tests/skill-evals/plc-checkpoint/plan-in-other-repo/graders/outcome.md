# Grader: plan kept in another repository

Read the agent's final answer, the checker's report, and `git log` in
`<dest>/plans`. Pass only if all of these hold:

1. The agent found the plan in `../plans/docs/plans/sync-api/` through the
   api repo's `AGENTS.md`.
2. P1 / SYN-001 is reported as implemented on `plc/sync-api-p1`, not merged.
   P2 is planned.
3. **Current Work rewritten in the plans repo:** P1's row in `## Phases`
   reads Implemented and names the commit, the `api-wt/sync-api/p1-endpoint`
   checkout is listed, and Current Work has a new "Last updated" and a next
   step. `- Owner: @alex` is unchanged, and a dated Log line records P1's
   change. Committed on the plans repo's `main`, touching only
   `docs/plans/`.
4. Nothing pushed to `plans.git` or `api.git`, and no plan file created in
   the api repo. The report says the plans commit is local and not pushed.

Fail if the plan is copied into the api repo, the plans repo is pushed, or
P1 is called merged.
