---
name: start-this-up
description: Prepare isolated git work by creating a feature branch and linked worktree from main, or by resuming a backlog plan's existing branch and bringing it up to date with main, without disturbing ongoing work in the current checkout. Runs the tests first so later failures aren't blamed on the new work, and records the worktree in the plan's Current Work block. Use when the user says "start this up", "start a new branch/worktree", "create a feature worktree", "set up isolated work for this task", "pick up where we left off on this plan", or asks to begin or resume work that should later merge back into main.
---

# Start This Up

## Operating Rules

Treat this as the safe beginning of a git worktree workflow. The goal is: a local feature branch exists (new, or resumed from a backlog plan), a linked worktree exists for that branch, the branch starts from or is brought up to date with the best available main ref, and all future task work happens in that worktree.

- Start only when the user explicitly asks to create isolated work, a feature branch, a worktree, or to begin a task that should be separated from ongoing work.
- Do not hard-code a branch prefix. Use the user's requested branch name first; otherwise follow repository branch naming conventions from instructions, docs, or recent branch patterns. If no convention is discoverable, prefer `<git-username>/<feature-slug>`.
- Never stash, reset, delete, overwrite, or switch away from user work to force progress.
- Do not treat a dirty current worktree as a blocker when the workflow can create the new worktree without mutating it. Report it so the user knows it remains untouched.
- Do not pull or fast-forward a dirty main worktree. Prefer using an updated remote main ref after `git fetch` when a remote exists.
- Do not reuse an existing branch or directory unless the user explicitly asked for that exact branch or path, or is resuming a plan whose Current Work block names it (see Resume Existing Work). When resuming, skip preflight's `--branch` check, which treats an existing branch as a blocker.
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

1. Choose names.
   - Derive a short, lowercase hyphenated feature slug from the user's task.
   - Choose a branch name from, in order: the user's requested branch name, a repository naming convention, or `<git-username>/<feature-slug>`.
   - For the fallback username namespace, use the configured Git or hosting username when available; otherwise use the local system username. Normalize only as needed for a valid branch name.
   - Use the repository's AGENTS.md worktree root when it defines one; otherwise use `<primary-worktree-parent>/<repo-name>-wt/<campaign>/<feature-slug>`, unless the user provided a path.
   - Rerun preflight with the intended target:

```powershell
uv run --script <skill-dir>/scripts/start_up_preflight.py --path . --branch <branch-name> --worktree-path <absolute-target-path>
```

2. Sync the base ref.
   - If the repository has remotes, run `git fetch --prune`.
   - Use the remote main ref from preflight, such as `origin/main`, when it exists after fetch.
   - Use the local main branch only when no remote main ref exists or the user explicitly wants a local-only branch.
   - Do not run `git pull` in a dirty main worktree.

3. Create the linked worktree.
   - Run:

```powershell
git worktree add -b <branch-name> <absolute-target-path> <base-ref>
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

6. Record the worktree in the plan.
   - If the work has a plan with a Current Work block (see `plc-planning`), add the checkout, its branch, and its state to "Where the work lives", and update the next action, in the copy the new branch carries. Commit only the plan file, as `docs(plan): start <checkout>`.
   - Skip this for work with no plan.

7. Continue from the new worktree.
   - Treat the new worktree path as the working directory for all implementation, testing, and git commands related to the feature.
   - Leave the original worktree and any uncommitted work exactly as found.

## Resume Existing Work

Use this when the user picks up a backlog plan or asks to continue an existing branch.

1. Find the plan and read its Current Work block: where the work lives, the next action, and blockers. Without a plan, use the branch the user named. If Current Work names no branch that still exists (a wrap-up for now deletes merged branches), start a new branch from main with the normal workflow above.
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
5. Record the worktree and the update in the plan's Current Work block, as in step 6 above.
6. Report the plan's Current Work in a few lines: where the work stands, what changed on main since, and the next action. For a full update, run `plc-checkpoint`.

If the branch's base is ambiguous, report that before making changes.

## Stop Conditions

Stop and report clearly if:

- The requested branch already exists and the user did not ask to reuse it.
- The target directory already exists and is not an empty directory intended for this worktree.
- The target path is inside an existing worktree.
- No main, master, or remote default branch can be found.
- `git fetch --prune` fails and the user asked to start from latest main.
- The new worktree is not clean immediately after creation.
- Creating the worktree would require stashing, resetting, deleting, or overwriting unrelated work.

## Final Response

Report:

- branch created or reused
- linked worktree path
- base ref used
- whether fetch was run
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
