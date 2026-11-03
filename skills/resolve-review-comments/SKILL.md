---
name: resolve-review-comments
description: "Resolves code review feedback on pull requests, merge requests, and equivalent changes on any host. Use when asked to handle review comments, fix valid findings, or reply and resolve discussions. Leave human threads open."
---

# Resolve Review Comments

Handle feedback on GitHub, GitLab, Bitbucket, Azure DevOps, Gerrit, or another code review system, including mixed batches and self-hosted services. Choose tools from the actual host and available capabilities. Do not assume a company, hostname, connector, CLI, or GitLab-specific ID or discussion format. If a host operation is unavailable, report that limit and continue work that its available tools can support.

## Workflow

1. **Choose the batch.** Accept review URLs, IDs with repository context, or a clearly specified group. Identify each review's host from its URL or repository remote configuration. Process every requested review; ask only when the target set is unclear. Track each review's host, repository, branch or change, and threads separately. Keep fixes in the correct review; use separate checkouts, such as Git worktrees, when needed.
2. **Read the feedback.** Use each host's available tools, CLI, or API to fetch the review details, current diff, and all pages of comments and replies in scope. Include review summaries and file comments, not just resolvable threads. Read relevant code, consumers, tests, and repository instructions. Skip system events and already handled feedback. For AI-only requests, leave human feedback untouched.
3. **Check each claim.** Confirm the concern against current source before accepting its proposed repair. Record each decision separately from its completion status, using the guidance below. An outdated comment is not proof of a fix. Leave valid issues that cannot be addressed open, explain the blocker, and continue through the batch.
4. **Make and verify fixes.** Apply the relevant audit skills below before editing and when checking the repair diff. Follow each repository's required checks and review workflow. Before claiming completion or resolving a fixed issue, ensure the reviewed branch or change contains the verified fix. After publishing fixes, use `create-mr-description` to refresh affected behavior and validation within the existing update authorization. If publishing is blocked or unauthorized, report the local fix and leave the thread open.
5. **Reply briefly.** Address every actionable point. Explain what changed and how it was checked, or why no change is needed, in plain English. Link supporting code or commits where useful. A request to reply and resolve authorizes those actions for the batch; an assessment-only request does not. Respect existing authorization without asking again.
6. **Resolve AI threads only.** Identify AI authors through account metadata or known integrations, never writing style. Resolve only after the reply is confirmed and every point is handled. Leave human and uncertain-author threads open, including AI-started threads with outstanding human questions or objections. Your own reply does not count as human review.
7. **Check before writing.** Refresh threads before replying or resolving to catch new feedback and avoid duplicate replies. Read back uncertain writes before retrying, and verify resolution. Report unsupported resolution actions or access failures and continue with other reviews.
8. **Summarize the batch.** Give one linked row per review with fixes, rejected suggestions, checks, resolved threads, and remaining human or blocked threads. Account for each handled comment or actionable point with a link or host-provided ID, decision, status, change or rejection reason, and validation evidence. Group shared fixes and checks without losing comment references. Finish the batch without starting an ongoing monitor.

## Decisions and completion

Use `good catch` for a demonstrated bug, risk, or worthwhile improvement;
`will not fix` for an intentionally rejected suggestion; and `it's not an issue`
when the current behavior is correct or the claim is mistaken. Support each
decision with source evidence or a concrete design reason. Duplicate and already
fixed comments can share an explanation and fix reference.

Keep acceptance separate from progress. A valid concern can still be blocked.
State whether a fix is local or published and whether required validation passed,
failed, or remains pending. Record replies and resolution separately; a closed
thread alone does not prove that the code is fixed.

Use engineering judgment for routine implementation choices. Ask when a material
product decision, conflicting requirement, public contract or schema change, or
scope expansion needs direction not already covered by the user's request.
Continue independent fixes meanwhile.

## Apply audit standards

Read the current `SKILL.md` for each applicable audit before designing the repair.
Use its criteria during implementation and when inspecting the final diff. Keep
the scope to the requested feedback, affected paths, and problems the repair adds
or worsens. Use these maintained skills rather than copying their checklists here.

| Concern in the repair | Skills to apply |
|---|---|
| Implementation idiom, cohesion, control flow, and comments | [code-quality-audit](../code-quality-audit/SKILL.md) |
| Behavior, errors, state, resource lifetime, retries, or concurrency | [correctness-reliability-audit](../correctness-reliability-audit/SKILL.md) |
| Ownership, module boundaries, dependencies, or added abstractions | [abstraction-quality-audit](../abstraction-quality-audit/SKILL.md) |
| Changed behavior and regression coverage | [audit-tests](../audit-tests/SKILL.md) |
| Tests added, changed, or relied on as proof | [test-quality-audit](../test-quality-audit/SKILL.md) |
| Names, prose, and source readability | [plain-language-audit](../plain-language-audit/SKILL.md), [visual-code-audit](../visual-code-audit/SKILL.md) |
| Trust boundaries, authorization, untrusted input, execution, secrets, or sensitive data | [application-security-review](../application-security-review/SKILL.md) |
| Runtime or resource cost | [performance-audit](../performance-audit/SKILL.md) |
| Removal of unused or obsolete code | [dead-code-audit](../dead-code-audit/SKILL.md) |
| Maintained documentation affected by the repair | [docs-sync](../docs-sync/SKILL.md) |
| Dependency changes | [dependency-auditor](../dependency-auditor/SKILL.md) |
| Rendered UI behavior or appearance | [frontend-design-review](../frontend-design-review/SKILL.md) |

Make the smallest coherent repair that restores the complete contract. Avoid
patches that preserve the root defect, speculative abstractions, taste-only
changes, and unrelated cleanup. Report unrelated debt separately.

After grouped fixes, inspect the repair diff and run required repository checks
and focused validation of the changed behavior. For corrected behavior defects,
add regression coverage that reaches the failing path and asserts the observable
result. Choose the lowest-cost test level that proves the contract. Mechanical
wording or formatting changes do not need tests that mirror the edited text.

Fix supported in-scope problems found in the repairs. Verify those corrections
with direct inspection and relevant checks. Invoke [audit-codebase](../audit-codebase/SKILL.md)
only when a combined audit is requested or required by repository instructions;
follow its specialist selection, delegation, and repeat-audit limits.

Use [verify-before-claiming](../verify-before-claiming/SKILL.md) before reporting
completion. Tie check results to the tested revision or local diff. Distinguish
inspection from executed tests and CI. If a required skill or check is unavailable,
name the missing evidence and leave the affected validation pending.
