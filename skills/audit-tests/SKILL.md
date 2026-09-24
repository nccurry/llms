---
name: audit-tests
description: "Review a code change for missing test coverage. Use for a branch, diff, PR, or commit; use test-quality-audit to judge whether existing tests prove behavior."
---

# Audit Test Coverage

## Workflow

1. Use the base branch, pull-request base, or commit range that the user specified.
2. If no range is given, detect the likely base and state the choice.
3. Read local instructions, test documentation, CI files, manifests, and nearby test patterns.
4. Map each changed behavior and failure path to the test that protects it, the level of evidence (unit or real-component integration), and any remaining gap.
5. Inspect unit, integration, and end-to-end suites that can prove the change.
6. Run focused tests when practical.
7. Report concrete coverage gaps and exact test recommendations.

## Routing Boundaries

- Use this skill for missing coverage in a recent change.
- Use `test-quality-audit` for suite trustworthiness, weak assertions, over-mocking, or flaky risk. Share its assessment of tests relied on for coverage; link an ineffective-test finding instead of reporting the same issue again.
- Use `correctness-reliability-audit` for defects in the production behavior itself.
- Use `performance-audit` for missing benchmarks or performance-regression coverage.

## Coverage Criteria

Check whether tests:

- Exercise the changed success path and important failure, boundary, and invalid-input paths.
- Prove user-visible behavior, API contracts, persistence, events, rendered output, or other intended effects.
- Cover changed files, databases, network calls, queues, commands, UI flows, and external boundaries.
- Add regression coverage for corrected defects.
- Use assertions that fail when the changed behavior breaks.
- Avoid treating a mock call, non-null object, or lack of an exception as proof of a richer contract.

## Output Contract

Lead with findings in impact order:

- `P1`: Missing coverage leaves a high-risk behavior, data path, or user workflow unprotected.
- `P2`: Missing coverage affects important changed behavior.
- `P3`: A smaller changed contract lacks evidence required by repository practice.

Use high confidence when no relevant test reaches the changed path. Use medium confidence when existing coverage appears indirect. Put low-confidence candidates under blind spots.

For each finding, include severity, confidence, the changed location, existing tests inspected, evidence, impact, a concrete correction, proposed test name, and key assertions. For P3 findings, cite the governing user, repository, language, or framework standard.

State the comparison range, commands, results, and test-discovery blind spots. If no actionable gaps exist, say so.

When `audit-codebase` invokes this skill, return scoped findings and validation evidence to the orchestrator. Do not choose the aggregate verdict or expand its scope.
