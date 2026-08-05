---
name: dead-code-audit
description: Audit code for unused symbols, obsolete paths, replaced abstractions, test-only production code, unreachable branches, and stale flags. Use when the user asks what code is dead, obsolete, or safe to delete.
---

# Dead Code Audit

## Workflow

1. Identify the audit scope from the user request or current changes.
2. Read local instructions, build configuration, runtime wiring, generated-code rules, and nearby tests.
3. Build a reference map from production entry points.
4. Separate production references from tests, fixtures, generated code, migrations, plugins, reflection, routing, and configuration.
5. Trace each candidate far enough to establish deletion confidence.
6. Prefer a short list of proven removals over broad speculation.
7. If deletion is authorized, remove the smallest coherent obsolete slice and run focused validation.

## Routing Boundaries

- Use this skill when the main question is whether code can be removed safely.
- Use `abstraction-quality-audit` when used code has the wrong ownership or too much indirection.
- Use `code-quality-audit` when a used function or class is unnecessary but not dead.
- Use `dependency-auditor` when dependency risk, versions, licenses, or advisories are the main concern.

## Evidence Criteria

Check for:

- Symbols, files, routes, commands, configuration keys, flags, or dependencies with no production references.
- Production code referenced only by tests, fixtures, mocks, snapshots, or examples.
- Replaced abstractions that remain after current production wiring moved to another path.
- Constructors, options, branches, enum values, or error paths that current wiring cannot reach.
- Duplicate implementations after one path became canonical.
- Scripts, assets, or generated files that no build, runtime, test, documentation, or package step uses.

## Safety Checks

Before deletion, account for:

- Reflection, dependency injection, serialization, framework routing, plugins, build tags, and generated registration.
- Public APIs, commands, migrations, schema compatibility, and external integrations.
- Runtime configuration, scheduled jobs, CI, deployment manifests, dashboards, alerts, and external documentation.
- Language conventions that create implicit references or import side effects.

If dynamic reachability is unresolved, label the item as a candidate. Name the missing evidence and do not call it dead.

## Output Contract

Lead with findings in impact order:

- `P1`: Obsolete code creates unsafe routing, fallback behavior, or material dependency risk.
- `P2`: Unused production code or a replaced abstraction creates meaningful maintenance cost.
- `P3`: A small stale helper, branch, option, test, script, or dependency has proven removal value.

Use high confidence for direct reference evidence. Use medium confidence when dynamic reachability is reasonably excluded. Put low-confidence candidates under blind spots.

For each finding, include tight locations, reference evidence, caveats, and a concrete removal or consolidation path.

If no actionable findings exist, say so. Name the areas and reachability mechanisms inspected.
