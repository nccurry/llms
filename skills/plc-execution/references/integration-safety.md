# Integration safety

Use the sections relevant to the integration risk. Keep evidence in the existing
work list and completion map; do not create another ledger or approval gate.

## Concurrent target updates

Serialize competing writes to a shared target using the project's existing
merge queue or integration process. For direct local merges without one, choose
an integration owner for the current merge window. Independent branches can
continue; no permanent coordinator or repository-wide process lock is required.

Record the expected target commit, delivered commit, and tested combined source.
Read the target's HEAD and status again immediately before integration. If it
moved, inspect the intervening changes, reconcile the candidate, and refresh
checks affected through callers, dependencies, configuration, or shared state.
A conflict-free merge and disjoint filenames do not prove behavioral independence.

Preserve other agents' work. Reuse an existing checked integration tree when it
represents the intended combined source; create a separate candidate only when
needed. After integration, verify the delivered tree, status, and unmerged
entries: successful Git exit can coexist with automatic-stash conflicts.
Verify remote identity when remote delivery is part of the assignment.

Keep the checked source stable during combined verification. Record its identity
before and after. An evidence-only documentation commit may preserve code checks
after inspecting its diff; a dependency change may invalidate them without
touching the feature's files. Refresh affected evidence, not every unrelated test.

## Check the changed contract

Choose the smallest existing check that reaches the changed contract. Where the
result depends on host timing, event order, layout preparation, or resource
lifetime, preserve that behavior in the fixture. Direct helper tests do not
prove a boundary they bypass. Use native/component evidence when that boundary
owns the result; contract-neutral edits do not automatically need a new end-to-end
test or platform run. Verify actual execution with `verify-before-claiming`.

## Track affected platforms and references

When behavior or dependencies vary by platform/backend, name the affected
variants, proving check, evidence revision, and actual acceptance owner in the
existing plan. A passing platform does not verify another. Respect explicit
user deferrals, retaining their scope and the condition for revisiting them.

For visual changes, resolve reference paths from the actual capture catalog;
case names need not equal image basenames. Inspect each affected reference's
history and compare baseline/candidate on the same environment. Review intended
differences against the authorized behavior before regenerating through the
repository's supported command. A matching baseline image proves preservation,
not correctness or acceptance of a new rendering policy.

## Existing failures and integration exceptions

Reproduce a relevant failure on the comparison base before calling it pre-existing.
Separate a known cause from an environment hypothesis. Repeated failure on both
trees does not establish the cause or make the affected behavior safe.

Fix introduced or worsened in-scope failures. Track unrelated debt separately.
When an integration exception relies on a repair handoff, name its owner and
tracking reference, obtain acknowledgement through authorized channels, and
record the acceptance step that must revisit it. If communication is unavailable,
retain ownership in the current plan rather than claiming the handoff occurred.

If required acceptance cannot be established, keep that gate failed/incomplete.
A user's explicit bounded integration exception permits only the stated merge;
record the exact cases, platform, evidence, and unresolved acceptance. It does
not turn the failed check into PASS, waive new cases, or complete the originating
feature's acceptance. Apply an existing authorization within its stated limits
without asking again. Raise a new decision only when those limits do not cover
the actual remaining requirement or risk.
