---
name: abstraction-quality-audit
description: Review code structure, naming, responsibility boundaries, dependency direction, and abstraction complexity. Use when evaluating whether code is too abstract, over-layered, poorly named, hard to trace, misplaced, or organized around vague Manager, Service, Helper, Handler, or Processor concepts instead of real ownership.
---

# Abstraction Quality Audit

## Workflow

1. Identify the review scope from the user request. If the scope is not explicit, inspect `git status`, diffs, changed files, and nearby package or folder structure.
2. Read local repo instructions first, such as `AGENTS.md`, architecture notes, style guides, and nearby code patterns.
3. Trace at least one representative workflow from entry point to data access, UI, external call, or other side effect.
4. Inspect names across folders, files, types, methods, parameters, interfaces, and tests.
5. Look for abstractions whose cost is higher than the complexity, boundary, or duplication they remove.
6. Report concrete findings with tight file and line references.

## Routing Boundaries

- Use this skill for ownership, layering, naming, dependency direction, and indirection problems.
- Use `code-quality-audit` for broader idiom, control flow, readability, and maintainability review.
- Use `visual-code-audit` for spacing, comment coverage, line shape, and scan path polish.
- Use `dead-code-audit` when the main question is whether code can be removed.

## Review Criteria

Check whether the code:

- Uses abstractions to hide real complexity, enforce useful boundaries, or remove meaningful duplication.
- Avoids pass-through layers, unnecessary interfaces, wrappers, factories, registries, and helpers.
- Keeps behavior traceable without long chains of tiny methods that only restate each other.
- Prefers cohesive methods over splitting every small step into private methods.
- Uses names that describe real behavior and ownership, not vague roles like Manager, Handler, Processor, Service, or Helper.
- Places files and folders where maintainers would naturally look.
- Avoids god objects or modules with unrelated reasons to change.
- Keeps dependency direction clean; lower-level or domain code should not leak adapter, host, persistence, UI, or third-party concerns.
- Uses dependency injection, config, generics, inheritance, and composition only when they clearly pay for themselves.

## Red Flags

Flag designs where:

- One class or module coordinates many unrelated workflows.
- A change requires touching many files with similar edits.
- Names are broad enough to absorb almost anything.
- Methods mostly call through to the next method in a chain.
- Interfaces have one implementation and no clear boundary or testing value.
- Folder structure hides the domain or user-facing capability.
- Tests know too much about internal orchestration.
- Abstractions appear before multiple concrete use cases exist.

## Output Contract

Lead with findings ordered by impact:

- `P1`: Risk likely to cause incorrect behavior, unsafe coupling, or blocked change.
- `P2`: Maintainability issue likely to make future work harder.
- `P3`: Naming, organization, or simplification issue worth cleaning up.

Each finding must include a file and line reference, the problem, why it costs more than it buys, the evidence inspected, and a concrete simplification, rename, or move direction.

If no meaningful issues are found, say so clearly, name the scope inspected, and mention any blind spots. Report validation run or validation still needed.

## Cleanup Guidance

When fixing issues, make the smallest change that reduces real complexity. Delete pass-through layers before adding new structure. Rename things for current behavior, not future intent. Move files only when ownership becomes easier to predict. Update tests when names, layout, or behavior change.
