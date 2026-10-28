# Proposal: one Status section, plc-checkpoint, and wrap-this-up

Status: built, 2026-10-27. Replaces [plc-status-skill.md](plc-status-skill.md).

**Update, 2026-10-28:** `main` gained its own replaceable "Current Work"
block and a compact plan while this was being built. The two were merged: the
skills read and rewrite Current Work, per-phase state lives in the Phase Status
table in `IMPLEMENTATION_PLAN.md`, and the compact plan replaces the one-page
plan. From this design, Current Work gains the branch and commit on "Last
updated" and the "Where the work lives" table. Below, "Status section" means
the Current Work block.

## Problems this fixes

1. **Coming back the next day.** You need a refresher on what an agent was
   doing, where it got to, and what's next.
2. **Plans go stale.** Status is spread across sections, appended instead of
   replaced, and finished plans sit beside active ones.
3. **Worktrees pile up on disk.**

## Your workflow, and which skill covers each step

| Step | Skill |
| --- | --- |
| Explore | `repo-navigation` and the audit skills |
| Plan | `plc-planning`: a full PLC, or a one-page plan for ad-hoc work that will run past one session |
| Start or resume work | `start-this-up` |
| Do the work | `plc-execution` and the monitored-* skills |
| Get an update, mid-flight or the next morning | `plc-checkpoint` (renamed from `plc-status`) |
| Merge into main and finish | `wrap-this-up` |
| Sweep abandoned work | `clean-stale-worktrees` |

## Shared rules

**One Status section per plan.** It is the only place current state lives,
and it is replaced, not added to. It sits in the packet's `README.md` (or at
the top of a one-page plan) and holds:

- overall status and the date and commit it was last checked against ("as of")
- one row per phase or task: state, owner, and evidence
- where the work lives: each worktree, its branch, and its state
- the next step
- what it's blocked on

Decisions and open questions keep their own tables. The phase table in
`IMPLEMENTATION_PLAN.md` loses its Status column, so state is never recorded
twice.

Four skills write it: `plc-execution` after each merge and phase, `start-this-up`
when it creates or resumes a worktree, `plc-checkpoint` when you ask, and
`wrap-this-up` at the end.

**States** stay as they are: planned, in progress, implemented, merged,
verified, live, plus blocked, deferred and dropped.

**Merged into main means finished, locally and on the remote.**

**Cleanup is split three ways:** checkpoint tidies what's already merged;
wrap-this-up cleans up everything for the work it lands; clean-stale-worktrees
sweeps abandoned work.

**Finished plans move.** When wrap-this-up completes a plan, it moves to the
repo's done folder (`<plans folder>/done/` unless the repo has its own
convention). A partly finished plan stays where it is.

## plc-checkpoint

For when you want an update and will keep working. It doesn't merge.

1. **Find the plan:** the argument, the conversation, the branch, then the
   repo's plan folders. The plan may be a PLC in this repo, a plan in another
   repo (the repo's `AGENTS.md` or the packet says where), or nothing at all
   for ad-hoc work.
2. **Read the last Status first**, and its "as of" commit.
3. **Check what changed since then:** fetch, then read git, worktrees, PRs/MRs,
   checks, this conversation, and other repos the plan waits on.
4. **Rewrite Status** with the latest state and commit it on its own, on the
   branch where the work continues. A plan in another repo gets its own commit
   there. A packet without a Status section gets one. Ad-hoc work with no plan
   gets an offer to start a one-page plan; nothing is created unasked.
5. **Tidy what's finished:** remove worktrees and branches whose work is merged
   into main or the integration branch, delete remote branches merged into
   main, and remove review copies and output nothing needs. Keep anything with
   unmerged commits, uncommitted files, a worktree lock, or another agent in it.
6. **Report:** what changed since the last status, then done, in progress,
   left, decisions, blockers, what was tidied, and records updated.

"Just tell me" skips steps 4 and 5.

## wrap-this-up

For when you're done, or done for now, and want it on main.

1. **Run plc-checkpoint** steps 1 to 5.
2. **Collect what's in flight:** every branch with unmerged commits for this
   work. Commit task-owned uncommitted changes. Skip a checkout another agent
   is using (a lock or uncommitted changes that aren't this task's), and say so.
3. **Choose the route:** your words, then the plan, then the repo's convention.
   Direct: merge into main and push. PR/MR: open or update it, and merge only
   when you say so.
4. **Check the combined result** with the repo's required checks. Unfinished
   work can merge; failing checks stop the merge, and it asks.
5. **Merge and confirm** main (on the remote when there is one) contains each
   branch.
6. **Finish the plan:** rewrite Status. If every requirement passed, mark it
   complete and move it to the done folder. Otherwise it stays, with what's
   left listed.
7. **Clean up this work:** after a merge into main, remove every worktree and
   delete local and remote branches and the campaign folder. With a PR/MR left
   open, remove the worktrees and keep the branch until it merges.
8. **Report** the route, merge commit, checks, what's left, and what was
   removed or kept.

## start-this-up

- Record the new worktree and branch in the plan's Status.
- Run the repo's tests in the fresh worktree before work starts, so a later
  failure isn't blamed on the new work. (From superpowers'
  `using-git-worktrees`.)
- **Resume** a backlog plan: reuse its branch and worktree (or recreate the
  worktree), bring the branch up to date with main using the repo's merge or
  rebase convention, then read Status and report where things stand.

## clean-stale-worktrees

A branch whose commits are all contained in a branch being kept, such as a
child merged into the integration branch, may be deleted. Nothing is lost.

## Choices made

| Question | Answer |
| --- | --- |
| Rename `start-this-up` / `wrap-this-up`? | No. The names match what you say, and both serve ad-hoc work |
| Prefix like `ncc:`? | No. Skill names allow only lowercase letters, digits and hyphens. Packaging as a plugin later gives `ncc:` in Claude Code for free |
| Push a plan kept in another repo? | Only when that repo's `AGENTS.md` says plans go straight to main |
| Push after a direct-route wrap-up? | Yes; skip it when there's no remote |
| Borrow from superpowers? | The clean test run in a fresh worktree, and tests on the merged result before pushing |

## Evals

Cases live in `tests/skill-evals/plc-checkpoint/` and
`tests/skill-evals/wrap-this-up/`. Each fixture writes `_expect.json` saying
which worktrees and branches must be gone; the checker fails on missing
removals and on any removal not listed.

plc-checkpoint: the seven existing cases, plus `morning-refresh` (stale Status,
a merged child to remove, an in-progress child to keep), `dirty-finished`,
`ad-hoc`, and `plan-in-other-repo`. `origin-ahead` now expects its merged
worktree and branches removed.

wrap-this-up: `direct-mid-stream`, `complete-moves-plan`, `failing-checks`,
`active-agent`, and `near-miss-status`. The PR/MR route needs a host login and
has no runnable case yet.

## Build order

1. plc-checkpoint evals, the Status format in `plc-planning`, plc-checkpoint,
   and the `plc-execution` update.
2. wrap-this-up evals, then the skill.
3. `start-this-up` resume and clean test run; the `clean-stale-worktrees` rule.
4. Installer, dependency list and docs; run the evals.
