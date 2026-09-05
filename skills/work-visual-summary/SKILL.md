---
name: work-visual-summary
description: "Summarize the current work with concrete, visual examples. Use when the user asks what has been done, what is planned, what remains, or what an implementation will look like. Do not use for a generic summary that does not need examples or work status."
---

# Work Visual Summary

Help the user see the current work clearly. Turn the discussion, plan, implementation, or diff into a short status report with examples that make the result easy to judge.

## Build the summary from evidence

Read the current conversation first. Then inspect only the plan, files, diff, tests, or configuration that help answer the request.

Classify the work before you write:

- **Planning:** No implementation exists yet. Show the intended outcome and the next decisions.
- **In progress:** Separate completed work, the active proposal, and the remaining work.
- **Completed:** Show what changed, the proof that it works, and the remaining review or merge work.

State uncertainty plainly. Do not turn an assumption into a fact. If the conversation does not settle an important choice, name it as an open question.

## Show a representative example

Include at least one small, concrete example that best matches the work. Choose the most useful form:

- A focused code snippet or a before-and-after diff for a code change.
- A terminal session for a CLI or workflow.
- A small configuration example for a configuration change.
- A request and response for an API.
- A brief user journey or ASCII wireframe for a user-facing change.
- A phase map, milestone table, or acceptance example for a PLC or other plan.

Use real snippets from the work when they exist. Keep excerpts small and explain the behavior they show. If the work is only planned, label every invented artifact **Proposed** or **Illustrative**. Never describe a proposed interface, command, file, or result as if it already exists.

Show the effect, not only the files. A reader must be able to tell what a user, developer, or operator will do differently.

## Write the response

Lead with one direct sentence that says where the work stands and what it accomplishes. Then use only the sections that help:

1. **Concrete example:** The representative example and a short explanation.
2. **Work status:** What is done, proposed, and remaining. Use a compact table or flow when it makes the sequence clearer.
3. **User experience:** What someone will see or do, when the work changes an interface or workflow.
4. **Decisions or risks:** Important choices, limits, or open questions.
5. **Merge path:** Tests, review, documentation, or release steps still required after implementation.

For a plan, make the future state easy to picture. For a completed change, make the shipped behavior and merge path easy to inspect. For an in-progress change, make the boundary between completed and proposed work unmistakable.

Use plain English. Prefer short, direct sentences and familiar words. Remove filler, generic claims, repeated restatements, and unsupported guesses. Do not dump every file, every diff hunk, or a template that does not fit the work.

## Quality bar

Before sending the summary, make sure that it answers these questions:

- What exists now?
- What will change, or what changed?
- What does it look like in practice?
- What is still needed?
- Which parts are facts, proposals, or open decisions?
