---
name: visual-code-audit
description: Audit source code for visual readability and polish: repository style fit, spacing, grouping, line length, comments on structs, classes, fields, and tricky sections, and an easy visual reading path. Use when the user asks for a visual code audit, readability polish, style pass, comment pass, eye-glide review, or whether code looks nice and legible.
---

# Visual Code Audit

Use this skill to audit how source code reads at a glance. Focus on visual rhythm, local style consistency, comment coverage, line shape, and whether related ideas are grouped so maintainers can scan the file comfortably.

## Workflow

1. Identify the review scope from the user's request. If the scope is not explicit, inspect `git status`, `git diff --stat`, and changed files.
2. Read local project instructions first, such as `AGENTS.md`, formatter config, lint config, style guides, and nearby code in the same package or feature area.
3. Sample existing files that maintainers would treat as idiomatic. Notice naming rhythm, blank-line usage, wrapping style, comment style, and declaration order.
4. Read the target code top to bottom as a visual pass before judging details. Look for places where the eye has to stop, jump backward, or chase unrelated ideas.
5. Check comments on structs, classes, fields, exported members, and tricky sections against the repository's expectations. Prefer concise comments that reveal purpose, invariants, units, ownership, or lifecycle.
6. Report concrete findings with tight file and line references. If the user asked for fixes, make the smallest readability-only edits, then run the formatter and focused validation when practical.

## Routing Boundaries

- Use this skill for visual polish, spacing, grouping, line length, comments, declaration order, and scan path.
- Use `code-quality-audit` for broader maintainability, control flow, idiom, and correctness-adjacent readability.
- Use `abstraction-quality-audit` when the shape problem is primarily ownership, naming, layering, or indirection.

## Audit Criteria

Check whether the code:

- Matches the repository's existing language, framework, formatter, naming, and comment conventions.
- Uses blank lines to separate unlike ideas while keeping related statements, declarations, and setup close together.
- Orders declarations, fields, constructors, helpers, and tests in a way that matches nearby code and creates a natural reading path.
- Breaks long lines at meaningful boundaries instead of forcing horizontal scrolling or dense wrapping.
- Keeps chained calls, literals, conditionals, and parameter lists shaped consistently with nearby code.
- Comments all structs, classes, fields, exported members, and tricky code sections when the repository expects documentation or when purpose is not obvious from names.
- Explains invariants, ownership, units, concurrency expectations, lifecycle, generated data, external contracts, and surprising control flow.
- Avoids comments that restate obvious code, preserve prompt history, or compensate for poor naming.
- Uses spacing inside functions to group setup, validation, main work, side effects, and return handling without creating decorative gaps.
- Keeps indentation and nesting visually calm; prefer guard clauses or small local helpers when they make the scan path cleaner.
- Leaves tests, fixtures, and examples with the same visual polish as production code.

## Visual Friction Smells

Flag code where:

- A file looks like one unbroken block of text.
- Blank lines split a single idea or merge unrelated ideas.
- Similar declarations use different shapes without a local reason.
- Comment coverage is uneven across adjacent structs, classes, fields, or tricky branches.
- A line is long because it combines multiple decisions, transformations, or side effects.
- A reader must repeatedly scan far up or down to connect a value with its use.
- Dense literals, tables, or test cases would be clearer with aligned grouping or named intermediate values.
- A cleanup would be purely mechanical and should be handled by the formatter instead of manual taste edits.

## Output Contract

Lead with findings ordered by impact:

- `P1`: Visual or documentation issue likely to hide incorrect behavior or misuse.
- `P2`: Readability issue likely to slow future maintainers or reviewers.
- `P3`: Polish issue worth fixing when touching the code.

Each finding must include a file and line reference, the visual readability problem, why it interrupts scanning or maintainability, evidence inspected, and a concrete edit direction.

If there are no meaningful issues, say so clearly, name the scope inspected, and report validation run or validation still needed. Avoid vague "looks good" answers without naming what was checked.
