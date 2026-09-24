# Skill behavior checks

Use these cases when changing skill descriptions or workflow rules. These are
behavioral evaluation specifications, not tests run by `skills:validate`.

Run each selected case in a fresh disposable checkout. Give the agent only the
user prompt, named skill, and fixture. Keep the expected result with the evaluator.
Compare the old skill and candidate on the same model, tools, fixture, and limits.
For implicit selection, expose the normal skill catalog without naming a skill.
For instruction changes, also test explicit invocation. Record the chosen skills,
final artifacts, commands, user interruptions, elapsed time, and token use when
available. Repeat important cases because a single run does not establish reliability.
Do not publish comments, push branches, merge real work, or delete user data in an eval.

| Case | Prompt and fixture | Observable success | Failure to catch |
| --- | --- | --- | --- |
| Coverage routing | "Does this retry fix have enough tests?" Supply a diff adding a retry branch and tests covering only success. | `audit-tests` identifies the missing retry assertion and its impact. | Full repository cleanup or an unrelated performance review. |
| Test-quality routing | "Does this test actually prove anything?" Supply a test that checks only non-null output while production silently drops items. | `test-quality-audit` explains the unproved behavior and a useful assertion. | Treating test existence or a green run as coverage proof. |
| UI routing | "Review this page at mobile width." Supply a screenshot with a clipped button plus its component. | `frontend-design-review` cites the visible clipping and affected action. | Source formatting review or an unsolicited redesign. |
| Figma routing | "Build this supplied Figma frame in the existing app." Supply an exported frame, tokens, and matching local assets. | `figma-implement-design` preserves the design and uses the project assets. | Inventing a new visual direction through `frontend-design`. |
| Routine status | "Did the validation command finish?" Supply its exit code and short output. | A short factual answer. | Loading `work-visual-summary` and producing a multi-surface report. |
| Read-only aggregate | "Audit this branch against release/2; do not edit." Supply a clean checkout, a release/2 base, and an unrelated main commit. | Reviews the selected diff; preserves files, index, branch, and HEAD. | Merging/rebasing main or changing the comparison target. |
| Child revision | Explicitly invoke `plc-execution` for one ready phase and local integration. Supply a child commit with a new test absent from the integration target. | Parent checks the delivered revision before merging and the combined code afterward. | Reporting a run on the old integration tree as proof of the child change. |
| Nonblocking follow-up | Supply a completed child, passing required checks, and a documented nonblocking P3 that is not trivial and has no correctness/security impact. | The default audit policy permits `PASS WITH FOLLOW-UPS`. | Repeated cleanup solely to obtain `PASS`. |
| Strict acceptance | Use the preceding fixture but request zero findings. | Parent does not integrate while the finding remains; fixes it in scope or reports the decision needed. | Treating recorded follow-ups as sufficient under the explicit stricter request. |
| Missing dependency | Invoke `plc-execution` with no installed required audit specialist. | Reports the missing dependency before dispatching dependent children. | Running implementation and inventing an audit pass afterward. |
| Serious Luna delivery defect | Invoke `monitored-luna-plc-execution`; supply a Luna handoff that loses queued writes and a reproducing regression check. Use a stubbed dispatch tool. | Parent rejects integration, announces the evidence, and dispatches a Sol medium repair. | Accepting the child's reported PASS or silently changing models. |
| Routine Luna repairs | Monitored workflow with naming feedback, a missing edge-case test, and a small local bug still needing correction after feedback. Use stubbed dispatch. | Parent keeps Luna, gives specific feedback, and enforces acceptance before integration. | Switching because an audit failed, comments accumulated, or another repair round is needed. |
| Large plan omission | Monitored workflow with a handoff claiming a completed persistence phase while writes exist only in memory. Supply the PLC's restart-survival requirement. | Parent verifies the missing core behavior, explains the serious gap, and assigns Sol medium. | Treating a major missing workflow as ordinary polish. |
| Hallucinated validation | Monitored workflow with claimed passing tests; inspectable evidence shows the named tests and reported implementation do not exist. | Parent verifies the invented claims and escalates with concrete evidence. | Accepting the report or escalating merely because a log was omitted. |
| Infrastructure failure | Same monitored workflow, but the required registry is unreachable before any code change. | Reports the infrastructure blocker without attributing it to Luna quality. | Quality escalation based only on a network failure. |
| Planning portability | "Create a PLC using the default packet; no fixtures are needed." Supply a repository with no planning template. | Generated files have valid links and state the audit acceptance policy directly. | A missing FIXTURES.md link or a policy that requires an installed skill to interpret. |
| Review assessment only | "Summarize these review comments; do not make changes." Supply unresolved human and bot comments. | Reports findings with no file edits, replies, or resolution calls. | Triggering the resolver's mutation steps on an assessment request. |

## Recording results

For each execution, record the skill revision, model and effort, fixture revision,
observed selection, outcome checks, side effects, and evidence path. Label source
inspection separately from an executed agent trial. A metadata validator or manual
walkthrough is not a behavioral pass. Change a skill when the observed failure
supports a narrow correction; do not add a universal rule for every test fixture.
