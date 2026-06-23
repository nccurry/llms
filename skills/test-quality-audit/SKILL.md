---
name: test-quality-audit
description: Audit unit, integration, and end-to-end test suites for meaningful behavior coverage, assertion quality, tautological or no-op tests, framework ergonomics, flaky risk, and confidence that passing tests imply the code works. Use when the user asks to review tests, improve coverage, validate testing strategy, check unit or e2e tests, find weak tests, or assess whether tests are elegant, idiomatic, intuitive, and trustworthy.
---

# Test Quality Audit

## Workflow

1. Identify the review scope from the user's request. If the scope is not explicit, inspect `git status`, `git diff --stat`, changed files, and conventional test directories.
2. Read local project instructions, test runner configuration, project/package files, CI, and nearby test patterns before judging style.
3. Map important production behavior to tests. Focus on business rules, edge cases, error paths, integration boundaries, persistence, concurrency, user-visible workflows, and prior bug fixes.
4. Read representative unit, integration, and e2e tests deeply enough to understand what behavior each test proves.
5. Run focused tests or coverage commands when practical and relevant. Treat coverage numbers as leads, not proof.
6. Report concrete findings first, ordered by severity, with file and line references.
7. If the user asked to fix tests, make the smallest changes that turn weak or missing coverage into meaningful behavioral checks, then run focused validation.

## Routing Boundaries

- Use this skill for test suite quality, assertion quality, flaky risk, framework ergonomics, and confidence that tests prove behavior.
- Use `audit-tests` when checking recent code changes for missing test coverage in a branch, diff, PR, or commit range.
- Use `code-quality-audit` when production code quality is the main concern.

## Meaningful Test Criteria

Check whether tests:

- Prove observable behavior rather than implementation details.
- Assert outcomes that would fail if the feature were broken.
- Cover success paths, failure paths, boundaries, invalid input, state transitions, lifecycle behavior, and regressions.
- Exercise critical paths at the right level: unit tests for local rules, integration tests for contracts between components, and e2e tests for real user flows.
- Use realistic fixtures and data without hiding important setup behind opaque helpers.
- Avoid over-mocking the collaborators needed to prove the behavior works.
- Verify side effects such as persisted state, emitted events, rendered UI, file output, network calls, or error messages when those side effects are the point.
- Remain deterministic, isolated, and fast enough for their role in the suite.

## Weak Test Smells

Flag tests that:

- Have no assertions or only assert that code does not throw without making that intent explicit.
- Assert the mock was called after arranging the implementation to call the mock, without checking user-visible behavior.
- Recompute the expected value with the same code path being tested.
- Assert constants, object construction, snapshots, or default values without exercising behavior.
- Only verify that a component renders, an object is not null, or a collection has any items when the requirement is more specific.
- Depend on sleeps, real time, random order, network availability, shared mutable state, or test execution order.
- Are broad e2e scripts that click through screens but do not prove the critical result.
- Duplicate lower-level tests without adding confidence at a higher level.
- Lock in incidental implementation details, making refactors risky without protecting behavior.

## Output Contract

Lead with findings ordered by impact:

- `P1`: Test weakness likely to miss a serious regression, produce false confidence, or cause damaging flake.
- `P2`: Missing or weak behavioral coverage for important code.
- `P3`: Assertion, fixture, naming, organization, or ergonomics issue worth improving.

Each finding must include file and line references, what the current test proves, what it fails to prove, evidence inspected, and a concrete test improvement.

If no meaningful issues are found, say so clearly, name the tests inspected, and mention residual risk. Report validation performed or validation still needed.
