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

No runs yet. Each case is to be run three times by hand, with each run's
checker result and grade recorded here.
