# Grader: decisions made in chat

Read the agent's final answer, the checker's `packet_changes`, and the diff of
`docs/plans/shop/` in `tavern`. Pass only if all of these hold:

1. The answer lists both calls from the conversation as decisions: no cost on
   shop rows, and the rarity filter moved out of this slice. It also lists the
   existing palette decision as already recorded.
2. SHOP-001 is reported as merged, but not as meeting its requirement as
   written: the requirement still asks for cost on each row.
3. SHOP-002 is reported as not started, and out of this slice according to
   the conversation.
4. **Records:** the packet's Decisions table gains both chat decisions. Each
   may be marked accepted, since the user said "ok, merge it", or proposed,
   since the user only approved the merge. Either passes if the answer says
   which and why.
5. **Records:** an open question records the conflict between SHOP-001's
   text and the merged code. `SRD.md` is unchanged.
6. **Records:** `tavern` is on `main`, the default branch, so the edit is left
   uncommitted and the answer asks whether to commit it.

Fail if a chat decision is missing, if `SRD.md` changes, or if the edit is
committed to `main` without asking.

Without the skill, record which points the answer covers, for comparison.
