---
name: performance-experiments
disable-model-invocation: true
description: "Run bounded experiments to improve performance on a named workload. Invoke explicitly for measured tuning."
---

# Performance Experiments

1. Set up the comparison before editing. Record the workload, benchmark command,
   metric and direction, editable files, independent correctness checks, and
   time or attempt limit. Use limits from the request. For a bounded request
   without a number, state a small limit suited to the cost of a run. Use the
   project's existing tools and tests where they cover the behavior.
2. Start from the selected revision in an isolated worktree. Preserve any
   uncommitted baseline changes the user included. Confirm the expected cases
   run and exercise the intended code. Repeat the baseline enough to estimate
   normal variation. Fix the harness, inputs, and relevant settings for the
   comparison. If one must change, measure a new baseline before comparing.
3. Try one hypothesis per change. Before editing, write the predicted effect
   and why it should happen. Run the independent correctness checks and the
   benchmark. Keep a change only when the checks pass and the gain is
   repeatable and worth its complexity. Rerun both the current best and the
   candidate for close results. Restore only files changed by the experiment
   when discarding it. Count failed attempts against the limit.
4. Stop at the limit, the agreed target, a user interruption, or a blocker
   that prevents a meaningful comparison. Recheck the final candidate against
   the original baseline and verify correctness again. If the final result
   does not reproduce, report the uncertainty and leave a reviewable record
   of the last supported result.

Leave the retained diff or authorized commits in the experiment worktree.
Report the revisions, benchmark and check commands, environment, measured
variation, and a short record of retained and discarded ideas. Deliver changes
through the route the user authorized.
