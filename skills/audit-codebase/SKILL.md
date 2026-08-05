---
name: audit-codebase
description: Run the complete code craftsmanship gate across current changes and affected structure. Use when the user says "run all audit skills" or "run the audits before continuing." Also use for a full code audit or craftsmanship pass. This skill combines structure, correctness, code quality, visual clarity, dead code, tests, and performance.
---

# Audit Codebase

## Workflow

1. Decide whether the request is audit-only or part of an authorized implementation task.
2. Select one scope for all specialist audits.
3. Read local repository instructions before you inspect code.
4. Resolve every required specialist from the active skill catalog.
5. Read each specialist's current `SKILL.md` completely. Do not use a `.backup-*` copy.
6. Apply the specialists in the order below.
7. Merge duplicate findings under the specialist that owns the concern.
8. Return one verdict for the complete gate.
9. If fixes are authorized, correct in-scope findings and rerun the gate.

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
2. `correctness-reliability-audit`: behavior, state, errors, lifecycle, concurrency, and recovery.
3. `code-quality-audit`: idiom, cohesion, control flow, necessity, and maintainability.
4. `visual-code-audit`: scan path, whitespace, comments, indentation, and line shape.
5. `dead-code-audit`: unused or obsolete code that can be removed safely.
6. `audit-tests`: missing coverage for the selected change.
7. `test-quality-audit`: weak assertions, poor test design, and flaky risk.
8. `performance-audit`: measurable or strongly evidenced runtime and resource costs.

If a required specialist is unavailable, return `INCOMPLETE`. Name the missing skill and do not claim a complete audit.

Dependency and application-security audits are not part of this gate. Run them only through their separate skills.

## Finding Ownership

- Assign each finding to one specialist.
- Merge supporting evidence from other specialists into that finding.
- Keep the highest severity that the evidence supports.
- Use high confidence for direct evidence.
- Use medium confidence for a strong inference from the inspected path.
- Put low-confidence candidates under blind spots. Do not block the gate on them.
- Require every P3 finding to cite a user, repository, language, or framework standard.
- Omit taste-only preferences.

## Authorization

Treat an audit-only request as read-only.

When the gate is part of authorized implementation work, fix findings inside the approved scope. Use the smallest coherent change that produces the right design. Rewrite the affected subsystem when a local edit preserves the wrong boundary.

Request direction before you change:

- A public API or wire contract.
- A schema or migration.
- An unrelated subsystem.
- User-visible behavior outside the authorized task.

## Output Contract

Return one verdict:

- `PASS`: No actionable findings remain.
- `REWORK REQUIRED`: At least one high-confidence or medium-confidence P1, P2, or P3 finding remains.
- `INCOMPLETE`: A required skill, tool, scope, or validation step was unavailable.

For each finding, include severity, confidence, a tight file and line reference, evidence, impact, and a concrete correction. Report validation results and blind spots.
