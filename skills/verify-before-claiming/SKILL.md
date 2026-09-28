---
name: verify-before-claiming
description: "Check current evidence before claiming that code, plans, tests, CI, or requirements are complete. Use during implementation, review, and status reports where an unsupported claim would mislead the next decision."
---

# Verify Before Claiming

Use the source that can establish each material claim. For example, inspect the
current code for implemented behavior, the selected revision's test result for
validation, and the current plan for its requirements. A plan, MR description,
child report, or old test run does not prove that the current code passes.

- Check the relevant source or run the smallest useful check before stating a
  material result. Keep the revision or other scope of the evidence clear.
- Separate what you observed from what you infer. State an inference as an
  inference when direct proof is unavailable.
- If a needed fact remains unknown, say exactly what is unknown and what check
  would settle it. Keep dependent work or acceptance open; continue safe work
  that does not depend on that fact.
- Do not invent files, APIs, command results, test runs, citations, or completion
  evidence. Do not turn a missing log into a claim that a test passed or failed.
- When sources disagree, inspect the source that governs the question. Surface
  any unresolved conflict that changes the work or its acceptance.

Give enough evidence for another person to check important conclusions, such as
a file and revision, a command and result, or a CI job. Ordinary local coding
choices do not need a formal evidence record. This skill guides work as it
happens; it is not a separate audit or a reason to stop for harmless uncertainty.
