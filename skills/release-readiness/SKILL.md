---
name: release-readiness
description: Prepare or audit a repository for release. Use before tagging, publishing, merging a release branch, drafting release notes, checking changelog quality, identifying breaking changes, verifying docs/tests/security status, or deciding whether a version is ready to ship.
---

# Release Readiness

Use this skill to turn a repo diff into a release-ready decision, changelog, and follow-up checklist.

## Workflow

1. Identify the release scope: version, branch, tag range, package, app, service, or deployment target. If not provided, infer from the latest tag, release branch, package manifest, or user request and state the assumption.
2. Read release policy first: `AGENTS.md`, changelog policy, versioning docs, CI config, package manifests, deployment docs, migration docs, and security policy.
3. Gather evidence from git history, changed files, PR metadata when available, issue references, package manifests, docs changes, and CI/test status.
4. Classify notable changes into human-facing groups: added, changed, fixed, deprecated, removed, security, docs, internal, and breaking changes.
5. Identify release blockers: failing validation, missing migration notes, stale docs, unreviewed breaking changes, security issues, dependency risk, missing artifacts, or incomplete version bumps.
6. Draft release notes for humans. Synthesize related commits instead of dumping commit messages.
7. If the user asked to finalize, run the repo's release validation commands and update release artifacts according to local policy.

## Release Criteria

Check:

- Versioning matches project policy and semantic impact.
- Changelog or release notes are dated, grouped, concise, and latest-first.
- Breaking changes are explicit and include migration guidance.
- User-visible changes are separated from internal maintenance.
- Docs, examples, install instructions, screenshots, generated docs, and API references reflect the release.
- Tests, build, lint, typecheck, package, and deploy dry-runs are green or clearly blocked.
- Security and dependency findings have been triaged.
- Release artifacts, checksums, packages, container tags, or deployment manifests are present when required.

## Routing Boundaries

- Use `docs-sync` for documentation updates outside a release decision.
- Use `dependency-auditor` for deep dependency risk analysis.
- Use `pre-merge` or `verify` for general branch readiness when release notes and versioning are not in scope.

## Output Contract

Lead with one of: `Ready`, `Ready with caveats`, or `Blocked`.

Include:

- Release scope and evidence inspected.
- Blockers and required fixes, ordered by severity.
- Draft release notes or changelog entries when requested or useful.
- Versioning recommendation when inferable.
- Validation commands run and results.
- Follow-up checklist for anything not completed.

If information is missing, name the exact missing evidence instead of guessing.
