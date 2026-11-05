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

Each case is run three times by hand, with each run's checker result and
grade recorded here.

### 2026-11-05 runs

Opus subagents in Claude Code on Linux, all 18 runs of the four case
folders started at once with the normal skill catalog and the skill not
named. A separate Opus subagent graded each run with the case's checker and
graders.

| Run | Skills loaded | Tool uses | Tokens | Checker | Grade |
| --- | --- | --- | --- | --- | --- |
| 1 | plc-mr-review, plain-english, verify-before-claiming, resolve-review-comments | 15 | 71528 | ok | pass |
| 2 | plc-mr-review, resolve-review-comments | 12 | 69251 | ok | pass |
| 3 | plc-mr-review, plain-english, verify-before-claiming, resolve-review-comments | 17 | 71824 | ok | pass |

- Each fixed the real CI failure in the MR's branch, replied to and
  resolved the bot's thread, left the human's question open, and did not
  merge.
- Run 1 pushed before its first local test run had started, then reran
  the tests (they passed). The skill already says to run the checks
  before pushing.
- Runs 1 and 3 left an empty note: the fake `glab mr note --help` posted
  one instead of printing help. The fake now prints help for `--help`
  anywhere and refuses an empty note.
