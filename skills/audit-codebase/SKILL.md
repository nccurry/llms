---
name: audit-codebase
description: Run the combined code audit when asked for all audit skills, a full code audit, or a craftsmanship pass. Select applicable specialists and combine their findings and evidence.
---

# Audit Codebase

## Workflow

1. Decide whether the request is audit-only or part of authorized implementation work.
2. Select one scope and comparison base for every specialist.
3. Read repository instructions and record the selected comparison base. Inspect base changes when relevant; an audit-only request does not authorize merging or rebasing.
4. Stabilize the diff before auditing. Do not run the aggregate gate while edits are still arriving.
5. Assess each specialist’s applicability from the diff and affected behavior. Read each applicable specialist's current `SKILL.md` completely. Do not use a `.backup-*` copy.
6. Run the applicable specialists once and record their scope, findings, and evidence in one shared ledger.
7. Merge duplicate findings under the specialist that owns the concern and classify their disposition.
8. If fixes are authorized, fix blocking findings and rerun only the owning specialists and relevant tests during convergence.
9. Perform at most one final aggregate verification after fixes converge, using the rules below.
10. Report the overall verdict and separate results for source review, automated checks, integration, and plan acceptance.

## Scope

Use the first available scope:

1. The target that the user specified.
2. Files changed by the active implementation, their affected dependencies, and their ancestor folders.
3. The branch diff against the detected base.
4. The full repository, only when the user explicitly requests it.

Always inspect the repository root and relevant ancestor folders. Use them to judge whether the file tree communicates ownership clearly.

## Specialist Selection

Assess every skill below; run those relevant to the selected scope. Record `not applicable` with a reason when no relevant change or affected behavior exists. Missing evidence is `not checked` or `incomplete`, never `not applicable`. Honor explicit requests to inspect a particular area.

1. `abstraction-quality-audit`: ownership, file-tree structure, boundaries, naming, and modularity.
2. `file-hygiene-audit`: repository file policy, temporary artifacts, misplaced planning files, and safe cleanup candidates.
3. `plain-language-audit`: word salad, vague prose, terminology, and conventional names.
4. `correctness-reliability-audit`: behavior, state, errors, lifecycle, concurrency, and recovery.
5. `code-quality-audit`: idiom, cohesion, control flow, necessity, and maintainability.
6. `ponytail:ponytail-review` (or `ponytail:ponytail-audit` for an explicitly full-repository scope): unnecessary complexity, speculative abstractions, standard-library or native replacements, and deletable code.
7. `visual-code-audit`: scan path, whitespace, comments, indentation, and line shape.
8. `dead-code-audit`: unused or obsolete code that can be removed safely.
9. `audit-tests`: missing coverage for the selected change.
10. `test-quality-audit`: weak assertions, poor test design, and flaky risk.
11. `performance-audit`: measurable or strongly evidenced runtime and resource costs.
12. `plc-alignment-audit`: when this session is working from a PLC document or plan, check completed work against it and report missing or conflicting implementation. Otherwise record `not applicable`.
13. `docs-sync`: when changes affect documented behavior, examples, or generated documentation, check that maintained docs match the implementation.

If an applicable specialist is unavailable, return `INCOMPLETE`. Name the missing skill and do not claim a complete audit.

Treat the Ponytail specialist as a selected-scope gate. Use `ponytail:ponytail-review` for a target, active-change, or branch-diff scope; substitute `ponytail:ponytail-audit` for an explicitly full-repository scope. Capture its concise result in the gate ledger and fold its findings into this aggregate report rather than returning its standalone output directly.

For Ponytail findings, require a replacement that preserves required behavior. One caller or implementation alone does not prove an abstraction is unnecessary. Route reachability claims to `dead-code-audit`; do not use line-count savings or its standalone “Ship” wording as an audit verdict. These rules govern Ponytail use in this aggregate audit.

Dependency, application-security, and frontend-design audits are not part of this gate. Run them only through their separate skills.

## Shared Evidence

Use one ledger rather than separate reports from every specialist. Record the comparison base, reviewed revision, and any uncommitted changes (with a saved diff or equivalent identifier). Each result needs its scope, evidence location, and method: source inspection, test, lint, build, or integration run. Reuse older evidence only after checking that intervening changes do not invalidate it.

Give each finding one ID, original finder and discovery method, owning specialist, source revision, fix revision or pending diff, and verification reference. Merging duplicates must preserve discovery credit. Completing the assigned requirement is acceptance evidence, not an audit discovery.

Name who performed each review. Several skills applied by one agent are several review angles, not independent reviewers. When independent review is used, give the reviewer concrete failure questions tied to the change, such as whether an obsolete attempt can update a replacement device.

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

Treat an audit-only request as read-only. Apply `file-hygiene-audit` to relevant file changes; send files to trash or relocate them only when the user expressly authorizes file cleanup. A request to audit, report, or fix ordinary findings does not by itself authorize file cleanup. Cleanup must use the host trash or recycle bin, never permanent deletion, and the final report must list every affected file.

When fixes are authorized, correct blocking findings inside the approved scope. After each fix, rerun only the specialist that owns the finding and the tests or checks that cover the changed behavior. Verification must confirm the fix and adjacent regressions without reopening the codebase or creating unrelated cleanup work.

Reserve aggregate audits for a settled feature or meaningful phase boundary. Group small corrections and refresh only affected evidence: wording changes need language review; fixture fixes need test-quality review and the coverage evidence they affect. Do not start another full audit for each correction.

After fixes converge, perform one final aggregate verification:

- Reuse valid evidence from unaffected gates in the ledger.
- Rerun the complete specialist suite only when a fix materially changes architecture, public contracts, persistence, concurrency, navigation or lifecycle, or multiple audit domains.
- Otherwise rerun only invalidated specialists and produce the aggregate verdict from the refreshed ledger.
- If no fixes followed the initial aggregate pass, use that pass as final evidence instead of repeating it.
- Use the selected integration target or comparison base, which may differ from `main`. If authorized integration updates that base, inspect its delta and rerun only the gates and tests it invalidates. Do not change branches merely to perform a source review.
- Do not invalidate code, performance, frontend, or test evidence for documentation changes that only record audit evidence or follow-up work.

Default to at most one initial aggregate pass and one final aggregate verification. If blocking findings remain after final verification, report them and request direction. Do not start another aggregate audit automatically.

Request direction before a fix changes a public API or wire contract, a schema or migration, an unrelated subsystem, or user-visible behavior outside the authorized task.

## Output Contract

Report separate results for source review, automated checks, integration, and plan acceptance. For each, state passed, failed, pending/incomplete, or not applicable with supporting evidence or a reason. Source review does not establish formatter compliance or successful execution.

Then return one overall verdict; it cannot pass while an applicable required check or acceptance step remains pending:

- `PASS`: No blocking findings or deferred follow-ups remain.
- `PASS WITH FOLLOW-UPS`: No blocking findings remain, but one or more nonblocking P3 findings were deferred.
- `REWORK REQUIRED`: At least one blocking finding remains.
- `INCOMPLETE`: An applicable required review, validation, or acceptance step is pending or unavailable.

Keep one concise report, using brief applicability notes and omitting empty finding sections. Cover:

1. Blocking findings.
2. Fixed findings.
3. Deferred follow-ups.
4. Validation evidence.
5. Gates rerun and why.
6. File cleanup actions: each `file-hygiene-audit` candidate's outcome, including files retained, relocated, moved to trash, blocked, or left ambiguous.

For every finding, include severity, confidence, a tight file and line reference, evidence, impact, and a concrete correction. Report blind spots separately.
