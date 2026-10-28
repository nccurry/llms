---
name: plc-checkpoint
description: Use when the user wants an update on planned or ad-hoc implementation work they will keep working on - "where are we", "catch me up", "what's left", "checkpoint", "is the plan up to date", "tidy up what's done". Reads the plan's Current Work block, checks what changed since in git and PRs, rewrites it where the plan is tracked (including another repo), and removes worktrees and branches already merged. Leaves in-progress work in place and never merges; to merge everything and finish, use wrap-this-up.
---

# PLC Checkpoint

Bring a piece of work up to date and tell the user where it stands, at any
point while it continues: mid-session, or the next morning in a new session.
Three jobs, in this order:

1. Find out what changed since the plan's Current Work block was last updated.
2. Remove what is already finished, so worktrees don't pile up.
3. Rewrite Current Work, so the next session starts from current state.

It never merges, rebases, switches branches, or touches work in progress.
Finishing work is `wrap-this-up`'s job.

**Report only** when the user says so, for example "just tell me" or "don't
change anything": skip steps 4 and 5 below and list what they would have
changed.

Load [plain-english](../plain-english/SKILL.md) and
[verify-before-claiming](../verify-before-claiming/SKILL.md) first.

Use a different skill when the request is something else:

- "Wrap this up", "merge it", "we're done": `wrap-this-up`.
- Clean up old worktrees across campaigns or repos: `clean-stale-worktrees`.
- "Does the code match the plan?" as a review: `plc-alignment-audit`.
- One narrow fact, such as whether a command finished: answer directly.

## 1. Find the work and its plan

Use the argument, the conversation, then the current branch. Otherwise look in
the repo's plan folders the way [plc-planning](../plc-planning/SKILL.md) does.
If several plans are in progress and none is named, give one headline line
per plan, change nothing, and ask which one to expand.

The plan is one of three kinds:

- **A PLC packet or compact plan in this repo.**
- **A plan in another repo.** The repo's `AGENTS.md` or `CLAUDE.md`, or a
  pointer in the packet, says where. Read and update it there.
- **No plan (ad-hoc work).** The conversation, the session's task list, and
  git are the plan. Don't create a plan file unasked. At the end, offer a
  compact plan from `plc-planning`'s `assets/compact-plan.md`, so the next
  session has a Current Work block to read.

Name the campaign: the plan ID or slug used for its worktree folder and
branches. Read the repo's `AGENTS.md` for its worktree layout, target branch,
and how plans are committed.

## 2. Start from the last Current Work

Read the plan's Current Work block first: its "Last updated" date and commit,
current state, next action, blockers, and where the work lives. In a full
packet, also read the Phase Status table in `IMPLEMENTATION_PLAN.md`. The rest
of the checkpoint is "what changed since then". An older packet may have no
Current Work block, or state scattered across sections; read those, and step 5
gives it a proper Current Work block.

## 3. Gather what changed

Fetch first, then collect facts. Record the commit each fact applies to.

1. **Every copy of the plan:** local `main`, `origin/main`, the integration
   branch, and each campaign worktree. Find the newest with
   `git log -1 --format='%h %cs' <ref> -- <plan>` for each ref, and note where
   copies disagree.
2. **Branches and worktrees.** Start from `git worktree list --porcelain`,
   not the campaign folder alone: older checkouts live in `.claude/worktrees`,
   `~/.codex/worktrees`, or elsewhere. For each one in this campaign: branch,
   commits ahead of and behind its target, `git -C <path> status --short
   --untracked-files=all`, and any lock (`git worktree list --porcelain` shows
   `locked`). The read-only report in `clean-stale-worktrees` gathers the same
   facts when `uv` is available:

   ```sh
   uv run --script <skills-dir>/clean-stale-worktrees/scripts/worktree_report.py --path . --fetch --reviews --format table
   ```

3. **PRs/MRs** with `gh` or `glab`: state, target, merge commit, CI, review.
4. **Checks.** For each item the plan calls verified, the check and the commit
   it ran on. A result from an older commit doesn't verify the current one.
5. **This conversation and child reports:** decisions, scope calls,
   approvals, and open questions since the work started.
6. **Other repos the plan waits on.** For each, read
   [dependency-check](references/dependency-check.md). Use one subagent per
   repo when there are several and the host supports it.

Sort each item onto this ladder, quoting the plan's words when they differ:

`planned → in progress → implemented → merged → verified → live`

plus **blocked**, **deferred**, and **dropped** (the last two only with
approval in the plan or the conversation). "Merged" names the branch it
merged into: the integration branch is not `main`. A phase takes the lowest
state among its items.

If a source is unavailable (no host login, a path on another machine), say
so under blind spots. Don't guess its state.

## 4. Tidy what is finished

Remove only what is finished, so the next session sees only live work. A
worktree is finished when **all** of these hold:

- Its branch has work of its own that reached the target. A branch just
  created from `main` is also an ancestor of `main`, but it is not started,
  not finished: keep it. Count it as finished when its commits are in `main`
  (`origin/main` after the fetch, or local `main` with no remote) or in the
  campaign's integration branch and `git reflog <branch>` shows commits after
  its creation, or when its PR/MR is merged and the branch has no commits
  after the merged head. Use `git merge-base --is-ancestor <branch> <target>`
  for the containment check. Squash and rebase merges fail it, so use the
  PR/MR state for those.
- `git status --short --untracked-files=all --ignored` shows nothing that
  isn't disposable output. Untracked or ignored files may be notes, `.env`
  files, or local config that exist nowhere else, and `git worktree remove`
  deletes ignored files without asking. Keep the worktree, name the files,
  and suggest moving anything useful into the plan.
- It is not locked and not the current checkout. A worktree lock is the hold
  signal. A plan row that still says "in progress" doesn't keep a branch
  git proves is merged; the plan is what step 5 corrects.

Then, for each finished worktree, one at a time, following
[clean-stale-worktrees](../clean-stale-worktrees/SKILL.md)' removal and
verification rules:

1. `git worktree remove <path>`, run from outside it, without `--force`. If
   it refuses, stop for that worktree and report why.
2. Confirm the folder and its `git worktree list` entry are both gone.
3. Delete its local branch with `git branch -D <branch>`, only after the
   merge check above passed for that exact commit. (`git branch -d` compares
   with the current branch, not the target, so it can't be the check.)
4. If the branch was merged into `main` and also exists on the remote, delete
   it there, only if the remote still points at the commit you checked:
   `git push --force-with-lease=<branch>:<checked-sha> <remote> --delete <branch>`.
   If the lease fails, someone pushed more work; keep it and report it. A
   branch merged only into the integration branch keeps its remote copy
   until wrap-up.

A local branch for this work with no worktree is finished when the same merge
check passes: delete it, and its remote copy when merged into `main`.

Also remove review and verification copies no longer in use, and output
folders (`<campaign>/_output/`, build folders) that no running check needs,
following `clean-stale-worktrees`' artifact rules. Keep the integration
worktree while the campaign is open.

## 5. Rewrite Current Work

Rewrite the plan's Current Work block in place, in the format from
`plc-planning`'s templates: status, "Last updated" (today, the branch, and
its commit), current state, next action, blocker, resume check, and where the
work lives (after tidying). In a full packet, also update the affected rows of
the Phase Status table: implementation, verification, and delivery, with
evidence. Replace the old content; don't append a history.

Also bring these up to date in their own sections: decisions from the
conversation (accepted if the user approved, otherwise proposed), open
questions, and blockers the evidence has cleared.

Don't change requirement or design text: when code and a requirement
disagree, add an open question. Don't mark anything verified or complete
without its evidence.

**Which copy, and where to commit:**

- Update the copy where the work continues: the integration or work branch
  the plan travels with, or `main` when there is none. If the newest copy is
  only on `origin`, don't edit an older local copy; say to pull.
- Skip a copy that has uncommitted changes you didn't make, or where another
  agent is working. Report what you would have changed. An uncommitted diff
  that touches only the Current Work block is usually an earlier checkpoint's
  edit waiting for a commit decision: rewrite it in place and ask again.
- Commit only the plan files, on their own, as
  `docs(plan): update <plan> status`, after `git diff --check`.
- On the default branch, commit only when the repo's `AGENTS.md` or the plan
  says plan updates go straight there. Otherwise leave the edit uncommitted
  and ask.
- A plan in another repo gets its own commit there, following that repo's
  rules. Push it only when that repo's instructions say to.
- Ad-hoc work with no plan: update the session's task list instead.

## 6. Report

Follow [the report template](references/report-template.md): headline, what
changed since the last status, next step, then where we are, done, in
progress, left, scope added, decisions, open questions and blockers, what you
can try now, tidied, drift and blind spots, records updated.

- Split remaining work into "can start now" and "waiting on".
- Explain project terms the user may not know in a few words.
- For a brief or quick status, give only the headline, since last status,
  next step, left, blockers, and records updated.

When everything selected is done, or the user sounds ready to stop, offer
`wrap-this-up`.

## Gotchas

- The integration branch is not `main`. A child merged into integration is
  finished as a branch, but its requirement is not merged into `main`.
- The plan copy in the main checkout often lags the active worktree's copy.
- Local `main` often lags `origin/main`. Compare against the remote after
  fetching; don't pull.
- "Verified" in a plan may refer to an older commit.
- A dependency the plan calls "waiting" may already be on the other repo's
  `main`.
- Decisions made in chat are often missing from the plan. An unapproved one is
  still worth recording as proposed.
- A plan can contradict itself, for example a header that says pending above
  a table that says merged. Current Work replaces both with one answer.
