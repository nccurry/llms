---
name: dependency-auditor
description: Audit project dependencies for security vulnerabilities, outdated packages, license concerns, and maintenance health. Use when checking CVEs, updating packages, reviewing license requirements, assessing dependency risk, or reducing dependency bloat.
---

# Dependency Auditor

Audit dependencies with the package manager, lock files, CI, and manifests already present in the project. Do not update packages unless the user explicitly asks for implementation.

## Workflow

1. Identify the audit scope: whole repo, package, manifest, lockfile, dependency group, CVE, license question, or update request.
2. Read local instructions and dependency policy first, such as `AGENTS.md`, README, CI config, security policy, package manager config, and lockfiles.
3. Detect ecosystems from manifests and lockfiles.
4. Use repository-native package-manager commands where available for audit, outdated, tree, why, license, and lockfile checks.
5. Use current authoritative advisory, registry, or project-maintainer sources when package-manager output is missing, stale, or ambiguous. Include source names and dates for CVE or advisory claims.
6. Separate direct dependencies from transitive dependencies and runtime dependencies from dev/test/build-only dependencies.
7. Report immediate actions and planned follow-ups. Prefer conservative, compatibility-aware recommendations.

## Detect Ecosystem

Check for:

- `package.json`, lockfiles, and workspace config: npm, yarn, pnpm, or bun.
- `requirements.txt`, `pyproject.toml`, `poetry.lock`, or `uv.lock`: Python.
- `go.mod` and `go.sum`: Go modules.
- `Cargo.toml` and `Cargo.lock`: Rust.
- `pom.xml`, `build.gradle`, or Gradle lockfiles: Java or Kotlin.
- `Gemfile` and `Gemfile.lock`: Ruby.
- `*.csproj`, `packages.lock.json`, or `Directory.Packages.props`: .NET.

## Audit Dimensions

Security:

- Identify known CVEs, GHSA advisories, OSV records, or ecosystem advisories.
- Report severity, installed version, fixed version, reachability if known, and recommendation.
- Prioritize critical and high findings, especially runtime and internet-facing dependencies.

Updates:

- Categorize patch, minor, and major updates.
- Review changelogs, release notes, migration guides, and peer dependency constraints before recommending major updates.
- Prefer lockfile-preserving or narrow update commands unless the user asks for broader modernization.

Licenses:

- Flag unknown, proprietary, strong copyleft, or project-incompatible licenses.
- Note attribution, source disclosure, redistribution, or commercial-use obligations when relevant.

Health:

- Check maintenance activity, release cadence, deprecation notices, issue volume, maintainer handoff, package size, and heavy transitive dependencies.
- Recommend replacement only when the current dependency is materially risky or already obsolete.

## Routing Boundaries

- Use this skill for dependency security, update, license, maintenance, and bloat questions.
- Use `dead-code-audit` when the main question is whether a dependency is unused.
- Use `code-quality-audit` when dependency usage is acceptable but local code around it is hard to maintain.

## Output Contract

Lead with findings ordered by severity and actionability:

- `P1`: Critical/high security issue, incompatible license, abandoned runtime dependency, or update needed to prevent real risk.
- `P2`: Important outdated direct dependency, moderate advisory, notable license ambiguity, or maintenance concern.
- `P3`: Low-risk update, transitive cleanup, duplicate dependency, or bloat reduction.

Each finding must include package name, installed version, affected range or current state, fixed or recommended version when known, evidence source, and a concrete action.

If no meaningful dependency issues are found, say so clearly, name the manifests and package manager evidence inspected, and mention any blind spots. Report commands run and whether tests were run or still need to be run after dependency changes.
