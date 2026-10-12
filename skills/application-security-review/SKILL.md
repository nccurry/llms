---
name: application-security-review
description: "Review application trust boundaries, authorization, untrusted input, execution, secrets, and sensitive data for concrete vulnerabilities. Use for security review or changes affecting those boundaries; dependency advisories belong to dependency-auditor."
---

# Application Security Review

Select the requested diff or component and its connected boundary behavior.
Read project security rules, deployment assumptions, and relevant tests. Review
source and local evidence; do not probe external services, read unrelated
secrets, or change production state without authorization.

## Inspect the boundary

Trace who can supply input, what they control, the authority used to process
it, and the protected resource/result. Follow the path through validation,
authorization, execution/storage, and output. Check relevant concerns:

- Authentication and per-action/resource authorization, including tenant and
  ownership boundaries.
- Injection into commands, queries, templates, paths, or interpreters.
- Path traversal, unsafe deserialization, file/URL access, and request forgery.
- Secrets and sensitive data in logs, errors, storage, responses, and fixtures.
- Unsafe defaults, session/token lifetime, state-changing requests, and failure
  behavior.
- Resource exhaustion where attacker-controlled work has a concrete missing
  bound.

Select concerns based on the actual architecture. Cite the governing contract
or supported threat scenario rather than importing a generic checklist.

## Establish evidence

A finding needs a reachable path, attacker capability, failed control, impact,
and source references. Reproduce with safe synthetic local inputs when useful.
Separate direct proof from inference; put unsupported possibilities under blind
spots. Dependency versions alone belong to `dependency-auditor`.

Report severity, confidence, affected boundary, evidence, concrete correction,
and relevant regression checks. Avoid exposing real credentials in the report.
State inspected scope and unverified assumptions when no issue is found.

When `audit-codebase` delegates this review, remain read-only, return findings
to its ledger, and let the parent own verdicts, fixes, and expensive checks.
For an authorized repair, keep behavior within scope and raise material
authorization/security-contract decisions before dependent changes.
