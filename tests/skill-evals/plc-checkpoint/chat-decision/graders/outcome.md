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
4. **Records:** both chat decisions are in the packet. Each is either a dated
   `Decision:` line added at the end of `## Log`, as accepted because the user
   said "ok, merge it", or an `Open question:` line waiting on `@alex`, as
   proposed because the user only approved the merge. Either passes if the
   answer says which and why. The palette decision's Log line is unchanged.
5. **Records, the unmet requirement:** the gap between SHOP-001's text and
   the merged code (no cost on the row) is recorded as an `Open question:`
   line waiting on `@alex`, or as a new phase row (Planned, or Deferred only
   with the user's approval) that names SHOP-001. SHOP-001 is never marked
   met without evidence: P1 is not marked Verified. `SRD.md` is unchanged.
   P1 stays In progress while it still holds SHOP-002 or the cost gap
   (plan-record point 6); it is Merged or Verified only once both have
   `moved to P<n>` rows.
6. **Records, the filter left out:** SHOP-002 is recorded as out of this
   slice, as a new phase row or an `Open question:` line, naming SHOP-002.
   The row is Planned, or Deferred only if the answer counts "ok, merge it"
   as the user's approval and says so.
7. **Records:** `tavern` is on `main`, the default branch, so the edit is left
   uncommitted and the answer asks whether to commit it.

Fail if a chat decision is missing, if SHOP-001's gap is not recorded, if
`SRD.md` changes, or if the edit is committed to `main` without asking.

Without the skill, record which points the answer covers, for comparison.
