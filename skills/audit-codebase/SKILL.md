---
name: audit-codebase
description: Run the complete code craftsmanship gate across current changes and affected structure. Use when the user says "run all audit skills" or "run the audits before continuing." Also use for a full code audit or craftsmanship pass. This skill combines structure, plain-language clarity, correctness, code quality, visual clarity, dead code, tests, and performance.
---

# Audit Codebase

## Workflow

1. Decide whether the request is audit-only or part of authorized implementation work.
2. Select one scope and comparison base for every specialist.
3. Read repository instructions and reconcile the work with current `main` when the workflow permits it.
4. Stabilize the diff before auditing. Do not run the aggregate gate while edits are still arriving.
5. Read each required specialist's current `SKILL.md` completely. Do not use a `.backup-*` copy.
6. Run the complete specialist suite once and record each gate's scope, findings, and validation evidence in a gate ledger.
7. Merge duplicate findings under the specialist that owns the concern and classify their disposition.
8. If fixes are authorized, fix blocking findings and rerun only the owning specialists and relevant tests during convergence.
9. Perform at most one final aggregate verification after fixes converge, using the rules below.
10. Return one verdict and the required report sections.

## Scope

Use the first available scope:

1. The target that the user specified.
2. Files changed by the active implementation, their affected dependencies, and their ancestor folders.
3. The branch diff against the detected base.
4. The full repository, only when the user explicitly requests it.

Always inspect the repository root and relevant ancestor folders. Use them to judge whether the file tree communicates ownership clearly.

## Required Specialists

Apply these skills in order:

1. `abstraction-quality-audit`: ownership, file-tree structure, boundaries, naming, and modularity.
2. `plain-language-audit`: word salad, vague prose, terminology, and conventional names.
3. `correctness-reliability-audit`: behavior, state, errors, lifecycle, concurrency, and recovery.
4. `code-quality-audit`: idiom, cohesion, control flow, necessity, and maintainability.
5. `visual-code-audit`: scan path, whitespace, comments, indentation, and line shape.
6. `dead-code-audit`: unused or obsolete code that can be removed safely.
7. `audit-tests`: missing coverage for the selected change.
8. `test-quality-audit`: weak assertions, poor test design, and flaky risk.
9. `performance-audit`: measurable or strongly evidenced runtime and resource costs.

If a required specialist is unavailable, return `INCOMPLETE`. Name the missing skill and do not claim a complete audit.

Dependency, application-security, and frontend-design audits are not part of this gate. Run them only through their separate skills.

## Finding Ownership and Disposition

- Assign each finding to one specialist and merge supporting evidence from other specialists into it.
- Keep the highest severity that the evidence supports.
- Use high confidence for direct evidence and medium confidence for a strong inference from the inspected path.
- Put low-confidence candidates under blind spots. Do not block the gate on them.
- Require every P3 finding to cite a user, repository, language, or framework standard. Omit taste-only preferences.
- Treat P1 and P2 findings as blocking.
- Treat a P3 as blocking only when it implies correctness or security risk, is trivial to fix, or the user explicitly requires zero findings.
- Treat other P3 findings as deferred follow-ups.

A trivial P3 fix must be localized, mechanical, and low risk. It must not change architecture, public contracts, persistence, concurrency, lifecycle, navigation, or multiple audit domains, and it must need only focused validation.

Explicit user instructions override this policy. Interpret `fix findings` as fixing blocking findings; do not interpret it as an implicit request to eliminate every P3 or rerun until perfect.

## Fixes and Verification

Treat an audit-only request as read-only.

When fixes are authorized, correct blocking findings inside the approved scope. After each fix, rerun only the specialist that owns the finding and the tests or checks that cover the changed behavior. Verification must confirm the fix and adjacent regressions without reopening the codebase or creating unrelated cleanup work.

After fixes converge, perform one final aggregate verification:

- Reuse valid evidence from unaffected gates in the ledger.
- Rerun the complete specialist suite only when a fix materially changes architecture, public contracts, persistence, concurrency, navigation or lifecycle, or multiple audit domains.
- Otherwise rerun only invalidated specialists and produce the aggregate verdict from the refreshed ledger.
- If no fixes followed the initial aggregate pass, use that pass as final evidence instead of repeating it.
- Reconcile with current `main` before final verification. If `main` changes afterward, inspect its delta and rerun only the gates and tests that the delta invalidates.
- Do not invalidate code, performance, frontend, or test evidence for documentation changes that only record audit evidence or follow-up work.

Default to at most one initial aggregate pass and one final aggregate verification. If blocking findings remain after final verification, report them and request direction. Do not start another aggregate audit automatically.

Request direction before a fix changes a public API or wire contract, a schema or migration, an unrelated subsystem, or user-visible behavior outside the authorized task.

## Output Contract

Return one verdict:

- `PASS`: No blocking findings or deferred follow-ups remain.
- `PASS WITH FOLLOW-UPS`: No blocking findings remain, but one or more nonblocking P3 findings were deferred.
- `REWORK REQUIRED`: At least one blocking finding remains.
- `INCOMPLETE`: A required skill, tool, scope, or validation step was unavailable.

Separate the final report into:

1. Blocking findings.
2. Fixed findings.
3. Deferred follow-ups.
4. Validation evidence.
5. Gates rerun and why.

For every finding, include severity, confidence, a tight file and line reference, evidence, impact, and a concrete correction. Report blind spots separately.
