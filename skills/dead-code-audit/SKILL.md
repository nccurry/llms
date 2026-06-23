---
name: dead-code-audit
description: Audit a codebase or recent changes for unused code, obsolete paths, replaced abstractions, test-only production code, unreachable branches, stale feature flags, and code that is no longer necessary given the current architecture. Use when the user asks to find dead code, remove unused code, identify obsolete abstractions, or check whether code is only exercised by tests.
---

# Dead Code Audit

## Workflow

1. Identify the audit scope from the user's request. If the scope is not explicit, inspect `git status`, `git diff --stat`, changed files, package/module layout, and likely entry points.
2. Read local project instructions, build configuration, routing or dependency wiring, generated-code conventions, and nearby tests before judging code as unused.
3. Build a call/reference map from production entry points outward. Use repository-native tools first, then `rg`, language servers, compiler diagnostics, coverage, or dependency graph commands where available.
4. Separate production references from test-only, fixture-only, generated, migration, plugin, reflection, serialization, CLI, routing, and configuration references.
5. Trace each suspect symbol, file, abstraction, branch, feature flag, endpoint, task, config option, and test helper far enough to distinguish truly unused code from dynamically reached code.
6. Rank findings by deletion confidence and maintenance cost. Prefer a short list of well-proven removals over broad speculation.
7. If the user asked for cleanup, delete the smallest safe slice, update tests/docs/config, then run focused validation and any broader suite justified by the blast radius.

## Routing Boundaries

- Use this skill when the primary question is whether code, tests, dependencies, flags, routes, or scripts can be removed.
- Use `abstraction-quality-audit` when an abstraction is still used but may be over-designed.
- Use `dependency-auditor` when dependency risk, updates, licenses, or advisories are the main concern.

## Evidence To Gather

Check for:

- No production references to a symbol, file, package, route, command, config key, feature flag, or dependency.
- Production code referenced only by unit tests, fixture builders, mocks, snapshots, examples, or old migration tests.
- Abstractions replaced by a clearer newer path, but left behind as pass-through wrappers, compatibility layers, or unused interfaces.
- Constructors, options, methods, branches, enum values, or error paths that can no longer be reached with current wiring.
- Feature flags, environment variables, CLI commands, routes, migrations, generated clients, or adapters whose owners and call sites disappeared.
- Duplicate implementations where one path is now canonical and the other has no distinct caller or behavior.
- Dependencies, scripts, assets, or generated files that are not used by build, runtime, tests, docs, or packaging.

## Safety Checks

Before recommending deletion, consider whether the code may be reached through:

- Reflection, dependency injection, serialization, framework routing, plugin loading, build tags, conditional compilation, or generated registration.
- Public APIs, exported packages, command-line interfaces, database migrations, schema compatibility, or external integrations.
- Runtime configuration, environment variables, cron jobs, CI jobs, deployment manifests, dashboards, alerts, or docs outside the immediate source tree.
- Language-specific conventions such as Go `init`, TypeScript barrel exports, Python module imports for side effects, C# attributes, or Java service loaders.

If dynamic reachability cannot be ruled out, label the finding as a candidate and name the missing evidence instead of asserting it is dead.

## Output Contract

Lead with findings ordered by confidence and impact:

- `P1`: Dead or obsolete code that creates real behavioral risk, confusing routing, unsafe fallback behavior, or dependency drag.
- `P2`: Unused production code or replaced abstraction that meaningfully increases maintenance cost.
- `P3`: Small stale helpers, branches, options, tests, docs, scripts, or dependencies worth pruning.

Each finding must include tight file and line references, what appears dead or obsolete, the evidence gathered, any caveat, and a concrete removal or consolidation path.

If no meaningful dead code is found, say so clearly, name the areas inspected, and mention any blind spots. Report validation run or validation still needed.
