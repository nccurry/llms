---
name: work-visual-summary
description: "Summarize current work with evidence-backed code, CLI, config, API, or UI examples. Use when the user asks what has been done, what is planned, what remains, or what an implementation will look like. Do not use for a generic summary that does not need examples or work status."
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

## Map the changed surfaces

Before drafting, identify which of these surfaces are present in the inspected evidence: source code, CLI or terminal workflow, configuration, API, user interface, and operational workflow. A surface is present when it changed, is being proposed, or is central to the user's request.

Unless the user explicitly asks for a high-level or nontechnical summary, include an artifact for every present surface. Do not let the agent choose one convenient format when the work affects several surfaces. If an artifact cannot be shown, say which surface is omitted and why.

## Show the real thing

Prefer a source-backed artifact over an explanatory visual. A generic diagram, phase map, status table, or prose user journey may supplement the summary, but never replaces a concrete artifact for a present surface.

Use the matching form for each surface:

- **Source code:** Show a focused, verbatim snippet or before-and-after diff from the changed or central file. Preserve syntax and make the behavior visible; do not replace it with pseudocode or an architecture diagram.
- **CLI or terminal workflow:** Show a terminal transcript with the executable command, meaningful arguments or input, and representative observed or expected output. Do not show only a bare command unless it intentionally has no output.
- **Configuration:** Show the smallest valid configuration fragment, including its file or key context and the behavior it enables. Do not merely name a setting in prose.
- **API:** Show a compact request and response using the actual route, fields, and status or result shape.
- **User interface:** When a running app, local screenshot, browser preview, or design source is readily available, inspect it and show the actual screenshot or rendered view. Otherwise, show a compact ASCII wireframe grounded in the implemented components, with the user's action and resulting state labeled. Never generate an imaginary polished mockup and present it as shipped behavior.
- **Plan or operational workflow:** Show the concrete acceptance scenario, command sequence, or decision path that someone will actually follow.

Use real snippets from the work when they exist. Keep excerpts small and explain the behavior they show. When code, a CLI, configuration, and a UI or API all apply, show a compact example of each rather than selecting only one. If the work is only planned, label every invented artifact **Proposed** or **Illustrative**. Never describe a proposed interface, command, file, or result as if it already exists.

Show the effect, not only the files. A reader must be able to tell what a user, developer, or operator will do differently.

## Write the response

Lead with one direct sentence that says where the work stands and what it accomplishes. Then use only the sections that help:

1. **Concrete artifacts:** The source-backed code, command, configuration, API, or UI examples relevant to the work, each with a short explanation.
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
- For every present surface, did I show its matching artifact or clearly explain why it is unavailable?
- Did I show the actual code, command, configuration, API exchange, or screen—not only an abstract visual?
- What is still needed?
- Which parts are facts, proposals, or open decisions?
