---
name: visual-code-audit
description: Audit source code for crisp visual readability, useful comments, meaningful whitespace, calm indentation, consistent line shape, and an obvious scan path. Use for a visual code audit, readability pass, comment pass, style pass, eye-glide review, or wall-of-code review.
---

# Visual Code Audit

## Workflow

1. Identify the review scope from the user request or current changes.
2. Read local instructions, formatter rules, lint rules, and nearby idiomatic files.
3. Inspect each target file from top to bottom before you judge individual lines.
4. Find places where the reader must stop, jump backward, or decode unrelated ideas.
5. Distinguish visual defects from deeper ownership or control-flow defects.
6. Report only corrections that improve a concrete reading path.

## Routing Boundaries

- Use this skill for whitespace, grouping, declaration order, line shape, indentation, comments, and scan path.
- Use `code-quality-audit` for idiom, cohesion, control flow, and necessity.
- Use `abstraction-quality-audit` for file-tree structure, ownership, layering, and modularity.
- Use a formatter for mechanical style that the repository already defines.

## Audit Criteria

Check whether the code:

- Matches repository conventions for formatting, naming rhythm, comments, and declaration order.
- Uses blank lines to separate different ideas and keep one idea together.
- Presents declarations and methods in a predictable reading order.
- Breaks long lines at meaningful boundaries.
- Keeps indentation and nesting visually calm.
- Shapes chains, literals, conditions, and parameter lists consistently.
- Uses comments only for non-obvious purpose, contracts, invariants, ownership, units, lifecycle, or tradeoffs.
- Documents public or exported members when repository or language conventions require it.
- Keeps setup, validation, main work, side effects, and return handling easy to distinguish.
- Gives tests, fixtures, and examples the same visual care as production code.

## Avoid Fake Crispness

- Do not split cohesive code into trivial one-use helpers to reduce line count.
- Do not add comments that restate names or statements.
- Do not add decorative blank lines.
- Do not enforce a universal line or method limit without a repository standard.
- Do not align code by hand when the formatter will undo it.
- Route a wall caused by mixed responsibilities to `code-quality-audit` or `abstraction-quality-audit`.

## Output Contract

Lead with findings in impact order:

- `P1`: A visual or documentation defect hides unsafe behavior or a required contract.
- `P2`: A defect materially slows reading, review, or maintenance.
- `P3`: A concrete polish defect violates a user, repository, language, or framework standard.

Use high confidence for direct evidence. Use medium confidence for a strong inference from nearby conventions. Put low-confidence candidates under blind spots.

For each finding, include a tight file and line reference, the interrupted reading path, evidence, and a concrete correction.

If no actionable findings exist, say so. Name the files, conventions, and scan paths inspected.

## Correction Guidance

If fixes are authorized, use the smallest coherent readability change. Route deeper design defects instead of hiding them with formatting.
