# Merge-request integration

Read only for an authorized MR/PR route. Follow the assignment's host, target,
and creator. By default the child opens its branch against the recorded target
after strict audit PASS and parent review. Describe resulting behavior, selected
work, validation, and known dependencies. Use structured arguments or a body
file for multiline descriptions.

Use authenticated host tools to inspect reviews and CI at the current revision.
Wait for pending required checks and reviews, then read their actual results.

- Fix supported actionable comments within scope and refresh affected tests
  and reviews. Inspect the resulting code; do not rely on a reply saying fixed.
- Reject incorrect comments with evidence. Identify outside-scope work before
  resolving or expanding it; do not silently broaden the assignment.
- Do not resolve actionable comments merely to make the MR appear clean.
- Reply or resolve only within existing user authorization and host policy.
  Leave human threads open when required by resolve-review-comments.
- Raise material unresolved requirements, contract, scope, security, or product
  decisions through the parent. Routine coding decisions follow established
  conventions without unnecessary user interruptions.

Recheck comments and CI after each update. Before merging, the parent reads the
current diff, validates delivery evidence, confirms strict audit PASS, all
required CI green at the final revision, and no unresolved actionable in-scope
review comment. A route authorizing review does not alone authorize final merge.

When the host is Codex desktop, attach every created PR to the current task
using attach_artifact. Use the equivalent host capability when available.
