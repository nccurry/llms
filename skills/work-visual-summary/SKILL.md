---
name: work-visual-summary
description: "Explain the user's requested subject, current work, or proposed behavior with concrete code, command, config, API, or UI examples. Use when examples help assess or understand it, not for a routine factual status reply."
---

# Work Visual Summary

Make the subject visible in practice. Answer what the user is asking about or
explain the work underway with representative examples instead of only naming
files, concepts, or phases.

## Ground the explanation

Read the conversation and inspect the smallest relevant source, plan, diff,
configuration, or result. Show what exists, what is proposed/changed, and what
remains uncertain only where that distinction matters to the question.
Current source establishes implemented behavior; plans and old results do not.

Select the examples that best explain the user's question. Usually one or a few
focused snippets are enough. Do not require an artifact for every surface
mentioned, dump the diff, or turn a simple status answer into a report.

## Show concrete examples

Use the form suited to the behavior:

- Code: a focused actual snippet or before/after change with enough syntax and
  surrounding context to explain the effect.
- CLI: an executable command with meaningful arguments, and observed output
  when it helps. A bare command is sufficient when invocation is the question.
- Configuration: the smallest valid fragment with its file/key context and the
  behavior it selects.
- API: a representative request/response using verified routes and shapes.
- UI: an actual inspected screenshot/preview when available; otherwise a
  labeled illustrative wireframe showing the relevant action and state.
- Workflow: the concrete action sequence or acceptance scenario someone follows.

Label invented/proposed code, interfaces, wireframes, or expected output
`Proposed` or `Illustrative`. Never fabricate a transcript or present expected
output as an executed result. For conceptual questions, clearly labeled
examples may teach the idea without pretending they come from the repo.

Explain each example's consequence in plain English. A diagram or status table
can supplement concrete examples when it clarifies relationships; it does not
replace the representative behavior the user needs to see.

## Response

Lead with the answer or outcome. Show the relevant examples next, then include
only useful status, decisions, evidence, remaining work, or limits. Avoid forced
sections and templates. Keep the completed/proposed boundary unmistakable.

Before sending, check: does the answer show what someone will write, run,
configure, request, or see; are examples accurate/labeled; and are material
unknowns or unfinished checks clear?
