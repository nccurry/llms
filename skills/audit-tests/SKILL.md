---
name: audit-tests
description: Audit test coverage for recent code changes. Use when checking a branch, diff, PR, commit, or recent implementation for missing unit, integration, or e2e tests and concrete coverage gaps.
---

# Audit Test Coverage

## Workflow

1. Identify the comparison scope. Prefer a user-provided base branch, PR base, or commit range. If none is provided, detect the likely base from `git merge-base`, upstream tracking, `main`, `master`, or repository docs, and state the choice.
2. Read local instructions and test docs first, such as `AGENTS.md`, README, CI config, Taskfile, Makefile, package manifests, and nearby test patterns.
3. Diff the selected range with stat and full context. Identify changed production files, changed test files, and behavior implied by the change.
4. For each changed code path, catalog new or modified functions, methods, branches, error paths, integrations, commands, UI flows, and persistence or side effects.
5. Find relevant existing tests by colocated test files, conventional test directories, e2e suites, snapshots, fixtures, and references to changed symbols or user-facing behavior.
6. Assess whether tests cover the specific change, not just pre-existing behavior.
7. Run focused tests when practical. Discover commands from project conventions instead of assuming `task test:*`; use the narrowest relevant unit, integration, e2e, lint, typecheck, or build commands available.
8. Report gaps with concrete test recommendations.

## Routing Boundaries

- Use this skill for coverage of recent changes in a diff, branch, PR, or commit range.
- Use `test-quality-audit` when reviewing whether an existing test suite is meaningful, trustworthy, flaky, or overfit.
- Use `code-quality-audit` when the main question is code maintainability rather than missing tests.

## Coverage Criteria

Check whether tests:

- Exercise the changed happy path and important failure, boundary, and invalid-input paths.
- Verify the user-visible behavior, API contract, persistence, emitted events, rendered output, or other side effects that the change is meant to create.
- Cover changed integration boundaries such as files, databases, network calls, queues, CLIs, UI flows, and external services.
- Include regression coverage for fixed bugs.
- Use meaningful assertions that would fail if the changed behavior broke.
- Avoid only proving that a mock was called, an object exists, or no exception occurred unless that is the intended contract.

## Output Contract

Lead with findings ordered by impact:

- `P1`: Missing test coverage for behavior with high regression, data loss, security, or user-visible risk.
- `P2`: Missing unit, integration, or e2e coverage for important changed behavior.
- `P3`: Smaller coverage gaps, weak assertions, or test organization improvements.

Include a compact table when useful:

| Changed Code | Existing Test | Gap | Recommended Test |
|---|---|---|---|

Each recommendation must include a test name, what it validates, and key assertions. State the base range, commands run, results, and any test discovery blind spots.

If no meaningful gaps are found, say so clearly, name the changed areas inspected, and report validation run or validation still needed.
