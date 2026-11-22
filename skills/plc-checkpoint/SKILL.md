---
name: plc-checkpoint
description: Use when the user wants an update on planned or ad-hoc implementation work they will keep working on - "where are we", "catch me up", "what's left", "checkpoint", "is the plan up to date", "tidy up what's done". Reads the plan's Current Work block, checks what changed since in git and PRs, rewrites it where the plan is tracked (including another repo), and cleans up finished task checkouts and eligible branches. Keeps unfinished source and active checkouts and never merges; to merge everything and finish, use plc-wrapup.
---

# PLC Checkpoint

Bring a piece of work up to date and tell the user where it stands, at any
point while it continues: mid-session, or the next morning in a new session.
Three jobs, in this order:

1. Find out what changed since the plan's Current Work block was last updated.
2. Remove what is already finished, so worktrees don't pile up.
3. Rewrite Current Work, so the next session starts from current state.

It never merges, rebases, switches branches, or touches work in progress.
Finishing work is `plc-wrapup`'s job.

**Report only** when the user says so, for example "just tell me" or "don't
change anything": skip steps 4 and 5 below and list what they would have
changed.

Load [plain-english](../plain-english/SKILL.md) and
[verify-before-claiming](../verify-before-claiming/SKILL.md) first.

Use a different skill when the request is something else:

- "Wrap this up", "merge it", "we're done": `plc-wrapup`.
- Clean up old worktrees across campaigns or repos: `clean-stale-worktrees`.
- "Does the code match the plan?" as a review: `plc-alignment-audit`.
- One narrow fact, such as whether a command finished: answer directly.

Follow the shared [tag rules](../plc-planning/references/shared-format.md#tags) when writing or maintaining plans.

## 1. Find the work and its plan

Use the argument, the conversation, then the current branch. Otherwise look in
the repo's plan folders the way [plc-planning](../plc-planning/SKILL.md) does.
If several plans are in progress and none is named, give one headline line
per plan, change nothing, and ask which one to expand.

The plan is one of three kinds:

- **A PLC packet or one-file plan in this repo.**
- **A plan in another repo.** The repo's `AGENTS.md` or `CLAUDE.md`, or a
  pointer in the packet, says where. Read and update it there.
- **No plan (ad-hoc work).** The conversation, the session's task list, and
  git are the plan. Don't create a plan file unasked. When the work will
  continue in a later session, offer to write a one-file plan with
  `plc-planning`, so that session has a Current Work block to read.

Name the campaign: the plan ID or slug used for its worktree folder and
branches. Read the repo's `AGENTS.md` for its worktree layout, target branch,
and how plans are committed.

## 2. Start from the last Current Work

Read the plan's Current Work block first: its "Last updated" date and commit,
current state, next action, blockers, and where the work lives. Also read the
README's `## Phases` table and the last lines of its `## Log`. The rest of the
checkpoint is "what changed since then". An older packet may have no Current
Work block, phase state in `IMPLEMENTATION_PLAN.md`, or state scattered across
sections; read those, and step 5 converts it to the shared template.

## 3. Gather what changed

Fetch first, then collect facts. Record the commit each fact applies to.

1. **Every copy of the plan:** local `main`, `origin/main`, the integration
   branch, and each campaign worktree. A move between lifecycle folders
   changes the path, so find each ref's copy by the packet's folder or file
   name in any lifecycle folder:
   `git ls-tree -r --name-only <ref> -- <plans folder>`. Then find the newest
   with `git log -1 --format='%h %cs' <ref> -- <that path>` for each ref, and
   note where copies disagree.
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

3. **PRs/MRs** with `gh` or `glab`: state, target, merge commit, CI, review,
   for this work's branches and open MRs whose description has a `Plan:`
   line for this plan, or whose branch name carries its ID. With no plan,
   use the work's own branches.
4. **Checks.** For each part the plan calls verified, the check and the commit
   it ran on. A result from an older commit doesn't verify the current one.
   For a Merged phase with no result on the target commit yet, name its
   checks in the next action; run them, in a detached checkout of the
   target, only when they are quick.
5. **This conversation and child reports:** decisions, scope calls,
   approvals, and open questions since the work started.
6. **Other plans the plan waits on**, from its `Depends on` line. For one in
   this repo, read its Current Work and Phases. For another repo, read
   [dependency-check](references/dependency-check.md). Use one subagent per
   repo when there are several and the host supports it.
7. **Tickets** the plan or the work names, when a tracker tool is
   available: their state, as one more source. Report where it disagrees
   with the plan as drift. Don't change tickets here.

Find each phase's parts with the Parts rule in `plc-planning`'s
[word list](../plc-planning/references/shared-format.md#words), and give each part a phase
state word from that list; when the plan uses a different word, quote the
plan's word beside yours. Then choose each phase's word with the list's
rule for a phase whose parts differ, including its steps for side states.
For example, a phase with one part merged and one not started is In
progress, not Planned.

If a source is unavailable (no host login, a path on another machine), say
so under blind spots. Don't guess its state.

## 4. Tidy what is finished

Start with cleanup left pending in Current Work or the prior handoff. Refresh
the status of each named MR and recheck each hold. Run the
[cleanup check](../clean-stale-worktrees/references/cleanup-check.md) within
this task's scope, including branch-only entries. Decide checkout, local
branch, and remote branch removal separately. Correct stale rows in step 5
and carry forward anything still pending.

An accepted child contribution can close its checkout before the campaign
reaches main. Confirm the child has released it, retain needed source and
notes, and check which tests or processes still need it. Keep the branch when
needed to preserve committed work. Preserve active assignments, including a new checkout
that has no commits yet; do not infer closure from ancestry alone.

For this task's branches proven merged into fetched remote main, remove the
remote branch only if it still points at the checked commit:
`git push --force-with-lease=<branch>:<checked-sha> <remote> --delete <branch>`.
If the lease fails, keep it and report the new work. A branch merged only
into integration keeps its remote copy until wrap-up. Local branches without
checkouts follow the same source and deletion checks.

Also remove review and verification copies no longer in use, and output
folders (`<campaign>/_output/`, build folders) that no running check needs,
following `clean-stale-worktrees`' artifact rules. Keep the integration
worktree while the campaign is open.

## 5. Rewrite Current Work

Preserve the document's readable structure when updating it. Put new results
in their owning evidence section, retain prior facts and limits, and split
growing explanations into descriptive subsections. Follow the shared
[writing guidance](../plc-planning/references/writing.md); keep generic
workflow instructions in skills rather than copying them into packets.


If the plan is an active packet in an older shape, convert it first with
`plc-planning`'s [old-packet conversion](../plc-planning/references/old-packet-migration.md),
then update it. Don't add a second status block beside the old one.

Rewrite the plan's Current Work block in place with the keys of `plc-planning`'s
[shared template](../plc-planning/references/shared-format.md), in its order:
Status, Owner, "Last updated" (today, the branch, and its commit), then the
other keys and where the work lives (after tidying). Keep Owner, Depends on,
Priority, and any `Replaces:` or `Superseded by:` line unless the evidence or
the user changes them. Replace the old content; history goes to the Log. When
Status changes between Planned and In progress, follow `plc-planning`'s
[lifecycle folders](../plc-planning/references/shared-format.md#lifecycle-folders) rule. Never
set Status to Complete or move the packet to `completed/`; finishing is
`plc-wrapup`'s job. When the work looks finished, say so and offer it.

Grow the plan first, following `plc-planning`'s
[Growing a packet](../plc-planning/references/packet-files.md#growing-a-packet) rule: when a
trigger in its [Adding files](../plc-planning/references/packet-files.md#adding-files) rule
holds for a file the plan lacks, including for what this update records as
approved, such as a requirement for a new CLI flag, add that file now,
turning a one-file plan into a folder. Don't leave that information in a
Log line or a README section instead.

Then, in the plan's README:

- Update the affected rows of the `## Phases` table under `plc-planning`'s
  [Phases rules](../plc-planning/references/shared-format.md#phases). Each changed note names the
  merge request or commit. Mark a phase Verified or Live only with its
  evidence in the note; otherwise give it the word `plc-planning`'s
  [Words](../plc-planning/references/shared-format.md#words) rules give.
- Update the `## Merge requests` table, if the plan has one, as
  `plc-planning`'s [Merge requests](../plc-planning/references/shared-format.md#merge-requests)
  rule says. Change only the plan, never the host.
- Add one dated line to `## Log` for each state change, decision, or
  surprise since the last update. A gap (see below) that nobody had named
  before this update counts as a surprise. A line about a merge names its
  merge request or commit. Don't change older Log lines.
- Compare each requirement ID, in `## Done when` or SRD.md, and each planned
  task with what shipped. A gap is a requirement or planned task that the
  shipped code does not meet, although its phase's work has merged, or the
  plan, a report or the user calls it done. Work that the plan, a commit
  message or the user already said is still to be built is not a gap while
  its phase stays In progress: the phase note names it. Record each gap in
  one of two ways:
  - as a new phase row, Planned, or Deferred only with the user's approval.
    Write `moved to P<n>` in the old phase's note, and choose the old
    phase's word from the parts it still holds;
  - or as an `Open question:` line naming what it blocks and whom it waits
    on. The gap then stays a part of its phase.

  Never mark a requirement met without its evidence.
- Record each decision the user approved in this conversation as a dated
  `Decision:` Log line, following `plc-planning`'s
  [open questions](../plc-planning/references/shared-format.md#open-questions) rule. When it
  adds a requirement, add the requirement where the plan now keeps them,
  with the next ID and a check, as the
  [requirements rules](../plc-planning/references/shared-format.md#requirements-and-checks)
  say. Record an unapproved one as an `Open question:` line; it adds no
  requirement and no file. Remove blockers the evidence has cleared.

Don't reword existing requirement or design text: when code and a
requirement disagree, add an open question. Moving a requirement into
SRD.md with its ID, text and check unchanged is not a change. Don't mark
the plan Complete while a requirement lacks its evidence.

Then run `python3 <skills-dir>/plc-planning/scripts/format_check.py --packet <packet> --strict`
and fix what it reports in the parts you changed. When a finding needs the
user's decision, such as a status that disagrees with the evidence, ask
instead of guessing. When this update added, changed or dropped approved
scope, such as a new requirement, run `plc-planning`'s
[independent review](../plc-planning/SKILL.md#independent-review) on it.

**Which copy, and where to commit:**

- Update the copy where the work continues: the integration or work branch
  the plan travels with, or `main` when there is none. If the newest copy is
  only on `origin`, don't edit an older local copy; say to pull.
- Skip a copy that has uncommitted changes you didn't make, or where another
  agent is working. Report what you would have changed. An uncommitted diff
  that touches only the Current Work block is usually an earlier checkpoint's
  edit waiting for delivery: rewrite it in place within existing authorization.
- A checkpoint edits only plan files; it does not commit unrelated source.
  Keep related records together for the next authorized delivery with the
  work. If a standalone checkpoint commit is requested or required, batch
  this checkpoint's plan files as `docs(plan): update <plan> status`, after
  `git diff --check`. Do not create one commit per status or validation result.
- On the default branch, commit only when the repo's `AGENTS.md` or the plan
  says plan updates go straight there, or the user authorized it. Otherwise
  leave the edit uncommitted and report where its next delivery belongs.
- A plan in another repo is delivered there, following that repo's rules;
  combine related records for the checkpoint rather than each product MR.
  Push it only when that repo's instructions or the user authorize it.
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
`plc-wrapup`.

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
