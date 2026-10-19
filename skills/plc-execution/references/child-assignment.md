# Child assignment

Read when assigning implementation or discovery work under PLC execution.

Every assignment includes:

- Absolute checkout, branch, immutable base, PLC files, and selected block.
- Prerequisites, named requirements/design goals, acceptance checks, and exit
  criteria. Discoveries do not expand these without the parent's scope review
  and any required user approval.
- Owned files, APIs, and behavior. State allowed exceptions explicitly; the
  default does not permit fixes outside the assignment.
- Integration route and target. For MR work, identify who opens the MR.
- Focused/project checks, required audit coverage, and reporting requirements.
- Completion-map rows and the proof required for each.
- Absolute paths to plain-english, design-for-change, and verify-before-claiming,
  with instructions to read/apply all three before work.
- Any prescribed model/effort and the parent's decision/escalation rules.
- The final cleanup target and the parent's cleanup ownership. Identify any
  files or running processes that must survive handoff.

Tell the child to read local instructions, source, PLC, goals, and prerequisites
before editing and report which skill paths it loaded. It must use only its own
checkout, not the integration checkout, another child's files, or main.

The child runs focused checks during work and the project checks covering its
delivery. After meaningful changes it pauses writers and asks the parent to
coordinate the strict audit, supplying scope, base, current revision/diff, and
existing evidence. It does not spawn implementation or review agents.

After parent-verified findings, the child repairs every actionable in-scope
issue, including P3, and reruns affected checks. An unresolved material choice
goes to the parent; independent work continues.

Update maintained project documentation when behavior changes, and record
completion evidence only in assigned PLC sections. Update current guidance in
place, preserve IDs and rationale, and reconcile conflicting text. Keep status
and evidence concise in the existing work list or status/evidence sections;
link results instead of repeating them or restating the skill's general workflow.
Keep session narration out of requirements and design.
Report proposed scope additions to the parent without adopting them. Stop at
the assigned exit criteria and required handoff; leave optional discoveries as
outside-scope follow-ups. Do not claim whole-phase completion for a smaller block.

Deliver a clean commit with changed files, tested revision, exact commands and
results, audit scope/verdict/evidence, findings fixed, and open decisions.
Only PASS satisfies strict audit acceptance.

A child may commit its branch but cannot merge/rebase shared branches. Push
or open an MR only as authorized by the assigned integration route. Before
release, report its final commit, needed modified/untracked/ignored files, and
running processes. Stop its own processes and release the checkout when the
parent confirms they are no longer needed. The parent verifies delivery and
removes the worktree and branch; the child does not delete its own checkout.
