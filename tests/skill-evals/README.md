# Skill evaluation cases

- [Stale TODO during PLC discovery](plc-execution/stale-todo/case.yaml)
- [Conflicting acceptance rerun](verify-before-claiming/conflicting-rerun/case.yaml)
- [Bounded loader optimization](performance-experiments/duplicate-load/case.yaml)
- [Retrospective on a premature success claim](review-agent-session/incorrect-diagnosis/case.yaml)

Build each fixture in a fresh empty directory outside this repo. Use the
case's working directory and prompt, then apply its outcome grader and run
its `check` command when listed.

Compare a fresh session with the skill named against a fresh session with the
normal catalog available. PLC execution is opt-in, so the unnamed discovery
case checks that an agent can answer a read-only request without treating it
as authorization to implement. The verification case checks whether the
agent selects verification guidance when asked for an evidence-based verdict.
For either comparison record the host, model, skill revision, skills loaded,
and observed outcome.

If the runner cannot read fixture files, supply their contents directly to
check the agent's judgment. Record that result separately from checks of skill
selection and file access.

For the first pilots of `performance-experiments` and `review-agent-session`,
repeat the same bounded workload or session review without the skill. Compare
the retained diff and benchmark evidence or the supported findings and replay
proposal, respectively.
