# plc-planning eval cases

One runnable case for [`plc-planning`](../../../skills/plc-planning/SKILL.md),
in the same shape as the [plc-checkpoint cases](../plc-checkpoint/README.md):
a `case.yaml`, a `fixture/build.py` that creates a git repository, and
Markdown graders.

| Case | What it checks |
| --- | --- |
| [small-change](small-change/case.yaml) | A durable plan for a small, bounded change is one file, `plc-<slug>.md`, in the shared PLC template: no SRD, SADD or implementation plan, and no code changes |

`check_plan.py` compares the fixture with the `_snapshot.json` its build
script wrote. The run must add exactly one plan, a one-file `docs/plans/planned/plc-<slug>.md`,
and change nothing else. The fixture's plans README and the planning skill's
sizing rule both name that shape for small work.
The plan must pass the planning skill's shipped format check in strict mode, as
a packet in `planned/`, and the evals' own rules for new packets, such as
section order and no placeholders, and name `@alex` as its owner. Both checks
come from `packet_shape_problems` in the shared
[fixture_lib.py](../fixture_lib.py). It prints JSON and exits 1 on a problem.
The outcome grader then judges the plan's content, and runs the shipped
format check on the plan too.

## Run a case

Run cases the same way as the
[plc-checkpoint cases](../plc-checkpoint/README.md#run-a-case), with
`check_plan.py <dest>` as the check. Do not name the skill in the prompt.

`tests/test_plc_planning_fixtures.py` builds the fixture and tests the
checker against a one-file plan and the ways a run can go wrong: a packet
folder, a side file, a code change, two plans, a misnamed or misplaced plan,
another owner, a missing template key, rewritten history, and an older plan
shape. It does not run an agent.

## Results

No runs yet. Each case is to be run three times by hand, with each run's
checker result and grade recorded here.
