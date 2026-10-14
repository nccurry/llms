---
name: audit-codebase
description: Run the combined code audit when asked for all audit skills, a full code audit, or a craftsmanship pass. Delegate focused specialist reviews and combine their findings and evidence.
---

# Audit Codebase

## Scope and preparation

Decide whether this is a read-only audit or part of authorized implementation.
Use the user's target; otherwise use the active changes and affected dependencies,
then the branch diff against its detected base. Audit the full repository only
when explicitly requested. Inspect root and relevant ancestor instructions and
folders to judge ownership and local standards. Audit-only does not authorize
merging, rebasing, cleanup, or edits.

Choose one comparison base and stabilize the source before review. Record the
commit and any uncommitted diff with an identifier that detects later changes.
Pause writers during each review wave. All specialists review that same source,
base, scope, and applicable instructions; a report on a different revision is
not evidence for this gate.

## Specialist selection

Assess every domain below. Required coverage comes from the scope, affected
behavior, repository instructions, and explicit user requests. Record `not
applicable` with a concrete reason when a domain has no relevant concern. Missing
evidence is `INCOMPLETE`, never `not applicable`.

1. `abstraction-quality-audit`: ownership, file-tree structure, boundaries,
   modularity, and whether unrelated changes can proceed independently.
2. `file-hygiene-audit`: temporary artifacts, misplaced files, repository file
   policy, and safe cleanup candidates.
3. `plain-language-audit`: unclear prose, terminology, and conventional names.
4. `correctness-reliability-audit`: behavior, state, errors, lifecycle,
   concurrency, and recovery.
5. `code-quality-audit`: idiom, cohesion, control flow, and maintainability.
6. `ponytail-review`, or `ponytail-audit` for explicitly full-repository scope:
   connected behavior, security, failure under load, risky coverage, unnecessary
   complexity, and simpler replacements.
7. `visual-code-audit`: scan path, whitespace, comments, and line shape.
8. `dead-code-audit`: provably unused or obsolete code.
9. `audit-tests`: missing coverage for the selected change.
10. `test-quality-audit`: weak assertions, unrealistic fixtures, and flaky risk.
11. `performance-audit`: measured or strongly evidenced runtime/resource costs.
12. `plc-alignment-audit`: completed work against the PLC or plan guiding this
    session; otherwise record why it does not apply.
13. `docs-sync`: maintained documentation affected by the work.
14. `application-security-review`: when the scope touches trust boundaries,
    authorization, untrusted input, secrets, execution, or sensitive data.

Read each applicable specialist's current `SKILL.md` completely. Resolve bare
Ponytail skill names first; use a plugin-qualified name only when that is how
the installed environment exposes the same skill. Never use backup copies.
An unavailable required specialist makes the audit `INCOMPLETE`.

Run `dependency-auditor` for relevant dependency risk and
`frontend-design-review` for rendered UI when requested or required by the work.
Record these extra gates in the same ledger.

## Focused independent reviewers

The parent coordinates one read-only subagent per required specialist. Each
reviewer applies only its assigned specialist, reads connected code as needed,
and returns evidence to the parent. Do not ask one child to perform all audits.
Use waves of at most three reviewers, reduced to the available slots. Wait for
implementation children to yield slots rather than creating recursive teams.

Give each reviewer the exact checkout, base, revision/diff identifier, scope,
local instructions, specialist path, and concrete failure questions. Do not
give it the desired verdict or earlier findings before its initial inspection.
Forbid edits, commits, cleanup, further delegation, and expensive overlapping
builds. The parent owns test/build scheduling, fixes, and integration. Reviewers
may request a necessary check; a source-only review must not claim it ran.

If delegation is unavailable, continue useful local inspection and report the
independent reviews as `INCOMPLETE`. Do not call several skills used by one agent
independent reviewers. Preserve explicit model choices from the invoking
workflow; otherwise inherit the current settings.

## Evidence and findings

Use one parent-owned ledger. For each domain, record reviewer, scope, revision,
applicability, method, evidence, and result. Distinguish source inspection from
tests, lint, build, rendered review, and integration runs. Reuse prior evidence
only after checking that intervening changes do not invalidate it.

The parent checks findings against current source before accepting them. Give
each accepted finding one ID, original finder, owning specialist, severity,
confidence, tight file/line reference, impact, correction, and fix/verification
reference. Preserve discovery credit when merging duplicates. Completing a
requirement is acceptance evidence, not an audit discovery.

- Use high confidence for direct evidence and medium for a strong inspected
  inference. Put low-confidence candidates under blind spots.
- Require P3 findings to cite a governing user, repository, language, or
  framework standard. Omit taste-only preferences.
- Route duplicate Ponytail findings to the owning domain. Require simpler
  replacements to preserve needed behavior; one caller or fewer lines alone
  does not prove an abstraction unnecessary. Reachability belongs to dead-code
  review. A standalone Ponytail verdict does not establish this aggregate gate.
- Keep existing debt outside the selected change as a separate follow-up unless
  the change adds/worsens it or it makes the selected behavior unsafe.
  When required acceptance relies on a delegated repair, record its owner and
  tracking reference; do not claim a handoff without acknowledgement.

## Strict fixes and bounded verification

During authorized implementation, fix every supported actionable finding within
scope, including P3. Recording a finding as a follow-up does not satisfy this
gate. Reject unsupported findings with evidence. A fix needing new scope or a
material unresolved decision stays open until the parent resolves it with the
user; continue independent repairs meanwhile.

Audit-only remains read-only. File cleanup needs express cleanup authority and
the safeguards in `file-hygiene-audit`; an ordinary fix request does not grant
it. Use host trash/recycle bin, never permanent deletion, and report every
candidate's outcome.

After grouped fixes, rerun affected specialists and relevant checks against the
new stabilized revision. Keep valid unaffected evidence. Reserve aggregate
review for a meaningful block or phase boundary, not every tiny correction.
Perform one initial aggregate pass and at most one final aggregate verification:

- Rerun the full suite only when fixes materially change architecture, public
  contracts, persistence, concurrency, navigation/lifecycle, or several domains.
- Otherwise refresh invalidated reviews/checks and form the final ledger verdict.
- If no fixes followed the initial pass, use it as final evidence.
- Inspect an authorized integration-base update and refresh only evidence it
  invalidates. Do not switch branches merely to inspect source.
- Documentation that only records evidence does not invalidate unrelated code
  or runtime checks.

If findings or required checks remain after final verification, report their
exact state and resolve the remaining repair or decision. Do not launch another
aggregate cycle without new work or evidence. Ask before changing contracts,
stored data, unrelated subsystems, or behavior beyond the authorized task.

## Report

Report source review, automated checks, integration, and plan acceptance
separately, with evidence: passed, failed, incomplete, or not applicable.
Choose one overall verdict:

- `PASS`: no actionable in-scope findings remain and all required gates passed.
- `REWORK REQUIRED`: at least one supported actionable in-scope finding remains.
- `INCOMPLETE`: a required review, check, or acceptance step is unavailable or pending.

Missing required evidence prevents `PASS` even when inspection found no defect.
A user's bounded integration exception changes the permitted action, not the
observed failed/incomplete check. State both separately and retain the exact
scope; do not use the exception as proof that the originating behavior is correct.
List fixed/open findings, outside-scope follow-ups, blind spots, checks run, and
reviews refreshed with reasons. Include cleanup outcomes when applicable. Keep
one concise report rather than concatenating each reviewer's output.
