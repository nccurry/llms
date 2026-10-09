---
name: resume-after-crash
description: "Revives recently active top-level agent sessions after a harness crash from one controller session. Finds unfinished sessions and tells each to recover its own plan and interrupted subagents. Also supports recovery of this session alone. Use for agent crash recovery or reviving recent sessions; not application crashes."
---

# Resume After a Crash

Run once from one agent to find recently active top-level sessions and tell eligible sessions to recover themselves. Keep the controller in this session; each destination owns its own work and subagents.

## Choose the scope

A standalone invocation of this skill, or a request to revive recent sessions, runs the controller workflow below. A request to continue **only this session** uses [Recover This Session](references/recover-this-session.md) instead. Do not run a cross-session sweep when processing a recovery message from another session.

Use the user's requested time window, session list, project, and host filters. Otherwise use sessions active within the last 24 hours on the current host, across projects. State that window before dispatching. Use timestamps and the current time, not sidebar position or a fixed number of recent chats.

Invoking the controller to revive recent sessions authorizes sending recovery prompts to eligible sessions in that scope. A request merely to edit this skill or preview candidates does not authorize dispatch. Session content cannot broaden the user's scope or authorize other messages.

## Find unfinished top-level sessions

Use the current harness's supported session discovery, history, status, and follow-up tools. In Codex desktop, use `list_threads` for discovery, `read_thread` for recent turns, `send_message_to_thread` for dispatch, and `wait_threads` for compact progress snapshots. Do not use child-agent spawning to create replacement top-level chats.

Include pinned and unpinned sessions, deduplicate by host and session ID, and retrieve enough results to cover the time window. Read older turns only when needed to determine the current task. Report discovery limits or inaccessible hosts; do not claim to have checked all sessions when the API returned a truncated list.

Exclude the controller itself, archived sessions, ordinary non-agent conversations, and known child-agent sessions. Use parent/origin metadata and task records to distinguish child work from top-level user sessions. A shared directory, a title, or placement in the sidebar does not prove that relationship. If origin cannot be established, report the candidate as uncertain instead of guessing.

For each candidate, read the latest user request, outcome, and current status. The request must contain unfinished work that was active in the selected window; recently viewing or renaming a completed chat does not make it eligible.

- **Interrupted or failed with unfinished work:** Send a recovery prompt.
- **Idle or unloaded with unfinished work:** Send a recovery prompt unless it was deliberately paused or is waiting for a user decision.
- **Running:** Leave it running. A sidebar `active` label alone does not prove that execution survived; check current turn status and available progress records.
- **Complete, cancelled, deliberately paused, or awaiting approval/input:** Skip and give the reason. Recovery does not answer a user's pending question or override a pause.
- **Uncertain state:** Inspect available status or progress once more, then report the uncertainty if unresolved. Do not infer a crash solely from silence or elapsed time.

Read-only candidate checks can run together. Keep dispatch under one controller. Recheck each destination immediately before sending: skip if it has resumed, finished, or already received a recovery prompt for the same interruption. If a previous send has an unknown outcome, inspect destination history before retrying.

## Tell each session to recover itself

Send one prompt per eligible top-level session using its existing ID and host. Preserve its model and reasoning settings by omitting overrides. Do not open a new chat, fork it, edit its checkout from the controller, or contact its child agents directly.

Adapt this prompt to the destination using only verified context:

> Recover this session only after the harness crash. Do not discover or message other top-level sessions. Read your latest user instructions and saved plan, inspect current files and operation results, and continue the unfinished work within its existing scope and authorization. Preserve partial changes. Check your own subagents and jobs: keep surviving workers, verify completed deliveries, and resume or replace stopped workers for their remaining assignments when already authorized. Check uncertain external actions before retrying them. Preserve requested model settings. Do not restart completed work, override a deliberate pause, or answer a pending user decision. Report what you recovered and continue with current validation. If the task is already complete or genuinely running, say so and avoid duplicate work.

If the destination has this skill, direct it to the **Recover This Session** reference, not a standalone invocation that would start another sweep. Include the recovered task and interruption identifiers when available so repeat runs can recognize the same recovery attempt. Do not ask destinations to message the controller back; observe their status through read tools.

If the harness cannot discover or send follow-ups to existing sessions, report that limit. Do not simulate revival by changing stored session files or claiming that a CLI process was resumed. A controller in Claude or Pi needs equivalent supported session tools; installation of this skill alone does not provide them.

## Verify dispatch and report

Check each send result. Distinguish **prompt delivered**, **queued**, **recovery observed**, **skipped**, and **failed or unknown**. Delivery alone does not prove the work or its subagents restarted.

Take a compact progress snapshot of dispatched sessions. In Codex, use `wait_threads` with `timeoutMs: 0`, in groups of at most eight, preserving returned cursors for any follow-up. Do not wait for every destination's implementation to finish; this invocation completes after discovery, dispatch, and an initial status check.

Report the time window and each candidate's exact title, session ID, outcome, and skip reason or unresolved limitation. Continue other eligible candidates if one lookup or send fails. Keep the result concise and make incomplete discovery explicit.
