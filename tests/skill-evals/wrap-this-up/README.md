# wrap-this-up eval cases

Six runnable cases for [`wrap-this-up`](../../../skills/wrap-this-up/SKILL.md).
All build the same `notify` repository from
[digest_fixture.py](digest_fixture.py): a bare `notify.git` remote, a primary
checkout, and child worktrees under `notify-wt/digest/`. Its `AGENTS.md` says
to merge straight into `main`, push, and run `run_tests.py`.

| Case | What it checks |
| --- | --- |
| [direct-mid-stream](direct-mid-stream/case.yaml) | P2 is unfinished: merge both anyway, keep the plan open with P2's remaining work, clean up everything |
| [complete-moves-plan](complete-moves-plan/case.yaml) | The only phase is done: merge, mark P1 Verified with evidence, mark the plan Complete with the historical-record line, move it to `completed/` |
| [unmet-requirement](unmet-requirement/case.yaml) | The only phase passes its tests but misses DIG-003: merge, but keep P1 In progress, record the gap, and keep the plan open |
| [failing-checks](failing-checks/case.yaml) | Each branch passes alone but not together: stop and ask |
| [active-agent](active-agent/case.yaml) | P2 is locked by another session: merge and clean up P1 only |
| [near-miss-status](near-miss-status/case.yaml) | "Where are we?" must go to `plc-checkpoint`, and nothing merges |

`check_wrap.py` reads the `_expect.json` each build script writes: commits that
must or must not be on `origin/main`, worktrees and branches that must be gone
or kept (with cleanup that applies only once a commit is merged), paths and
text that must or must not be on `origin/main`, and the plan's expected state.
It extracts the plan from `origin/main` and checks it with fixture_lib's
`packet_shape_problems`, which runs the shipped format check in strict mode
plus the evals' own rules, including the `@alex` owner. It reads the packet
status as a word, so `Done` counts as Complete, and checks whether Current
Work opens with the historical-record line.

It also compares the end state with `_snapshot.json`. A worktree or local
branch the run added must be gone, including the `_merge` checkout the skill
merges in. The primary checkout must stay on its branch, may only
fast-forward to `origin/main` or gain plan-only commits, and may keep
uncommitted changes only under `docs/plans/`. It prints JSON and exits 1 when
an expectation fails.
The outcome graders judge the report and the plan's Current Work, and the
cases that may edit the plan also use the shared
[plan-record grader](../plc-checkpoint/graders/plan-record.md), which runs the
planning skill's shipped format check on the plan in strict mode.

The digest packet uses the shared PLC template, owned by `@alex`, and is built
with the shared [fixture_lib.py](../fixture_lib.py).

The PR/MR route needs a host login, so it has no runnable case yet.

Run cases the same way as the [plc-checkpoint cases](../plc-checkpoint/README.md#run-a-case).
`tests/test_wrap_this_up_fixtures.py` checks that each fixture's tests pass or
fail as intended, that each packet has the shared shape, and that a correct
wrap-up satisfies the checker while a wrong one fails it.

## Results

Results before 2026-11-03 used the older packet shape: an older Current Work
block, phase state in the implementation plan, and a folder for finished
plans that is now `completed/`. The fixtures and graders now use the shared
PLC template, so those results do not cover the Owner, Log, evidence, gap and
historical-record points. The unmet-requirement case was first run on
2026-11-03.

### 2026-11-03, unmet-requirement runs

Three runs of the unmet-requirement case by Opus subagents. Each got the
prompt and chose its own skills. The grade is the one given at the time,
with the grader as it was then.

| Run | Skills loaded | Tool uses | Tokens | Checker | Grade |
| --- | --- | --- | --- | --- | --- |
| 1 | wrap-this-up | 24 | 106276 | ok | fail: point 4 |
| 2 | wrap-this-up | 25 | 111724 | ok | fail: points 4 and 5 |
| 3 | wrap-this-up | 26 | 116267 | ok | fail: point 4 |

- Point 4, runs 1 and 2: P1 read
  `In progress — DIG-001 merged @ <merge>; DIG-003 not started`, and the
  grader wanted Merged. Grader defect, now fixed: the owner decided on
  2026-11-04 that a phase with part of its work merged and part not started
  is In progress.
- Point 4, run 3: P1 read
  `Planned — DIG-001 merged @ <merge>; DIG-003 not started`. The agent
  applied plc-checkpoint's old rule, "A phase takes the earliest word, in
  the list's order, among its items", as written, so this was neither a
  grader defect nor the agent's own error. That rule has since been
  rewritten; Planned still fails.
- Point 5, run 2: one dated Log line named both the merge and the gap, and
  the grader wanted a line for each. Grader defect, now fixed: P1's word did
  not change, so the gap is the one event the Log rule asks for, and one
  line naming both passes.
- The grader's findings name no other failed point.
- These runs used the skill text and grader from before the 2026-11-04
  fixes, so the state-word and grader fixes have not been re-run yet.

### 2026-10-27, first run

One run per case, same setup as the
[plc-checkpoint run](../plc-checkpoint/README.md#2026-10-27-first-run-of-plc-checkpoint).

| Case | Checker | Outcome |
| --- | --- | --- |
| direct-mid-stream | fail: remote branch remains | pass otherwise: merged both branches including unfinished P2, tested the combined result, plan kept open with P2's remaining work, both worktrees and local branches removed. `git push origin --delete` was denied by the session's permission check; the agent recorded it as pending and asked |
| complete-moves-plan | ok | pass: merged, tested, plan marked Complete and moved to the folder for finished plans, everything removed including the remote branch |
| failing-checks | ok | pass: found the combined failure and its cause, merged only P1 after saying so, asked about P2. Its remote branch deletion was denied by the permission check too |
| active-agent | fail: remote branch remains | pass otherwise: merged and cleaned up P1, left P2 and its lock alone, plan open. Remote deletion denied by the permission check |
| near-miss-status | ok | pass: `plc-checkpoint` handled it; nothing merged |

The three remote-branch failures come from the eval session's permission
check, which blocked `git push --delete` in some runs and allowed it in
`complete-moves-plan`. Each agent stopped and asked rather than working
around it. In your own sessions, allow `git push origin --delete` for these
skills, or expect them to ask.
