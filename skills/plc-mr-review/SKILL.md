---
name: plc-mr-review
description: "Prepares open merge requests and pull requests for review, or recommends how to merge them. Use for CI failures, review feedback, stacked changes, or merge advice. Use plc-wrapup for final delivery and cleanup."
---

# PLC MR Review

Take one or more open merge requests (MRs) or pull requests to the point
where a reviewer can approve them: CI passes, every review thread is
handled, and the description matches the change. Merging is a separate
step that happens only when the user asks.
Use [merge policy](references/merge-policy.md) when recommending how to
merge or when to push.
For advice-only requests, read the MR, diff, project settings, and relevant
CI results, then go straight to the report. Do not create a worktree, edit
files, push, or merge.

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

Read the failing jobs' logs for the current MR revision, identifying the
tested SHA and whether it is source-only, merged-result, or train/queue CI.
Fix real failures in the MR's own branch with the repository's normal care:
group related repairs, run their checks locally, then push them together
when authorized. Avoid one push per comment or a history rewrite just for
tidiness while expensive CI is running. A failure that comes from the target
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

- **Merge now:** after required CI and approvals pass for the current source
  and required combined result; use the existing train/queue when applicable.
- **Merge when green:** set merge-when-pipeline-succeeds (GitLab) or
  auto-merge (GitHub).
- **Merge train:** add the MR to the train when the repository uses one.

For a stack, merge bottom up using the ancestry guidance in merge policy.
Retarget or rebase each next MR as the host requires, carrying only its
remaining changes after a squashed prerequisite. Do not rewrite dependents
or restart train pipelines merely to tidy the commit list.

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
Batch these records for the delivery using the checkpoint's commit rules;
do not open a separate completion MR after each merge. With no plan, skip
this step.

## 7. Report

One row per MR: its link, CI state for the source and required combined
result, threads fixed, answered and left open, whether the description changed,
and whether it is ready, blocked (with why), merged (with the merge commit),
or set to merge when green. Give the recommended or chosen merge method
and its reason when it affects dependent branches, history, or CI cost.
Name pending checks on the merged result and unpublished plan updates.
