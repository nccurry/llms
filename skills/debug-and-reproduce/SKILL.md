---
name: debug-and-reproduce
description: "Investigate a concrete application failure or regression, reproduce it, isolate the cause, and verify a focused repair. Use for debugging; not agent session recovery or speculative whole-repository review."
---

# Debug and Reproduce

Work from an observed symptom to a verified cause and repair. Preserve the
user's scope and partial work.

1. Read the report, relevant source, project instructions, and existing checks.
   Record the failing input/action, expected behavior, environment, revision,
   and observations. An application crash is not an agent-session crash.
2. Reproduce with the smallest realistic command, test, or user sequence. Reuse
   supported fixtures and local environments. If reproduction is blocked, say
   what evidence is missing; do not invent a successful reproduction.
3. Trace the failing path and form a falsifiable explanation. Check inputs,
   ownership/state, boundaries, errors, and recent changes that could cause it.
   Use focused experiments to distinguish explanations rather than accumulating
   unrelated edits.
4. Apply the smallest coherent fix to the demonstrated cause. Follow project
   conventions for routine choices. Ask only if the repair needs a material
   unresolved requirement, public contract, data migration, security decision,
   additional authorization, or scope expansion; continue independent work.
5. Repeat the original reproducer against the repaired revision and run checks
   covering adjacent affected behavior. Add a meaningful regression test when
   it protects a realistic failure; verify it exposes the old defect when
   feasible. Do not mirror implementation details or weaken existing assertions.

Keep temporary instrumentation out of the final change unless it belongs in
the product. Preserve useful diagnostics and avoid resetting user files.
Testing a hypothesis must not silently alter production data or contact live
services outside the task's authorization.

Report the symptom, reproduced cause, resulting behavior, source evidence,
commands/results and revision, and remaining uncertainty. Distinguish an
unconfirmed hypothesis, successful local repair, and validated deployment.
