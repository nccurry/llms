# plc-planning eval cases

Four runnable cases for [`plc-planning`](../../../skills/plc-planning/SKILL.md),
in the same shape as the [plc-checkpoint cases](../plc-checkpoint/README.md):
a `case.yaml`, a `fixture/build.py` that creates a git repository, and
Markdown graders.

| Case | What it checks |
| --- | --- |
| [small-change](small-change/case.yaml) | A durable plan for a small, bounded change is one file, `plc-<slug>.md`, in the shared PLC template: no SRD, SADD or implementation plan, no code changes, and no diagrams padding the plan |
| [substantial-phase](substantial-phase/case.yaml) | A substantial phase makes scope, steps and acceptance easy to find without copying template instructions |
| [growing-evidence](growing-evidence/case.yaml) | Checkpoint, explicitly invoked execution and wrapup preserve provenance, prior results, limits and pending acceptance |
| [design-comparison](design-comparison/case.yaml) | Alternatives and reader/reload flow use a suitable form without duplicating the behavior contract |

The new cases share [readable_fixture.py](readable_fixture.py), which builds
invented local repositories, [check_readable.py](check_readable.py), which checks
scope, packet shape and evidence facts, and [the readability rubric](readability.md).
The rubric owns judgments about organization and meaning; the checker does not
pretend a count of bullets or tables proves readability. The growing-evidence
rubric defines separate maintenance variants and their invocation rules.

`tests/test_readable_plan_fixtures.py` checks fixture construction and rejects
missing provenance and application edits. It does not run or grade an agent.

`check_plan.py` compares the fixture with the `_snapshot.json` its build
script wrote. The run must add exactly one plan, a one-file `docs/plans/planned/plc-<slug>.md`,
and change nothing else. The fixture's plans README names that shape for
small work, and none of the planning skill's triggers for adding a file
holds.
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

Each case is to be run three times by hand, with each run's checker result
and grade recorded here.

### 2026-11-03, small-change runs

Three runs of the small-change case by Opus subagents. Each got the prompt
and chose its own skills. The grade is the one given at the time, with the
grader as it was then.

| Run | Skills loaded | Tool uses | Tokens | Checker | Grade |
| --- | --- | --- | --- | --- | --- |
| 1 | plc-planning | 10 | 80336 | ok | fail: point 6 |
| 2 | plc-planning | 12 | 82028 | ok | fail: point 6 |
| 3 | plc-planning | 10 | 77485 | ok | fail: point 3 |

- Point 6, runs 1 and 2: the Log held the Created line and one dated
  `Decision:` line, and the grader allowed only the Created line. Grader
  defect, now fixed: the skill's Log rule allows one dated line per state
  change, decision or surprise.
- Point 3, run 3: its Next action was "Implement P1 on `main`; whoever
  picks it up adds their @handle to the P1 row", which names the whole
  phase, not a first step. Real agent behavior; the grader now gives an
  example of a concrete step.
- The grader's findings name no other failed point.
- Checked by hand against the current grader, using the saved run output;
  no agent re-run and no new grading: point 6 passes for runs 1 and 2.
  Point 3 asks for one concrete first step that names a file to change or
  a command to run. Run 3's Next action names neither, so it still fails.
  Runs 1 and 2 name files (`tests/test_harbor.py`, `harbor.py`); whether
  each also names a single first step is left to the next grading.
- These runs used the skill text and grader from before the 2026-11-04
  fixes; no run has used those fixes yet.

### 2026-11-05, small-change runs

Opus subagents in Claude Code on Linux, all 18 runs of the four case
folders started at once with the normal skill catalog and the skill not
named. A separate Opus subagent graded each run with the case's checker and
graders.

| Run | Skills loaded | Tool uses | Tokens | Checker | Grade |
| --- | --- | --- | --- | --- | --- |
| 1 | plc-planning, review-and-fix-plc | 9 | 77494 | ok | pass |
| 2 | plc-planning, review-and-fix-plc | 9 | 75002 | ok | pass |
| 3 | plc-planning, review-and-fix-plc | 10 | 79740 | ok | pass |

- Each wrote one `planned/plc-list-limit-check.md` with @alex as owner and
  changed no code. Runs 1 and 3 had a reviewer find and fix gaps (run 3's
  caught a design that would have changed the `--limit abc` error). Run 2
  could not start a reviewer because too many subagents were running, and
  said so instead of reviewing its own plan.

### 2026-11-05, small-change runs with point 11

Three runs of the small-change case at `ee72611`, graded with the grader's
new point 11 (no padding with diagrams).

| Run | Plan | Checker | Grade |
| --- | --- | --- | --- |
| 1 | `planned/plc-list-limit-check.md` | ok | pass |
| 2 | `planned/plc-list-limit-validation.md` | ok | pass |
| 3 | `planned/plc-list-limit-check.md` | ok | pass |

- `check_plan.py` printed `"ok": true` with no problems in all three. Each
  run wrote one file in `planned/`, and each plan passes the strict format
  check.
- No plan has a diagram, so point 11 is met in all three.
- Each run said the independent review could not run, because no reviewer
  was available in the eval.

### 2026-11-09, readable-plan comparison

Baseline: `c26b708` skill copies. Revised: the readable-plan changes on that
base. Codex CLI 0.163.0 used `gpt-6.1-sol`; Claude Code 2.1.238 used
`claude-sonnet-5-5` (including the host's `[1m]` designation). Each host ran
three fresh trials per row below. Execution was explicitly invoked; the other
cases used implicit selection from the normal installed catalog. Tool reads
or host-injected skill bodies confirm the intended workflow skill loaded.

| Host | Scenario / workflow | Baseline checker; rubric | Final revised checker; rubric |
| --- | --- | --- | --- |
| Codex | small-change / plc-planning | 3/3; 3/3 | 3/3; 3/3 |
| Codex | substantial-phase / plc-planning | 3/3; 3/3 | 3/3; 3/3 |
| Codex | design-comparison / plc-planning | 3/3; 3/3 | 3/3; 3/3 |
| Codex | growing-evidence / plc-checkpoint | 3/3; 3/3 | 3/3; 3/3 |
| Codex | growing-evidence / plc-execution | 3/3; 3/3 | 3/3; 3/3 after review |
| Codex | growing-evidence / plc-wrapup | 3/3; 3/3 | 3/3; 3/3 |
| Claude | small-change / plc-planning | 3/3; 3/3 | 3/3; 3/3 |
| Claude | substantial-phase / plc-planning | 3/3; 3/3 | 3/3; 3/3 |
| Claude | design-comparison / plc-planning | 3/3; 3/3 | 3/3; 3/3 |
| Claude | growing-evidence / plc-checkpoint | 3/3; 3/3 | 3/3; 3/3 |
| Claude | growing-evidence / plc-execution | 2/3; 2/3 | 3/3; 3/3 |
| Claude | growing-evidence / plc-wrapup | 1/3; 1/3 | 3/3; 3/3 |

Final comparison: baseline 33/36 for both checks and rubric; revised 36/36
checker, 35/36 raw model rubric, 36/36 after parent review. The rejected
finding is Codex execution trial 2: the grader calls SRD creation unauthorized,
but the skill's existing packet-growth rule requires that maintenance, and
every behavior cited by the SRD already appears in the fixture's `brief.md`.
REQ-001/REQ-002 and their checks move unchanged; no application code or new
behavior is added. The raw grade and separate review rationale were inspected;
this record retains the finding, adjudication and counts.

The three baseline failures omit explicit supplied-result attribution. Dates,
counts and pending browser acceptance remain present; the failure is lost
provenance, rather than a demonstrated execution of invented checks.

Earlier revised trials exposed a compact-plan section-order error and two
wrapup attribution omissions. The template now shows where custom sections
belong, planning's final validation explicitly checks order, and wrapup's
update step explicitly labels supplied results. All trials for each affected
scenario are repeated on both hosts, including previously passing runs.
Unchanged passing artifacts remain valid for unaffected scenarios.
There were 54 revised trial executions: the initial 36, six after the template
comment, and 12 after the final planning/wrapup instruction changes. The final
comparison uses 24 unaffected initial outputs and all 12 final affected outputs.
Older trials, including failures, were retained locally through acceptance.

Two checker corrections apply equally to saved baseline and revised outputs:
phase links accept deeper Markdown headings, and maintenance rejects a missing
supplied-result label/source reference. These enforce the existing contract
and rubric. The final comparison uses both corrections. The prose rubric is
graded with the same prompt by a tool-free Claude session; supported findings
are checked against the documents. A first grade missed two provenance
omissions, which inspection and the strengthened checker caught.

Limits: these are invented fixtures with delegation and external services
disabled. They test authoring and maintenance, not feature implementation or
real Git-host integration. Ambiguous early wrapup prompts were excluded and
replaced before comparison; paired prompts now match within each host. This
small sample does not prove a general improvement rate. Local prompts,
transcripts, documents, model/skill metadata and checker/grade records were held
in `/tmp/plc035/` through acceptance. Wrapup removed that disposable output
after remote delivery. Raw session logs are not published in this repository.

The evaluated four-skill source manifest covers planning, checkpoint, execution
and wrapup files, excluding Python caches. Its SHA-256 is
`293749db695426005d9b25c25444643f9b8290e4e530c2af5b5b715a36be30d1`.
The manifest was `/tmp/plc035/revised-source-manifest.json`; reviewed grades were
separate from raw model grades. All 72 compared trials confirm the intended
workflow skill loaded, and paired baseline/revised prompt bytes match per host.
Wrapup removed one extra blank line at the end of each of `packet-files.md`
and `writing.md`; their instructions are unchanged from the evaluated source.

Delivery was verified on both remote main branches on 2026-11-09: skill code
`4a6eb75`, board code `38ccfb9`, and completed packet `0ac16d1`. The exact board
delivery tree passes its full check: 3,534 unit/component tests, 117 binary
tests and 202 browser tests; all coverage measures exceed 96%. The temporary
verification copy and eval artifacts are removed. Both primary repositories
remain; unrelated in-flight board API work was excluded from this delivery.
