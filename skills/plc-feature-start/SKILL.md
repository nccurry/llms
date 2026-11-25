---
name: plc-feature-start
description: Set up or resume a single feature branch and linked worktree, with or without a plan. Use for "start this plan", "create a feature worktree", or "pick up where we left off" when the user wants checkout setup. Managed PLC execution sets up its own worktrees.
---

# PLC Feature Start

Use this for the rare case of starting one feature by hand. Work that
`plc-execution` runs gets its worktrees from that workflow instead. A plan
is optional: without one, skip the plan steps.

## Operating Rules

Treat this as the safe beginning of a git worktree workflow. The goal is: a local feature branch exists (new, or resumed from a backlog plan), a linked worktree exists for that branch, the branch starts from or is brought up to date with the best available main ref, and all future task work happens in that worktree.

- Start only when the user explicitly asks to create isolated work, a feature branch, a worktree, or to begin a task that should be separated from ongoing work.
- Do not hard-code a branch prefix. Use the user's requested branch name first; otherwise follow repository branch naming conventions from instructions, docs, or recent branch patterns. If no convention is discoverable, prefer `<git-username>/<feature-slug>`.
- Never stash, reset, delete, overwrite, or switch away from user work to force progress.
- Do not treat a dirty current worktree as a blocker when the workflow can create the new worktree without mutating it. Report it so the user knows it remains untouched.
- Follow [Sync main](#sync-main) before starting from main.
- Honor explicit requests for a new checkout. Otherwise inspect this task's existing checkouts first and continue in one assigned to the same task and branch when available and safe (see Resume Existing Work). Create another for a concrete isolation need; record that need and what happens to the older checkout. Never repurpose another task's checkout or reuse a directory for another branch. When resuming, skip preflight's `--branch` check, which treats an existing branch as a blocker.
- Do not push, create a remote branch, or open a pull request unless the user explicitly asks.
- Place the worktree under its campaign folder as described in [worktree layout](references/worktree-layout.md). Read that file before choosing a path.
- After creating the worktree, continue implementation commands from the new worktree path.

## Preflight

Run the bundled preflight script before creating branches or worktrees. Resolve `scripts/start_up_preflight.py` relative to this skill directory and launch it with [uv](https://docs.astral.sh/uv/) so the same command works on every platform:

```powershell
uv run --script <skill-dir>/scripts/start_up_preflight.py --path .
```

Use its JSON output to record:

- repository root
- current branch and current worktree path
- detected main branch
- remote main ref, if present
- recommended base ref
- primary worktree path
- existing worktrees and checked-out branches
- dirty status in the current and main worktrees
- any problems or warnings

If the script reports problems, handle them before creating anything. Common blockers are not being in a git repository, no detectable main or master branch/ref, an existing target branch, an existing target directory, or a target directory inside another worktree.

If the script is unavailable, manually gather the same facts with:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git remote
git worktree list --porcelain
git status --short
git show-ref --verify --quiet refs/heads/main
git show-ref --verify --quiet refs/heads/master
git symbolic-ref --quiet --short refs/remotes/origin/HEAD
```

## Workflow

Before replacing a checkout for the same assignment, read its work record.
If the branch and ownership still match and the checkout is safe to use,
follow [Resume Existing Work](#resume-existing-work). Otherwise run the
[cleanup check](../clean-stale-worktrees/references/cleanup-check.md) for
the predecessor. Remove it only if cleanup is already authorized for this
assignment. Record anything that must stay.

1. Choose names.
   - Derive a short, lowercase hyphenated feature slug from the user's task.
   - Choose a branch name from, in order: the user's requested branch name, a repository naming convention, or `<git-username>/<feature-slug>`. When the work belongs to a plan, put its ID and phase in the slug, such as `<git-username>/plc-12-p2-<feature-slug>`, so tools can match the branch to the plan; with no plan, use the slug alone.
   - For the fallback username namespace, use the configured Git or hosting username when available; otherwise use the local system username. Normalize only as needed for a valid branch name.
   - Use the repository's AGENTS.md worktree root when it defines one; otherwise use `<primary-worktree-parent>/<repo-name>-wt/<campaign>/<feature-slug>`, unless the user provided a path.
   - Rerun preflight with the intended target:

```powershell
uv run --script <skill-dir>/scripts/start_up_preflight.py --path . --branch <branch-name> --worktree-path <absolute-target-path>
```

2. [Sync main](#sync-main) and record the base commit.

3. Create the linked worktree.
   - Run:

```powershell
git worktree add -b <branch-name> <absolute-target-path> <base-commit>
```

   - Use quotes around paths on Windows when needed.
   - If the command fails because the branch or path already exists, stop and choose a new name/path or ask the user how to proceed.

4. Verify the new worktree.
   - Run:

```powershell
git -C <absolute-target-path> status --short --branch
git worktree list
```

   - Confirm the new worktree is on the intended branch and has a clean status.
   - If the repository has setup or restore steps that are required before coding, run the lightest normal setup step from the new worktree.

5. Run the tests before any work.
   - Run the repository's normal test command (from `AGENTS.md`, the task runner, or CI config) in the new worktree.
   - Report failures as already present on the base ref, with the failing test names, so they aren't later blamed on the new work. Don't fix them unless asked.
   - If there is no test command or it needs services that aren't available, say so and continue.

6. Record the checkout path, branch and current commit, owner, and purpose
   in the existing work record or handoff. If it needs a hold, record the
   release condition in the Git lock reason.
    - If the plan has a Current Work block, update the authoritative packet in
      the new branch or in the separate repository that owns the plan.
      First [hand off any local draft](../clean-stale-worktrees/references/cleanup-check.md#hand-off-a-local-plan)
      if the packet is moving between checkouts.
     Follow `plc-checkpoint`'s rewrite rules: add the checkout, branch and
     state to Where the work lives; set Last updated and Next action; change
     Status from Planned to In progress and move the packet as `plc-planning`
     says; then add a dated Log line. Keep any `## Code repositories`
     section and its URLs unchanged. Commit only plan files as
     `docs(plan): start <checkout>`.
   - With no plan, skip the plan update and keep the checkout details in the handoff.

7. Continue from the new worktree.
   - Treat the new worktree path as the working directory for all implementation, testing, and git commands related to the feature.
   - Keep feature changes in the new worktree and preserve any existing uncommitted work.
   - When this work has a ticket or the project uses tickets, run [manage-tickets](../manage-tickets/SKILL.md) for the start of work.

## Sync main

Use the repository's default branch if it has a different name.

1. If there is no upstream main or the user explicitly chose a local-only
   base, record the local main commit and use it. Otherwise, fetch the remote
   that hosts the intended main branch. Find its fetched ref, such as `origin/main`, and record the
   commit it points to. If you cannot verify a fresh upstream commit, report
   why and stop unless the user has authorized a fallback base.
2. Compare local main with the fetched commit. If local main is only behind
   and is already checked out in a clean, idle, unlocked worktree, fast-forward
   it there with `git -C <main-worktree> merge --ff-only <base-commit>`.
   Check the worktree just before updating it. If it has edits, is in use, is
   locked, or local main has its own commits, skip the update and report why.
   If main has no safe checkout or the fast-forward fails, report that too.
3. Use the recorded fetched commit for the new worktree, including when
   the local update was skipped.

## Resume Existing Work

Use this when continuing an established task or branch, including a backlog plan.

1. Find the plan and read its Current Work block: where the work lives, the next action, and blockers. Without a plan, use the branch named by the user or established for this task in the conversation and Git state. If that does not establish an existing assignment, start a new branch from main with the normal workflow above. Do not adopt a similarly named branch as proof of task ownership.
2. Use `git worktree list --porcelain` to see whether the branch already has a worktree. If it does, continue from that path. If not, create one in the campaign folder without `-b`:

```powershell
git worktree add <absolute-target-path> <branch-name>
```

3. Bring the branch up to date with main, so the work isn't built on a stale base.
   - Fetch, then compare: `git -C <path> rev-list --left-right --count HEAD...<remote-main>`.
   - If it's behind, update it with the repository's convention: merge `<remote-main>` into the branch by default, or rebase when `AGENTS.md` says so and the branch isn't shared or pushed for review.
   - Skip the update and report if the worktree has uncommitted changes, is locked, or another agent is using it.
   - On conflicts, stop, abort the merge or rebase, and report the conflicting files. Don't resolve them without the user.
4. Run the tests (step 5 above) on the updated branch.
5. Record the worktree and the update in the plan, as in step 6 above.
6. Report the plan's Current Work, or with no plan the branch's state, in a few lines: where the work stands, what changed on main since, and the next action. For a full update, run `plc-checkpoint`.

If the branch's base is ambiguous, report that before making changes.

## Stop Conditions

Stop and report clearly if:

- A requested new branch already exists. For an established task being resumed, use Resume Existing Work instead.
- The target directory already exists and is not an empty directory intended for this worktree.
- The target path is inside an existing worktree.
- No main, master, or remote default branch can be found.
- The upstream base could not be verified and there is no authorized fallback.
- The new worktree is not clean immediately after creation.
- Creating the worktree would require stashing, resetting, deleting, or overwriting unrelated work.

## Final Response

Report:

- branch created or reused
- linked worktree path
- base ref and commit used
- whether fetch succeeded and whether local main was updated, including why it was skipped when applicable
- whether the new worktree status is clean
- the test result on the starting commit, with any failures named
- for a resumed branch, how far behind main it was and how it was updated
- the plan's Current Work entry added, or that there is no plan
- any existing dirty work intentionally left untouched
- anything intentionally not done, such as pushing the branch

If the branch was created or the thread was switched onto it, emit the Codex app git directive in the final response:

```text
::git-create-branch{cwd="<absolute-target-path>" branch="<branch-name>"}
```
