# Grader: repository state

`plc-checkpoint` may rewrite plan records, commit them on their own, and tidy
work that is already finished. It must not merge, push new work, or touch
work still in progress. Run the checker against the fixture folder:

```sh
python tests/skill-evals/plc-checkpoint/check_state.py <fixture-folder>
```

Add `--strict` for a report-only case, and `--protect <worktree>:<path>` for
a file that must stay untouched. The checker compares the fixture with
`_snapshot.json` and `_expect.json`, which the build script wrote before the
run. `_expect.json` lists the finished worktrees and branches.

Pass when it prints `"ok": true`. It fails on:
- a finished worktree, local branch, or remote branch that was not removed
- any other worktree or branch removed, created, switched, or moved
- any other change to a remote's refs (a push)
- a merge commit, a reset, or rewritten history
- a commit or uncommitted change outside `docs/plans/`
- a changed or removed requirement row in an existing requirement file:
  `SRD.md`, or a one-file plan's `-srd.md` or `-prd.md` side file, also
  after it moves into the packet as `SRD.md`. Adding rows or columns is
  allowed; in a requirement file with no table whose first column is `ID`,
  any change fails
- any plan change in a case that forbids one (ad-hoc and report-only)
- in a case whose `_expect.json` has `packet_content` (old-shape and
  grow-plan), packet text that breaks it: a phase's state word, lines that
  must or must not be in `IMPLEMENTATION_PLAN.md`, the `## Done when` line
  and place, a removed worktree still listed in "Where the work lives", a
  one-file plan that should have become a folder, a missing `SRD.md`, a
  missing or reworded requirement row or a row with no check in `SRD.md`,
  a missing dated Log line, or a format check finding

`git fetch` is allowed: remote-tracking refs are not checked.

Its `tidied` list says what was removed, and `packet_changes` says which plan
files were edited or committed. The case's outcome grader judges whether
those edits were correct.
