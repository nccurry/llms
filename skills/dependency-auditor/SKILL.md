---
name: dependency-auditor
description: Audit project dependencies for security advisories, outdated packages, incompatible licenses, maintenance risk, and dependency bloat. Use when reviewing manifests, lockfiles, package updates, CVEs, licenses, or supply-chain health. This audit is separate from the routine code craftsmanship gate.
---

# Dependency Auditor

Do not update packages unless the user authorizes implementation.

## Workflow

1. Identify the repository, package, manifest, lockfile, dependency group, advisory, license question, or update scope.
2. Read local instructions, dependency policy, CI files, package-manager configuration, and lockfiles.
3. Detect each package ecosystem from its manifests and lockfiles.
4. Use repository package-manager commands for audit, outdated, tree, why, license, and lockfile checks.
5. Use current authoritative sources when local output is missing, stale, or ambiguous.
6. Separate direct from transitive dependencies.
7. Separate runtime dependencies from development, test, and build dependencies.
8. Report immediate actions and compatibility-aware follow-ups.

## Audit Dimensions

Security:

- Report the advisory, severity, installed version, affected range, fixed version, and reachability when known.
- Prioritize critical and high findings in runtime and exposed paths.

Updates:

- Separate patch, minor, and major updates.
- Read release notes, migration guidance, and peer constraints before recommending a major update.
- Prefer narrow, lockfile-aware update commands.

Licenses:

- Flag unknown, proprietary, strong-copyleft, or project-incompatible licenses.
- State relevant attribution, disclosure, redistribution, and commercial-use obligations.

Health:

- Examine maintenance activity, deprecation notices, release cadence, maintainer changes, package size, and transitive weight.
- Recommend a replacement only when the current dependency has material risk or clear obsolescence.

## Routing Boundaries

- Use this skill for dependency security, versions, licenses, maintenance, and bloat.
- Do not include it in `audit-codebase` unless the user explicitly requests dependency review.
- Use `dead-code-audit` when the main question is whether a dependency is unused.
- Use `performance-audit` when a dependency causes measured runtime or resource cost.
- Use an application-security specialist for local trust boundaries, authorization, injection, secrets, and cryptography.

## Output Contract

Lead with findings in impact order:

- `P1`: A critical advisory, incompatible license, or abandoned runtime dependency creates material risk.
- `P2`: An outdated direct dependency, moderate advisory, or maintenance concern needs planned action.
- `P3`: A low-risk update, duplicate package, transitive cleanup, or bloat concern has concrete value.

For each finding, include the package, installed version, affected state, recommended version, evidence source, date, and concrete action.

If no actionable findings exist, say so. Name the manifests, commands, sources, and blind spots.
