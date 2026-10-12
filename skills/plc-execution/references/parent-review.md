# Parent review

Read before accepting the first child delivery. The parent owns delegation,
review, integration, and evidence; it never substitutes a child's PASS or green
CI for its own inspection.

Read the actual diff from the assigned base through the delivered commit and
enough surrounding code to judge it. Review subsequent repairs too. Check:

- Named requirements/design goals and completion-map claims match current code.
- Logic, failure paths, state, and resource ownership fit connected behavior.
- Tests prove changed behavior and relevant failures; fixes have not weakened
  assertions or removed needed coverage.
- Names, control flow, boundaries, and dependencies solve needs in this scope.
- Changes stay within assignment and check/audit claims have real evidence.

Reproduce checks needed for correctness against the delivered commit in its
worktree. Coordinate expensive builds so reviewers do not compete for them.
Run required combined checks after integration.

Keep rejected work out of the target until repaired, strictly audited, and
reviewed. Give concrete feedback with source, behavior, missing acceptance, or
failing check evidence. Retain prescribed model settings; apply any escalation
rule in the explicitly invoked monitored skill.

The parent coordinates one read-only reviewer per required audit specialist
in bounded waves. Implementation children request this review and make repairs;
they do not launch recursive reviewers. Preserve provenance and rerun only
invalidated reviews/checks during convergence.

If a finding or missing check remains after repair/final verification, report
the exact open work. Resolve routine repairs; ask the user only about material
decisions or additional authorization under the base skill's decision rule.
