---
name: code-quality-audit
description: Audit recent or proposed code for idiomatic style, simplicity, clear comments, intuitive structure, unnecessary abstractions, excessive call chains, deep nesting, and maintainability. Use when the user asks whether delivered code is clean, elegant, intuitive, over-engineered, idiomatic for the project language/framework, or ready to continue building on.
---

# Code Quality Audit

## Workflow

1. Identify the review scope from the user's request. If the scope is not explicit, inspect `git status`, `git diff --stat`, and changed files.
2. Read local project instructions first, such as `AGENTS.md`, style guides, formatter or lint config, and nearby code patterns.
3. Read each changed file with enough surrounding context to understand the design, not just the edited lines.
4. Judge the code against concrete quality signals. Prefer specific findings over broad taste statements.
5. If the user asked for a review, lead with findings ordered by severity and cite file/line references.
6. If the user asked to fix issues, make the smallest cleanup that improves readability or correctness, then run focused validation.

## Routing Boundaries

- Use this skill for broad code quality, idiom, readability, control flow, maintainability, and comments.
- Use `abstraction-quality-audit` when ownership, layering, naming, dependency direction, or indirection is the central concern.
- Use `visual-code-audit` when the request is mainly about visual polish, spacing, line shape, and scan path.
- Use `test-quality-audit` when the request is mainly about test design quality.

## Review Criteria

Check whether the code:

- Follows the language, framework, and repository idioms already in use.
- Solves the problem with the least useful amount of code and abstraction.
- Keeps control flow easy to scan, using guard clauses or early exits when they reduce nesting.
- Avoids wrapper methods, helper classes, service layers, or indirection that do not remove real complexity.
- Avoids "function calls function calls function" designs where behavior becomes harder to trace than the original logic.
- Uses names that make the code readable without explanatory comments.
- Keeps comments concise and factual; remove comments that explain prompt history, obvious code, or intent already clear from names.
- Uses straightforward loops and conditionals when they are clearer than complex fluent or query chains.
- Keeps methods cohesive without splitting every small step into a separate private method.
- Keeps data structures, state ownership, errors, nullability, lifecycle, and edge cases obvious and consistent with nearby code.
- Has tests or manual validation appropriate to the risk of the change.

## C# And Game Code Notes

When reviewing C# game code:

- Prefer idiomatic modern C# that remains readable to the project team.
- Avoid clever allocation-heavy patterns in hot update paths.
- Prefer `for` or `foreach` loops over complex LINQ in gameplay code.
- Keep MonoGame lifecycle methods, draw/update code, and asset ownership easy to follow.
- In Friflo ECS query loops, flag structural changes or callbacks that may cause structural changes during `ForEachEntity`; collect work during the query and apply it after the loop.

## Output Contract

Lead with findings ordered by impact:

- `P1`: Risk likely to cause incorrect behavior, data loss, unsafe behavior, or blocked work.
- `P2`: Maintainability issue likely to make future work harder.
- `P3`: Readability, naming, comment, or simplification issue worth cleaning up.

Each finding must include a tight file and line reference, the concrete issue, why it matters, evidence inspected, and a specific edit direction.

If no meaningful issues are found, say so clearly, name the scope inspected, and mention residual test or design risk. Report validation performed or validation still needed.
