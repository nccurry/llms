---
name: wrap-this-up
description: "Use when the user is done with a piece of work, or done for now, and wants it landed - 'wrap this up', 'merge it down', 'we're done', 'close this out', or finishing after PLC, Luna, Sol, or Opus execution. Merges everything in flight, finished or not, into main directly or through a PR/MR (merged only when the user says), rewrites the plan's Current Work to its real end state, moves a completed plan to done, and removes the work's worktrees and branches locally and on the remote. For an update that keeps work going, use plc-checkpoint."
---

# Wrap This Up

Land everything this work has in flight on `main`, record exactly what is
finished and what isn't, and leave nothing behind on disk. Use it at the end
of the work, or to stop for now with what exists merged.

It differs from `plc-checkpoint`, which only reports and tidies what is
already merged. Here, unfinished work merges too, and the plan records what
is left.

Load [plain-english](../plain-english/SKILL.md) and
[verify-before-claiming](../verify-before-claiming/SKILL.md) first.

## Reuse the owning workflow

For PLC execution work, read `plc-execution`'s procedures for integration
safety, parent review, PR/MR delivery, and cleanup, and resume their recorded
gates instead of repeating finished work. Keep an active monitored
Luna/Sol/Opus/Sonnet workflow's model choices, escalation state, strict
acceptance, and parent ownership when repairs need children. Use `docs-sync`
for maintained documentation that the delivered behavior changes. Without a
PLC, use the repo's own checks and conventions; don't create a packet just to
close out.

## 1. Checkpoint first

Run [plc-checkpoint](../plc-checkpoint/SKILL.md) steps 1 to 4: find the work
and its plan, read the last Current Work block, gather what changed, and tidy
what is already merged. Don't rewrite Current Work yet; step 6 writes it once, with the
end state.

## 2. Collect what's in flight

List every branch for this work with commits not on `main`: child, repair,
and integration branches, in the campaign folder or anywhere else
`git worktree list` shows them.

- Commit this task's uncommitted source, test, and doc changes on their own
  branch, after reading the diff. Don't commit scratch notes, logs, or
  output: move anything useful into the plan, and ask about the rest, since
  whatever you commit lands on `main`.
- Leave alone a checkout another agent holds: a worktree lock, or uncommitted
  changes that aren't this task's. Its branch doesn't merge. Say which, and
  why.
- If which branches belong to this work is unclear, ask before merging any.

## 3. Choose the route

Use the user's words, then the plan's recorded route, then the repo's
`AGENTS.md` convention.

- **Direct:** merge in a checkout made for it, never in the user's primary
  checkout, which may be dirty, on another branch, or hold their own
  unpushed commits. Use the integration worktree when there is one;
  otherwise `git worktree add --detach <campaign>/_merge origin/main`. Merge
  each branch there, run the checks (step 4), then `git push <remote>
  HEAD:main`. A wrap-up on this route authorizes that push. Afterwards,
  fast-forward local `main` only if it is clean and can fast-forward;
  otherwise say it is behind.
- **Local only:** when the user says not to push, or names a local target
  such as local `main` or `release/next`, merge into that ref and stop there.
  Check delivery against that ref, skip the push and remote-branch deletion,
  and record remote cleanup as pending.
- **PR/MR:** push and open one PR/MR from the integration branch, or one per
  child branch when there is none, or update existing ones, following
  `plc-execution`'s
  [merge-request-integration](../plc-execution/references/merge-request-integration.md).
  Use `create-mr-description` to draft or refresh each description before
  opening it and after the source, target, or checks change.
  Merge only when the user says to ("merge it"). Otherwise leave it ready for
  review, and say so.

Unfinished work merges as it stands. That is the point of wrapping up for
now: the plan records what's left, and the next session starts from `main`.

## 4. Check the combined result

Before anything reaches `main`, run the repo's required checks on the
combined result: the integration branch, or a local merge of every branch
being delivered. Each branch passing alone doesn't prove they pass together.

If a check fails, stop before merging. Report the failure and its likely
cause, and ask whether to fix it, merge anyway, or leave it. Merging the
branches that pass on their own is acceptable once you've said so; a failing
combination reaches `main` only with the user's explicit go-ahead.

For PLC work, also satisfy the owning workflow's gates (parent review,
audits, CI, host review) at the final revision.

## 5. Merge and confirm

Merge, then confirm the target contains each delivered branch's tip:
`git merge-base --is-ancestor <tip> origin/main` after a fetch (or the local
target ref on the local-only route), or the PR/MR's merged state for squash
and rebase merges. Recheck the target right before pushing; if it moved,
merge it in and rerun the affected checks. Never force-push `main`.

## 6. Finish the plan

Rewrite Current Work, and in a full packet the Phase Status table, to the
real end state, in the plan's own format:

- Each item merged, verified, or still open, with the merge commit and the
  checks that ran on it.
- If every requirement has passed its acceptance: mark the plan Complete and
  move it to the repo's done folder (`<plans folder>/done/<slug>/` unless the
  repo has its own convention). Update links that pointed at the old path.
- Otherwise the plan stays where it is, with what's left as the next step.
  Don't mark anything complete to make the wrap-up look finished.
- Record decisions and open questions from the conversation, as
  `plc-checkpoint` does.

Deliver the plan update the same way as the code: in the merge, or as a
commit on `main` pushed with it. A plan kept in another repo gets its own
commit there, following that repo's rules.

## 7. Clean up this work

Follow [clean-stale-worktrees](../clean-stale-worktrees/SKILL.md) for each
removal and its verification. Only this work's checkouts and branches; other
campaigns are untouched.

- **Merged into `main`:** remove each worktree, including the `_merge`
  checkout (run from outside it, no `--force`, after checking ignored files
  as `plc-checkpoint` step 4 describes), confirm the folder and registration
  are gone, delete the local branch, and delete the remote branch with
  `git push --force-with-lease=<branch>:<merged-sha> <remote> --delete
  <branch>`, so later pushes to it aren't lost. Remove the campaign folder
  and its `_output/` once it's empty of live work.
- **Local only:** the same, except remote branches stay; list them as
  pending in Current Work.
- **PR/MR left open:** remove the worktrees once the branch is pushed with no
  local changes, keep the branch until the PR/MR merges, and record cleanup as
  pending on that PR/MR in Current Work.
- **Skipped (another agent, failing checks):** keep the worktree and branch,
  and list them in Current Work with the reason.

## 8. Report

- Route, what merged, and the merge commit(s) on `main`.
- Checks run on the combined result, and on which commit.
- The plan: complete and moved, or open with what's left and the next step.
- Removed: each worktree, local branch, and remote branch.
- Kept: each one, with its reason and what releases it.

Call the wrap-up complete only when everything selected is merged (or its
PR/MR is ready, if the user said not to merge), the plan says what's true,
and every checkout for this work is removed or accounted for.

## Gotchas

- Squash and rebase merges leave branches looking unmerged; use the PR/MR's
  merged state, then delete.
- Merging into the integration branch isn't delivery. Only the final target is: `main`, or the local target the user named.
- `git branch -d` compares with the current branch, not `main`, so check
  ancestry against `origin/main` yourself and then use `-D`.
- A child's report that its tests passed was on its branch alone. Run the
  checks again on the combined result.
