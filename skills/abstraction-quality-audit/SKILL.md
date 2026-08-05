---
name: abstraction-quality-audit
description: Review file-tree structure, naming, ownership, responsibility boundaries, dependency direction, modularity, and abstraction cost. Use when code is hard to locate, trace, or change. Also use for vague catch-all types or folders.
---

# Abstraction Quality Audit

## Workflow

1. Identify the review scope from the user request or current changes.
2. Read local repository instructions and architecture guidance.
3. Inspect the repository root and every ancestor folder of the target files.
4. Decide whether each folder and file has a clear purpose and owner.
5. Trace one representative workflow from its entry point to its observable effect.
6. Inspect names across folders, files, types, methods, parameters, interfaces, and tests.
7. Compare each abstraction's cost with the complexity, boundary, or duplication that it removes.
8. Report concrete findings with tight file and line references.

## Routing Boundaries

- Use this skill for ownership, file-tree structure, layering, naming, dependency direction, modularity, and indirection.
- Use `code-quality-audit` for idiom, cohesion, control flow, comments, and general maintainability.
- Use `visual-code-audit` for whitespace, line shape, comment placement, and scan path.
- Use `dead-code-audit` when the main question is whether code can be removed safely.
- Use `correctness-reliability-audit` when a boundary causes incorrect state or failure behavior.

## File-Tree Criteria

Check whether the structure:

- Makes the application's major capabilities visible at the repository root.
- Gives each folder one predictable purpose and ownership boundary.
- Places files where a maintainer will look for them first.
- Uses feature, domain, layer, or platform organization consistently.
- Avoids vague catch-all folders such as `Common`, `Utils`, `Helpers`, `Managers`, or `Services`.
- Keeps related implementation, contracts, and tests close when repository conventions allow it.
- Avoids directory depth that hides the user-facing capability.
- Uses standard language, framework, and design-pattern names instead of invented synonyms.

## Abstraction Criteria

Check whether the code:

- Uses abstractions to hide real complexity or enforce a useful boundary.
- Avoids pass-through layers, speculative interfaces, wrappers, factories, registries, and helpers.
- Keeps behavior traceable without long chains of small methods.
- Prefers cohesive units over fragmentation into one-use functions or classes.
- Gives each module one coherent reason to change.
- Keeps lower-level code independent from host, adapter, persistence, UI, and third-party details.
- Uses dependency injection, generics, inheritance, and composition only when their cost is justified.
- Treats modularity as clear ownership, not a high count of modules.

## Output Contract

Lead with findings in impact order:

- `P1`: The structure creates unsafe coupling, incorrect ownership, or a blocked change.
- `P2`: The structure makes important work hard to locate, trace, or modify.
- `P3`: A concrete naming, placement, or simplification defect violates an established standard.

Use high confidence for direct structural evidence. Use medium confidence for a strong inference from the traced workflow. Put low-confidence candidates under blind spots.

For each finding, include the file and line, evidence, cost, and a concrete rename, move, consolidation, or rewrite direction.

If no actionable findings exist, say so. Name the tree areas, workflows, and boundaries inspected.

## Correction Guidance

If fixes are authorized, make the smallest coherent change that produces the right ownership model. Rewrite the affected subsystem when local edits preserve the wrong boundary.

Request direction before a rewrite changes a public contract, schema, unrelated subsystem, or unauthorized user-visible behavior.
