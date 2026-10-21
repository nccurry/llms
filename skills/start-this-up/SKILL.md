---
name: start-this-up
description: Prepare isolated git work for a new feature by creating a safe feature branch and linked worktree from main without disturbing ongoing work in the current checkout. Use when the user says "start this up", "start a new branch/worktree", "create a feature worktree", "set up isolated work for this task", or asks Codex to begin work on a feature that should later merge back into main.
---

# Start This Up

## Operating Rules

Treat this as the safe beginning of a git worktree workflow. The goal is: a new local feature branch exists, a linked worktree exists for that branch, the branch starts from the best available main ref, and all future task work happens in the new worktree.

- Start only when the user explicitly asks to create isolated work, a feature branch, a worktree, or to begin a task that should be separated from ongoing work.
- Do not hard-code a branch prefix. Use the user's requested branch name first; otherwise follow repository branch naming conventions from instructions, docs, or recent branch patterns. If no convention is discoverable, prefer `<git-username>/<feature-slug>`.
- Never stash, reset, delete, overwrite, or switch away from user work to force progress.
- Do not treat a dirty current worktree as a blocker when the workflow can create the new worktree without mutating it. Report it so the user knows it remains untouched.
- Do not pull or fast-forward a dirty main worktree. Prefer using an updated remote main ref after `git fetch` when a remote exists.
- Do not reuse an existing branch or directory unless the user explicitly asked for that exact branch or path.
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

5. Continue from the new worktree.
   - Treat the new worktree path as the working directory for all implementation, testing, and git commands related to the feature.
   - Leave the original worktree and any uncommitted work exactly as found.

## Existing Branches

If the user asks to continue an existing branch:

- Use `git worktree list --porcelain` to see whether that branch already has a worktree.
- If it already has a worktree, continue from that path instead of creating another one.
- If the branch exists but is not checked out anywhere, create a worktree without `-b`:

```powershell
git worktree add <absolute-target-path> <branch-name>
```

- If the branch exists and its base is ambiguous, report that before making changes.

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
- any existing dirty work intentionally left untouched
- anything intentionally not done, such as pushing the branch

If the branch was created or the thread was switched onto it, emit the Codex app git directive in the final response:

```text
::git-create-branch{cwd="<absolute-target-path>" branch="<branch-name>"}
```
