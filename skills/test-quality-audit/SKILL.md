---
name: test-quality-audit
description: Audit an existing test suite for trustworthy behavior checks, meaningful assertions, realistic fixtures, appropriate isolation, and flaky risk. Use when the main question is whether passing tests prove that the code works. Use audit-tests for recent-diff coverage.
---

# Test Quality Audit

## Workflow

1. Identify the test suite or feature area from the user request.
2. Read local instructions, test-runner configuration, CI files, and nearby test patterns.
3. Map important production behavior to the tests that claim to prove it.
4. Read representative unit, integration, and end-to-end tests in full.
5. Run focused tests or coverage commands when useful.
6. Treat coverage percentages as leads, not proof.
7. Report concrete weaknesses before general strategy advice.

## Routing Boundaries

- Use this skill for assertion quality, realistic behavior coverage, fixture design, over-mocking, isolation, and flaky risk.
- Use `audit-tests` for missing coverage in a branch, diff, commit, or active implementation.
- Use `correctness-reliability-audit` for defects in production behavior.
- Use `performance-audit` for benchmark quality or performance-regression checks.

## Meaningful-Test Criteria

Check whether tests:

- Prove observable behavior instead of implementation details.
- Use assertions that fail when the feature breaks.
- Cover state transitions, failures, boundaries, invalid input, lifecycle, and regressions.
- Exercise each contract at the correct test level.
- Use realistic fixtures without hiding important setup behind opaque helpers.
- Avoid mocking the collaborators needed to prove that the behavior works.
- Verify persistence, events, rendered UI, files, network effects, or errors when those effects are the contract.
- Remain deterministic, isolated, and fast enough for their suite.

## Weak-Test Smells

Flag tests that:

- Have no assertion or only prove that code did not throw.
- Assert a mock call without checking the intended result.
- Recompute the expected value with the implementation's algorithm.
- Assert constants, construction, snapshots, or non-null values without proving behavior.
- Depend on sleeps, wall-clock time, random order, live networks, shared state, or execution order.
- Click through an end-to-end flow without proving the critical result.
- Duplicate lower-level tests without adding confidence.
- Lock in incidental implementation details.

## Output Contract

Lead with findings in impact order:

- `P1`: A weak test creates serious false confidence or damaging flaky behavior.
- `P2`: An important behavior has weak or misleading proof.
- `P3`: A concrete assertion, fixture, naming, or organization defect violates an established standard.

Use high confidence for direct evidence. Use medium confidence for a strong inference from the test and production path. Put low-confidence candidates under blind spots.

For each finding, include severity, confidence, the test location, what it proves, what it misses, evidence, impact, and a concrete correction. For P3 findings, cite the governing user, repository, language, or framework standard.

If no actionable findings exist, say so. Name the tests, production paths, and validation results.

When `audit-codebase` invokes this skill, return scoped findings and validation evidence to the orchestrator. Do not choose the aggregate verdict or expand its scope.
