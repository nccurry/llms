---
name: code-quality-audit
description: Audit recent or proposed code for idiomatic design, simple control flow, cohesive units, useful comments, intuitive names, and maintainability. Use when the user asks whether code is clean, elegant, easy to follow, or ready for more work.
---

# Code Quality Audit

## Workflow

1. Identify the review scope from the user request or current changes.
2. Read local instructions, style guides, formatter rules, and nearby code patterns.
3. Read each target file with enough context to understand its role.
4. Judge the code against the repository's language and framework idioms.
5. Route specialist concerns to the skills listed below.
6. Report concrete findings before general observations.

## Routing Boundaries

- Use this skill for idiom, cohesion, control flow, necessity, comments, and general maintainability.
- Use `abstraction-quality-audit` for file-tree structure, ownership, layering, naming systems, and indirection.
- Use `visual-code-audit` for whitespace, line shape, comment placement, and scan path.
- Use `correctness-reliability-audit` for behavior, state, errors, lifecycle, and recovery.
- Use `performance-audit` for measurable runtime or resource cost.
- Use `test-quality-audit` for test design and assertion quality.

## Review Criteria

Check whether the code:

- Uses common names for the language, framework, and design pattern.
- Makes control flow easy to scan.
- Uses guard clauses when they remove meaningful nesting.
- Keeps methods and classes cohesive without splitting every step into a helper.
- Avoids unnecessary functions, methods, classes, interfaces, wrappers, and call chains.
- Uses straightforward loops and conditions when they communicate intent better than a clever expression.
- Keeps data structures, nullability, errors, and lifecycle expectations visible.
- Adds comments for contracts, invariants, ownership, units, lifecycle, tradeoffs, and surprising decisions.
- Removes comments that restate code, preserve prompt history, or compensate for poor names.
- Fits the repository's established conventions without copying a local defect.
- Includes validation that matches the risk of the change.

## C# and Game-Code Notes

- Prefer modern C# that remains familiar to the project team.
- Route hot-path allocations and repeated update or draw work to `performance-audit`.
- Route unsafe structural changes during ECS iteration to `correctness-reliability-audit`.
- Keep asset ownership and lifecycle code easy to follow.

## Output Contract

Lead with findings in impact order:

- `P1`: A quality defect makes behavior unsafe, blocks change, or creates severe maintenance risk.
- `P2`: A defect makes important code difficult to understand or modify safely.
- `P3`: A concrete idiom, naming, comment, or simplification defect violates an established standard.

Use high confidence for direct evidence. Use medium confidence for a strong inference from the inspected code. Put low-confidence candidates under blind spots.

For each finding, include a tight file and line reference, evidence, impact, and a specific correction.

If no actionable findings exist, say so. Name the files inspected, validation results, and blind spots.

## Correction Guidance

If fixes are authorized, make the smallest coherent change that produces clean code. Use a larger rewrite when a local edit preserves the root defect.

Request direction before a rewrite changes a public contract, schema, unrelated subsystem, or unauthorized user-visible behavior.
