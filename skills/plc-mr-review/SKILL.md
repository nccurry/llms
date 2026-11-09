---
name: plc-mr-review
description: "Gets existing open merge requests or pull requests ready for review: CI green, review threads handled, descriptions current, stacks worked bottom up. Leaves them unmerged by default; merges, sets merge-when-green, or adds them to a merge train only when the user asks, then updates any linked plan. Works with or without a plan. For landing and cleaning up a session's in-flight work, use plc-wrapup instead. Use when the user says 'get these MRs ready', 'get CI green and resolve comments', 'clean up my open PRs', or 'merge them when green'."
---

# PLC MR Review

Take one or more open merge requests (MRs) or pull requests to the point
where a reviewer can approve them: CI passes, every review thread is
handled, and the description matches the change. Merging is a separate
step that happens only when the user asks.

Load [plain-english](../plain-english/SKILL.md) and
[verify-before-claiming](../verify-before-claiming/SKILL.md) first.

## 1. Find the MRs

Use the MRs the user names. Otherwise list the repository's open MRs with
the host's tool (`glab mr list`, `gh pr list`) and pick the ones the user
means, such as their own or one stack; ask when that is unclear. For a
stack, where each MR targets the one below it, work from the bottom up, so
each fix lands before the MRs that build on it. An MR whose description says
`Stacked on !N` or `Based on !N` is also part of a stack, even when every MR
targets the default branch; keep that line true when you retarget or rebase.

For each MR, note its source branch, target, head commit, CI state and open
threads. Work in the checkout or worktree that already holds its branch;
otherwise add a worktree for it. Never change the user's primary checkout.

## 2. Get CI green

Read the failing jobs' logs at the MR's head commit. Fix real failures in
the MR's own branch with the repository's normal care: the smallest fix,
its checks run locally, then a push. A failure that comes from the target
or from infrastructure, such as a flaky runner, is reported, not patched
here; retry a job only when the logs show it is flaky. Wait for pending
required jobs and read their actual results.

## 3. Handle review threads

Run [resolve-review-comments](../resolve-review-comments/SKILL.md) on each
MR's threads. It decides which to fix, replies, and which threads it may
resolve; human threads stay open.

## 4. Keep the description current

When steps 2 or 3 changed what the MR does or how it was checked, refresh
its description with
[create-mr-description](../create-mr-description/SKILL.md).

## 5. Leave it ready, or merge when asked

By default, leave each MR open and unmerged, and report it as ready, or
say what still blocks it.

Merge only when the user asks, and only the way they ask, using the
repository's route (`glab`, `gh`, or the host's merge button):

- **Merge now:** after required CI and approvals pass at the head commit.
- **Merge when green:** set merge-when-pipeline-succeeds (GitLab) or
  auto-merge (GitHub).
- **Merge train:** add the MR to the train when the repository uses one.

For a stack, merge bottom up, and retarget or rebase each next MR as the
host requires before merging it.

When this work has a ticket or the project uses tickets, run
[manage-tickets](../manage-tickets/SKILL.md) for each MR it merges.

## 6. Update a linked plan after a merge

When a merged MR belongs to a plan, update the plan's Current Work and
`## Phases` table with the rewrite rules in `plc-checkpoint`'s
[Rewrite Current Work](../plc-checkpoint/SKILL.md#5-rewrite-current-work)
step. The phase's note names the MR and the merge commit, and the phase
gets its word from `plc-planning`'s [Words](../plc-planning/references/shared-format.md#words)
rules: it is Merged only when all its parts are on the branch the work is
delivered to, and a merge into another target, such as the next MR down a
stack, leaves it Implemented. Leave Verified to the plan's checks on the
merged code, as [plc-wrapup](../plc-wrapup/SKILL.md) step 5 or a later
checkpoint runs them. Update the `## Merge requests` table, if the plan
has one, as `plc-planning`'s
[Merge requests](../plc-planning/references/shared-format.md#merge-requests) rule says.
With no plan, skip this step.

## 7. Report

One row per MR: its link, CI state at the head commit, threads fixed,
answered and left open, whether the description changed, and whether it is
ready, blocked (with why), merged (with the merge commit), or set to merge
when green.
