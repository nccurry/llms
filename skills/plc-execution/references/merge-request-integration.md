# Merge-request integration

Read only for an authorized MR/PR route. Follow the assignment's host, target,
and creator. By default the child opens its branch against the recorded target
after strict audit PASS and parent review. Use `create-mr-description` before
opening the review. Refresh its description after published changes, rebases or
target changes, material validation updates, and before final merge readiness.
Keep the description tied to the current diff and applicable evidence.

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

After an authorized merge, inspect the host's actual merged state, source and
integration commits, and target before running the base cleanup procedure.
Commit useful implementation notes in the PLC packet before the final handoff.
After merge, task receipts and temporary output may be discarded without an
archive; their presence does not justify keeping predecessor checkouts.
An open or closed-but-unmerged review does not prove delivery. Account for local
commits beyond its merged source, including after squash or rebase integration.
If the review will merge later, record cleanup as pending with the exact PR/MR
and final target. Recheck when execution resumes; arrange a later monitor only
when requested. Keep pending cleanup visible in the final report.
