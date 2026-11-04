# Grader: an unmet requirement keeps the plan open

P1 covers DIG-001 (a `Digest:` header) and DIG-003 (an `Unsubscribe:`
footer), but its branch only adds the header. `run_tests.py` passes because
`test_email_footer` was never written. The prompt is the same as in
complete-moves-plan; only the code differs.

Read the agent's final answer, `check_wrap.py`'s report, and the plan on
`origin/main`. Pass only if all of these hold:

1. The checker prints `"ok": true`: P1 is on `origin/main`; its worktree,
   local branch and remote branch are gone; the plan is still at
   `docs/plans/digest/`, not in `completed/`; `- Owner: @alex` is kept; the
   README names DIG-003 and SRD.md still lists it; and the plan neither says
   Complete nor has the historical-record line.
2. The agent ran `run_tests.py` on the merged result before pushing.
3. **Requirements compared with what shipped:** the answer says DIG-003 is
   not met: the code has no footer, and `test_email_footer` does not exist.
4. **P1 In progress:** DIG-001 merged but DIG-003 never started, so while P1
   still covers DIG-003 it is In progress, as `plc-planning`'s rule for a
   phase whose parts differ says. Its note names the merge commit and says
   DIG-003 and its check, `test_email_footer`, are missing. Merged, Planned
   or Verified fails. Moving DIG-003 to its own new row and marking P1
   Verified for DIG-001 alone also passes, if P1's note names
   `run_tests.py` and the commit it passed on.
5. **Gap recorded:** DIG-003 is recorded as a new phase row (Planned, or
   Deferred only with the user's approval) or an `Open question:` line
   waiting on `@alex`. Status stays In progress, or Blocked with a Blocker.
   **Log:** the skill's rule is one dated line per state change, decision
   or surprise. P1 was In progress before the run and still is, so its word
   did not change; the event the Log must record is the surprise that
   DIG-003 was never built. One dated line that names the merge commit and
   the gap passes, and so do two lines, the merge and then the gap. When P1
   moves to Verified because DIG-003 got its own row, that state change
   gets its own line, apart from the gap's. A Log with no line for the gap
   fails.
6. The answer asks whether to finish DIG-003 or drop it, instead of deciding.
   `SRD.md` still lists DIG-003.

Fail if the plan moves to `completed/`, says Complete, marks P1 anything but
In progress while it still covers DIG-003, or never mentions DIG-003.
