---
name: correctness-reliability-audit
description: Audit code for behavioral correctness and reliable failure handling. Use when reviewing logic, invariants, state transitions, error paths, resource ownership, concurrency, idempotency, retries, timeouts, or recovery behavior.
---

# Correctness and Reliability Audit

## Workflow

1. Identify the review scope from the user request or current changes.
2. Read local instructions, contracts, schemas, and nearby tests.
3. Trace representative success and failure paths from their entry points to observable effects.
4. Identify the state, invariants, ownership, and lifecycle rules on each path.
5. Inspect boundary values, invalid inputs, partial failures, and repeated operations.
6. Run focused tests or static checks when they can confirm a finding.
7. Report only findings that have direct evidence or a strong path-based inference.

## Routing Boundaries

- Use this skill for behavioral validity, state, errors, lifecycle, concurrency, and recovery.
- Use `code-quality-audit` for idiom, cohesion, control flow, and maintainability.
- Use `abstraction-quality-audit` for ownership, layering, naming, and file-tree structure.
- Use `performance-audit` for runtime cost and resource efficiency.
- Use `audit-tests` for missing test coverage in a change.
- Use a security specialist for trust boundaries, authorization, injection, secrets, or cryptography.

## Audit Criteria

Check whether the code:

- Preserves its stated and implied invariants.
- Handles success, empty, boundary, invalid-input, cancellation, and failure paths.
- Makes state transitions legal, complete, and observable.
- Propagates, translates, or handles errors without hiding important failures.
- Owns and releases files, handles, connections, subscriptions, memory, and other resources correctly.
- Prevents races, unsafe shared state, deadlocks, lost updates, and invalid callback ordering.
- Makes repeated requests, retries, and recovery operations safe when the contract requires idempotency.
- Uses timeouts, retries, and fallback behavior without duplicate side effects or unbounded work.
- Preserves transactions and rollback behavior during partial failure.
- Keeps persisted state, emitted events, rendered output, and other observable effects consistent.

## Evidence Rules

- Use high confidence when execution, tests, or a complete path trace proves the defect.
- Use medium confidence when the inspected control flow strongly implies the defect.
- Put low-confidence candidates under blind spots and name the missing evidence.
- Do not report a style preference as a correctness finding.

## Output Contract

Lead with findings in impact order:

- `P1`: The defect can corrupt data, break a critical workflow, leak resources, or create unsafe behavior.
- `P2`: The defect can break an important edge case, failure path, or state transition.
- `P3`: The defect affects a smaller behavior or resilience contract that has clear evidence.

For each finding, include confidence, a tight file and line reference, the failing path, evidence, impact, and a concrete correction.

If no actionable findings exist, say so. Name the paths inspected, validation results, and blind spots.

## Correction Guidance

If fixes are authorized, make the smallest coherent change that restores the complete contract. Add a regression test for each corrected defect.

Request direction before a correction changes a public contract, schema, unrelated subsystem, or unauthorized user-visible behavior.
