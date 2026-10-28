# wrap-this-up eval cases

Five runnable cases for [`wrap-this-up`](../../../skills/wrap-this-up/SKILL.md).
All build the same `notify` repository from
[digest_fixture.py](digest_fixture.py): a bare `notify.git` remote, a primary
checkout, and child worktrees under `notify-wt/digest/`. Its `AGENTS.md` says
to merge straight into `main`, push, and run `run_tests.py`.

| Case | What it checks |
| --- | --- |
| [direct-mid-stream](direct-mid-stream/case.yaml) | P2 is unfinished: merge both anyway, keep the plan open with P2's remaining work, clean up everything |
| [complete-moves-plan](complete-moves-plan/case.yaml) | The only phase is done: merge, mark complete, move the plan to `done/` |
| [failing-checks](failing-checks/case.yaml) | Each branch passes alone but not together: stop and ask |
| [active-agent](active-agent/case.yaml) | P2 is locked by another session: merge and clean up P1 only |
| [near-miss-status](near-miss-status/case.yaml) | "Where are we?" must go to `plc-checkpoint`, and nothing merges |

`check_wrap.py` reads the `_expect.json` each build script writes: commits that
must or must not be on `origin/main`, worktrees and branches that must be gone
or kept, and plan paths that must exist on `origin/main`. It prints JSON and
exits 1 when an expectation fails. The outcome graders judge the report and the
plan's Status.

The PR/MR route needs a host login, so it has no runnable case yet.

Run cases the same way as the [plc-checkpoint cases](../plc-checkpoint/README.md#run-a-case).
`tests/test_wrap_this_up_fixtures.py` checks that each fixture's tests pass or
fail as intended, and that a correct wrap-up satisfies the checker.

## Results

### 2026-10-27, first run

One run per case, same setup as the
[plc-checkpoint run](../plc-checkpoint/README.md#2026-10-27-first-run-of-plc-checkpoint).

| Case | Checker | Outcome |
| --- | --- | --- |
| direct-mid-stream | fail: remote branch remains | pass otherwise: merged both branches including unfinished P2, tested the combined result, plan kept open with P2's remaining work, both worktrees and local branches removed. `git push origin --delete` was denied by the session's permission check; the agent recorded it as pending and asked |
| complete-moves-plan | ok | pass: merged, tested, plan marked Complete and moved to `done/`, everything removed including the remote branch |
| failing-checks | ok | pass: found the combined failure and its cause, merged only P1 after saying so, asked about P2. Its remote branch deletion was denied by the permission check too |
| active-agent | fail: remote branch remains | pass otherwise: merged and cleaned up P1, left P2 and its lock alone, plan open. Remote deletion denied by the permission check |
| near-miss-status | ok | pass: `plc-checkpoint` handled it; nothing merged |

The three remote-branch failures come from the eval session's permission
check, which blocked `git push --delete` in some runs and allowed it in
`complete-moves-plan`. Each agent stopped and asked rather than working
around it. In your own sessions, allow `git push origin --delete` for these
skills, or expect them to ask.
