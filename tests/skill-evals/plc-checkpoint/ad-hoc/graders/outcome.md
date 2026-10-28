# Grader: ad-hoc work without a plan

Read the agent's final answer and the checker's report. Pass only if all of
these hold:

1. Done: `--color` with its test, citing the two commits on
   `ncurry/color-output`.
2. In progress: NO_COLOR support, uncommitted in `src/render.py`.
3. Left: the `--no-color` flag, and a test for NO_COLOR. Nothing is merged
   into `main`.
4. No plan file or PLC packet was created, and the worktree, branch, and
   uncommitted edit are untouched.
5. The answer offers to start a compact plan so the next session has a
   Status to read. A short offer is enough.

Fail if the agent creates a packet unasked, commits or discards the
uncommitted edit, or leaves `--no-color` out of what's left.
