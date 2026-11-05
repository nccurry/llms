# plc-mr-review eval cases

One runnable case for [`plc-mr-review`](../../../skills/plc-mr-review/SKILL.md).
It builds the `app` repository from [host_fixture.py](../host_fixture.py),
with its `retry-backoff` branch missing the delay cap, and the fake GitLab
host described in the [manage-tickets cases](../manage-tickets/README.md#the-fake-host).

| Case | What it checks |
| --- | --- |
| [ready-no-plan](ready-no-plan/case.yaml) | No plan. MR !7's CI fails, a review bot's thread names the cause, and a human asks a question. Fix the branch so CI passes with its tests unchanged, handle the threads with `resolve-review-comments` (the bot's resolved, the human's left open), and leave the MR open and unmerged |

The fake host works out CI for a commit by running the fixture's
`run_tests.py` on it, so pushing the fix turns CI green.
`check_mr_review.py` reads the fake host's state and calls against the
`_expect.json` the build script writes; its docstring lists the rules. It
prints JSON and exits 1 when one fails. The outcome grader then judges the
report, the replies, and whether `resolve-review-comments` handled the
threads.

## Run a case

Run it like the [manage-tickets cases](../manage-tickets/README.md#run-a-case),
with `<dest>/bin` first on `PATH` and `check_mr_review.py <dest>` as the
check. Do not name the skill in the prompt.

`tests/test_plc_mr_review_fixtures.py` builds the fixture, checks that it
sets up its situation, and checks that a correct result passes the checker
and a merged or wrongly resolved one fails it. It does not run an agent.

## Results

No runs yet. The case is to be run three times by hand, with each run's
checker result and grade recorded here.
