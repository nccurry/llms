---
name: plc-wrapup
description: "Use when the user is done with a piece of work, or done for now, and wants this session's in-flight work landed and cleaned up - 'wrap this up', 'merge it down', 'we're done', 'close this out' - or wants to drop it unmerged, or finishing after PLC, Luna, Sol, or Opus execution. Merges everything in flight, finished or not, into main directly or through a PR/MR (merged now, or set to merge when CI is green, only when the user says), rewrites the plan's Current Work to its real end state, moves a finished plan to the completed folder, and removes the work's worktrees and branches locally and on the remote. For an update that keeps work going, use plc-checkpoint."
---

# PLC Wrapup

Land everything this work has in flight on `main`, record exactly what is
finished and what isn't, and leave nothing behind on disk. Use it at the end
of the work, or to stop for now with what exists merged.

It differs from `plc-checkpoint`, which only reports and tidies what is
already merged. Here, unfinished work merges too, and the plan records what
is left.

Load [plain-english](../plain-english/SKILL.md) and
[verify-before-claiming](../verify-before-claiming/SKILL.md) first.

**Scope.** The work is what the user names, which may be several plans or
branches. When they name none, it is all the work this session and its
children started: every plan whose work they started, not one they only
touched for its records, such as a checkpoint's Log line, and every branch
or worktree they made. Ask only when that is unclear. Each plan in scope
gets its own pass through the plan steps below.

## Reuse the owning workflow

For PLC execution work, read `plc-execution`'s procedures for integration
safety, parent review, PR/MR delivery, and cleanup, and resume their recorded
gates instead of repeating finished work. Keep an active monitored
Luna/Sol/Opus/Sonnet workflow's model choices, escalation state, strict
acceptance, and parent ownership when repairs need children. Use `docs-sync`
for maintained documentation that the delivered behavior changes. Without a
PLC, use the repo's own checks and conventions; don't create a packet just to
close out, and skip the plan steps below.

When the user is dropping the work rather than landing it, merge nothing.
Run step 1 and skip steps 2 to 5. Then the plan ends in `archived/` as
`plc-planning`'s [Ending a packet](../plc-planning/SKILL.md#ending-a-packet)
rule says, delivered by step 6's rules, including its ticket call, and
checked with `--strict`; if the plan exists only on a dropped branch, ask
whether to keep it on `main`.
Steps 7 and 8 then keep or remove the unfinished branches as
[clean-stale-worktrees](../clean-stale-worktrees/SKILL.md) says, and report.

## 1. Checkpoint first

Run [plc-checkpoint](../plc-checkpoint/SKILL.md) from "Find the work and its
plan" through "Tidy what is finished" for each plan in scope: read its last
Current Work block, gather what changed, and tidy what is already merged.
The scope above names the plans, so don't stop at the checkpoint's "several
plans, none named" question when the session's own work identifies them.
Don't rewrite Current Work yet; step 6 writes it once, with the end state.

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
- On every route, merge in dependency order: a branch, or a plan's work,
  that builds on another merges after it.

## 3. Choose the route

Use the user's words, then the plan's recorded route, then the repo's
`AGENTS.md` convention.

- **Direct:** merge in a checkout made for it, never in the user's primary
  checkout, which may be dirty, on another branch, or hold their own
  unpushed commits. Use the integration worktree when there is one;
  otherwise `git worktree add --detach <campaign>/_merge origin/main`. Merge
  each branch there, run the checks (step 4), commit the plan update on top
  (step 6), then `git push <remote> HEAD:main`. A wrap-up on this route
  authorizes that push. Afterwards,
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
  Do what the user asks: merge now ("merge it"), set the host's
  merge-when-pipeline-succeeds or auto-merge so it merges once CI is green
  ("merge it when green"), or, by default, leave it ready for review, and
  say so. Until the merge happens, treat it as left open.

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
merge it in and rerun the affected checks. Never force-push `main`. On the
direct route the push happens at the end of step 6, with the plan update;
run the `origin/main` check after that push. Before step 6, run each
merged phase's checks that need the merged code on the merged result (step
4's results on the same tree count), so step 6 can mark it Verified, or
keep it Merged and name the check that is left.

## 6. Finish the plan

Do this for each plan in scope: its own Current Work and `## Phases`
update, and, when it is finished, its own move to `completed/`.

Rewrite Current Work and the README's `## Phases` table to the real end
state, using the rewrite rules in `plc-checkpoint`'s
[Rewrite Current Work](../plc-checkpoint/SKILL.md#5-rewrite-current-work)
step. Its commit rules don't apply; this step's delivery rules below do.
Update the `## Merge requests` table, if the plan has one, and add rows
for the MRs this wrap-up opened, as `plc-planning`'s
[Merge requests](../plc-planning/SKILL.md#merge-requests) rule says.
First decide, with step 7's rules, which checkouts and branches step 7 will
remove and which it will keep. Record what it will keep now, so the plan is
delivered once: in an open plan, as rows in Current Work's "Where the work
lives" table, with the reason in the State cell; in a finished plan, as a
dated Log line, written before step 2 below adds the historical-record line.

The plan is finished only when every requirement has passed its acceptance.
Then, in this order:

1. Check the phases before changing Status:
   `python3 <skills-dir>/plc-planning/scripts/format_check.py --packet <packet> --strict --lifecycle completed`.
   Until step 2 below sets Complete, it reports that Status does not match
   `completed/`; that finding is expected.
   - When it reports a phase that `completed/` does not allow, the plan is
     not finished. Leave Status as it is, add no historical-record line, and
     record what is left as the rewrite rules say: each gap as a new row or
     an `Open question:` line, and other unfinished work in its phase's
     note.
   - When a finding needs the user's decision, such as a status that
     disagrees with the evidence or a missing owner, stop and ask.
   - Fix any other finding and run the check again.
2. Set Status to Complete and add the historical-record line that
   `plc-planning`'s [Ending a packet](../plc-planning/SKILL.md#ending-a-packet)
   rule describes, naming the merge commit on the target.
3. Move the packet to `<plans folder>/completed/` as `plc-planning`'s
   [lifecycle folders](../plc-planning/SKILL.md#lifecycle-folders) rule says.
   Plans that older versions of this skill finished into another folder stay
   there.
4. Run the check on the moved packet with `--strict`. It must exit 0.

A plan that is not finished is not moved to `completed/`; any other move
follows the lifecycle folders rule. Its next action says what's left. Don't
mark anything complete to make the wrap-up look finished.

Deliver the plan update with the code:

- **Direct:** commit it in the merge checkout on top of the merge, push both
  together, then run step 5's `origin/main` check.
- **Local only:** commit it on top of the merge on the local target.
- **PR/MR:** an open plan's update travels in the PR/MR. Finishing the plan
  waits for the merge. If it merged during this wrap-up, finish the plan now
  as a follow-up commit by the repo's usual route; otherwise the next
  wrap-up finishes it after the merge.
- A plan kept in another repo gets its own commit there, following that
  repo's rules.

When this work has a ticket or the project uses tickets, run
[manage-tickets](../manage-tickets/SKILL.md) for the wrap-up, to close the
ticket or comment on it.

## 7. Clean up this work

Follow [clean-stale-worktrees](../clean-stale-worktrees/SKILL.md) for each
removal and its verification. Only the checkouts and branches in scope;
work that other sessions started is untouched. Step 6 already recorded what
stays. If a removal step 6 planned fails, record what is left: in an open
plan, as a row in "Where the work lives"; in a finished plan, as the one
dated follow-up Log line that `plc-planning`'s
[Ending a packet](../plc-planning/SKILL.md#ending-a-packet) rule allows.
With no plan, step 8's report is the record.

- **Merged into `main`:** remove each worktree, including the `_merge`
  checkout (run from outside it, no `--force`, after checking ignored files
  as `plc-checkpoint`'s "Tidy what is finished" step describes), confirm the
  folder and registration are gone, delete the local branch, and delete the
  remote branch with
  `git push --force-with-lease=<branch>:<merged-sha> <remote> --delete
  <branch>`, so later pushes to it aren't lost. Remove the campaign folder
  and its `_output/` once it's empty of live work.
- **Local only:** the same, except remote branches stay, pending.
- **PR/MR left open:** remove the worktrees once the branch is pushed with no
  local changes, and keep the branch until the PR/MR merges, pending on that
  PR/MR.
- **Skipped (another agent, failing checks):** keep the worktree and branch,
  pending, with the reason.

## 8. Report

- Route, what merged, and the merge commit(s) on `main`.
- Checks run on the combined result, and on which commit.
- The plan: complete and moved, or open with what's left and the next step.
- Removed: each worktree, local branch, and remote branch.
- Kept: each one, with its reason and what releases it.

Call the wrap-up complete only when everything selected is merged, or its
PR/MR is left ready or set to merge when green, as step 3 chose; the plan
says what's true; and every checkout for this work is removed or accounted
for.

## Gotchas

- Squash and rebase merges leave branches looking unmerged; use the PR/MR's
  merged state, then delete.
- Merging into the integration branch isn't delivery. Only the final target is: `main`, or the local target the user named.
- `git branch -d` compares with the current branch, not `main`, so check
  ancestry against `origin/main` yourself and then use `-D`.
- A child's report that its tests passed was on its branch alone. Run the
  checks again on the combined result.
