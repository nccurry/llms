# plc-planning eval cases

One runnable case for [`plc-planning`](../../../skills/plc-planning/SKILL.md),
in the same shape as the [plc-checkpoint cases](../plc-checkpoint/README.md):
a `case.yaml`, a `fixture/build.py` that creates a git repository, and
Markdown graders.

| Case | What it checks |
| --- | --- |
| [small-change](small-change/case.yaml) | A durable plan for a small, bounded change is one README in the shared PLC template: no SRD, SADD or implementation plan, and no code changes |

`check_plan.py` compares the fixture with the `_snapshot.json` its build
script wrote. The run must add exactly one plan under `docs/plans/planned/`,
as `<slug>/README.md` or a one-file `plc-<slug>.md`, and change nothing else.
The plan must have the shared template's shape, checked by
`packet_shape_problems` in the shared [fixture_lib.py](../fixture_lib.py), and
name `@alex` as its owner. It prints JSON and exits 1 on a problem. The
outcome grader then judges the plan's content, and runs the planning skill's
shipped format check on the plan in strict mode.

## Run a case

Run cases the same way as the
[plc-checkpoint cases](../plc-checkpoint/README.md#run-a-case), with
`check_plan.py <dest>` as the check. Do not name the skill in the prompt.

`tests/test_plc_planning_fixtures.py` builds the fixture and tests the
checker against a README-only plan and the ways a run can go wrong: a full
packet, a code change, two plans, a misnamed or misplaced plan, another owner,
rewritten history, and an older plan shape. It does not run an agent.

## Results

No runs yet. Each case is to be run three times by hand, with each run's
checker result and grade recorded here.
