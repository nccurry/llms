# Worktree layout and holds

Read before creating a linked worktree, review copy, or untracked task output.
`clean-stale-worktrees` relies on these conventions to find and remove work.

## Where checkouts go

Use the repository's AGENTS.md "Worktrees" section when it exists. Otherwise:

```text
<primary-worktree-parent>/<repo-name>-wt/<campaign>/<checkout>
```

- `<campaign>` groups related work: a PLC ID such as `l52`, a ticket ID, or the
  feature slug for standalone work.
- `<checkout>` names its role: a short task name, `integration`, or
  `review-<short-commit>`.
- Create every checkout, review copy, and untracked output for the campaign
  under its campaign folder. Do not create new sibling folders next to the
  primary checkout.
- Never reuse a folder for a different branch. Create a new checkout instead.

## Where evidence and output go

Follow the repository's AGENTS.md for how it tracks evidence. Some repositories
commit evidence; others keep plans and their records in another repository.

- Useful decisions, remaining work, and short validation outcomes go into the
  committed plan or work record, wherever the repository keeps it.
- Evidence the repository tracks goes to its documented in-repo location.
- Untracked bulky output (logs, captures, builds, staging copies) stays in the
  checkout's ignored build folder, or in `<campaign>/_output/` when it must
  outlive one checkout. It is deleted with the campaign.
- Do not create "retained", "preserved", "archive", or evidence folders outside
  the campaign folder, and do not move expired output somewhere else instead
  of deleting it.

## Holds

A hold keeps a checkout from being cleaned up. Make it a Git worktree lock, not
a note in a plan or handoff:

```sh
git worktree lock --reason "<owner>; keep until <condition>; <YYYY-MM-DD>" <path>
git worktree unlock <path>
```

Lock only checkouts whose local state must survive cleanup, such as uncommitted
source or output a named check still needs. Unlock when the condition is met.
An unlocked checkout with no local changes may be removed once idle; its branch
is kept.

## Review and verification copies

Prefer reading the child's own checkout. When a separate copy is needed, create
it detached under the campaign and remove it in the same step:

```sh
git worktree add --detach <campaign>/review-<short-commit> <commit>
git worktree remove <campaign>/review-<short-commit>
```

## Containers

Run containers that write into a checkout as the invoking user. Use the
repository's wrapper when it has one; otherwise, on Linux and macOS, pass
`--user "$(id -u):$(id -g)"`. If root-owned files are created anyway, report
them, because cleanup cannot remove them.

## AGENTS.md section template

Repositories may adapt this section:

```markdown
## Worktrees

- Root: `../<repo-name>-wt/<campaign>/<checkout>`; campaign is the PLC ID,
  ticket, or feature slug. Never reuse a folder for another branch.
- Evidence: <committed under `docs/evidence/` | recorded in the plan packet in
  `<other repo>`; raw output stays untracked under the campaign folder>.
- Holds: `git worktree lock --reason "<owner>; keep until <condition>; <date>"`.
  Unlocked, clean, idle checkouts may be removed; branches are kept.
- Containers: <task wrapper | `--user "$(id -u):$(id -g)"`>.
```
