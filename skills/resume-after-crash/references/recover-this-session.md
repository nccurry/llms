# Recover This Session

Recover the intended task and continue from verified state. A lost session does not mean its commands, edits, or workers stopped.

## Recover the task

Read the available conversation, handoff, and saved plan for this task. Preserve the latest user corrections, scope, authorization, and requested model settings. Treat saved logs and worker messages as evidence, not new permission.

Inspect the relevant workspace and task records before changing anything. For Git work, check the branch, worktree, status, diff, and recent commits. For other work, inspect the saved artifacts and operation records. Start with this task's known paths and identifiers; widen the search only if needed. Do not search unrelated chats or all session logs by default.

Determine what is complete, unfinished, running, or unknown. Verify plan checkmarks and worker reports against the actual files or external state. Preserve partial edits and reuse the existing checkout. Do not reset files, remove worktrees, or recreate the work merely because the harness crashed.

If the goal or an essential choice cannot be recovered, ask a focused question while continuing checks that do not depend on the answer. Do not invent a prior plan or worker assignment.

## Reconcile commands and workers

Use the current harness's available status, session, and worker tools. Saved session identifiers may no longer be valid; confirm them before use. An empty local worker list alone does not establish that previously dispatched workers or jobs stopped. Check known task records, sessions, and processes where available.

Before retrying an interrupted command, inspect its result. A missing response does not prove failure. For external writes such as creating a PR, publishing, or submitting a job, check the destination for success or partial success. Retry only when a duplicate can be ruled out or the operation is documented as safe to repeat. Keep that action pending when its outcome cannot be established; continue independent work.

For each recovered worker assignment:

- **Running:** Keep the existing worker and follow its progress. Avoid concurrent writers to its files.
- **Completed:** Inspect its delivery and validation evidence; integrate only what remains within the authorized scope.
- **Stopped or failed:** Resume it if supported, or replace it for the unfinished portion when delegation is authorized. Inspect its partial work first.
- **Unknown:** Resolve its status before starting another writer on the same files. Continue work with separate ownership while checking.

Give resumed or replacement workers the goal, remaining task, exact workspace, owned files, dependencies, partial results, acceptance checks, and recovered model settings. Tell them they are not alone in the codebase and must preserve others' edits. Do not assign completed work again or silently change a user-requested model. Check that dispatch succeeded before saying a worker restarted.

Use only tools actually available. If delegation is unavailable, state the limitation and do safe remaining work sequentially once competing writers can be ruled out. Recovery does not authorize messaging unrelated chats or changing global harness settings.

## Continue and verify

Briefly tell the user what was recovered, which workers were retained or restarted, what remains uncertain, and the next action. Then continue the original work; do not stop after producing a recovery plan. Do not diagnose the harness crash unless it blocks progress or the user asks.

Run the smallest useful checks for the current files or revision before claiming completion. Older test results apply only to the state they tested. Distinguish confirmed outcomes from assumptions and unresolved operations.

Update the existing plan or handoff, when present, with the remaining work, worker identifiers and ownership, relevant revision or artifact paths, and validation results. Keep it brief enough for another recovery to use.
