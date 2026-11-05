# manage-tickets eval cases

Three runnable cases for [`manage-tickets`](../../../skills/manage-tickets/SKILL.md).
Each builds the same small `app` repository from
[host_fixture.py](../host_fixture.py): a bare `app.git` remote, a primary
checkout on `main`, and a pushed `retry-backoff` branch. What differs is the
project's ticket evidence, and the fake host the case installs.

| Case | What it checks |
| --- | --- |
| [no-tracker](no-tracker/case.yaml) | Nothing shows tickets: the MR opens with no ticket reference, and no ticket is created |
| [jira-key](jira-key/case.yaml) | `CONTRIBUTING.md` and a CI job require `PROJ-123: Summary` MR titles: the title starts `PROJ-481: `, and Jira is not written to, because its automation moves the ticket |
| [github-closes](github-closes/case.yaml) | The PR template and history use `Closes #N`: the PR body says `Closes #42`, and the issue stays open until the merge |

## The fake host

These cases need a code host and a tracker without a network or a login.
[fake_host.py](../fake_host.py) stands in for `glab`, `gh` and a `jira`
CLI. The build script copies it to `<dest>/_host/`, writes its state to
`<dest>/_host/state.json`, and puts wrappers for the case's tools in
`<dest>/bin`. Every call is logged to `<dest>/_host/calls.jsonl`. Its
docstring lists what it supports.

`check_tickets.py` reads the fake host's state and calls against the
`_expect.json` each build script writes; its docstring lists the rules. It
prints JSON and exits 1 when one fails. The outcome graders then judge the
report and how the agent learned the project's style.

## Run a case

Run cases the same way as the
[plc-checkpoint cases](../plc-checkpoint/README.md#run-a-case), with two
differences: start the agent session with `<dest>/bin` first on `PATH`, as
each case's `env` says, and use `check_tickets.py <dest>` as the check. Do
not name the skill in the prompt.

`tests/test_manage_tickets_fixtures.py` builds each fixture, checks that it
sets up its situation, and checks that a correct result passes the checker
and a wrong one fails it. It does not run an agent.

## Results

Each case is run three times by hand, with each run's checker result and
grade recorded here.

### 2026-11-05 runs

Opus subagents in Claude Code on Linux, all 18 runs of the four case
folders started at once with the normal skill catalog and the skill not
named. A separate Opus subagent graded each run with the case's checker and
graders.

| Case | Run | Skills loaded | Tool uses | Tokens | Checker | Grade |
| --- | --- | --- | --- | --- | --- | --- |
| no-tracker | 1 | create-mr-description, manage-tickets | 12 | 75620 | ok | pass |
| no-tracker | 2 | create-mr-description, manage-tickets | 13 | 70424 | ok | pass |
| no-tracker | 3 | create-mr-description, manage-tickets, plain-english, verify-before-claiming | 13 | 69405 | ok | pass |
| jira-key | 1 | manage-tickets, create-mr-description | 13 | 70235 | ok | pass |
| jira-key | 2 | create-mr-description, manage-tickets | 10 | 67979 | ok | pass |
| jira-key | 3 | manage-tickets, create-mr-description | 10 | 68201 | ok | pass |
| github-closes | 1 | create-mr-description, manage-tickets | 11 | 69179 | ok | pass |
| github-closes | 2 | create-mr-description, manage-tickets, plain-english, verify-before-claiming | 12 | 70216 | ok | pass |
| github-closes | 3 | create-mr-description, manage-tickets | 9 | 66314 | ok | pass |

- no-tracker: no ticket created or invented; each said why and offered to
  link one, two suggested recording the tracker in `AGENTS.md`.
- jira-key: every title starts `PROJ-481: `, the body uses a non-closing
  `Refs PROJ-481`, and nothing was written to Jira.
- github-closes: a first round failed the checker in all three runs
  because issue #42 asked for more than the branch did; each used
  `Refs #42` and explained why, which is the skill's partial-work rule.
  The fixture's issue now asks only for the helper, and the rerun above
  used `Closes #42` in all three.
- Harness artifacts, not skill failures: parallel runs shared one scratch
  folder and briefly overwrote each other's draft files (the agents
  noticed and republished), and the fake `gh` ignored `-q`, now fixed.
