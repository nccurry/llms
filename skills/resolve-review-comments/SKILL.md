---
name: resolve-review-comments
description: "Handle comments on one or more code reviews in GitLab, GitHub, or other hosts. Fix valid issues, explain rejected suggestions, reply, and resolve AI threads from reviewers such as Greptile or CodeRabbit while leaving human threads open."
---

# Resolve Review Comments

Works with GitLab merge requests, GitHub pull requests, and equivalent reviews on other hosts, including mixed batches. Fix valid feedback, explain rejected suggestions, and resolve completed AI threads. Leave human threads open.

1. **Choose the batch.** Accept review URLs, IDs with repository context, or a clearly specified group. Identify each review's host from its URL or repository remote. Process every requested review; ask only when the target set is unclear. Track each review's host, repository, branch or change, and threads separately. Keep fixes in the correct review; use separate Git worktrees when needed.
2. **Read the feedback.** Use each host's available tools, CLI, or API to fetch the current diff and all pages of unresolved comments and replies. Read relevant code and repository instructions. Skip system events and already handled feedback. For AI-only requests, leave human feedback untouched.
3. **Check each claim.** Fix valid issues with the smallest sound change and appropriate checks. Reject incorrect, duplicate, already fixed, or unhelpful suggestions with concrete evidence or a design reason. An outdated comment is not proof of a fix. Leave valid issues that cannot be addressed open, explain the blocker, and continue through the batch.
4. **Complete fixes.** Follow each repository's validation and review workflow. Before claiming completion or resolving a fixed issue, ensure the reviewed branch or change contains the verified fix. If publishing is blocked or unauthorized, report the local fix and leave the thread open.
5. **Reply briefly.** Address every actionable point. Explain what changed and how it was checked, or why no change is needed, in plain English. Link supporting code or commits where useful. A request to reply and resolve authorizes those actions for the batch; an assessment-only request does not. Respect existing authorization without asking again.
6. **Resolve AI threads only.** Identify AI authors through account metadata or known integrations, never writing style. Resolve only after the reply is confirmed and every point is handled. Leave human and uncertain-author threads open, including AI-started threads with outstanding human questions or objections. Your own reply does not count as human review.
7. **Check before writing.** Refresh threads before replying or resolving to catch new feedback and avoid duplicate replies. Read back uncertain writes before retrying, and verify resolution. Report unsupported resolution actions or access failures and continue with other reviews.
8. **Summarize the batch.** Give one linked row per review with fixes, rejected suggestions, checks, resolved threads, and remaining human or blocked threads. Finish the batch without starting an ongoing monitor.
