---
name: file-hygiene-audit
description: Audit a repository for verified temporary, stray, or obsolete files and safely clean them up without disturbing intentional documentation, source, or build assets.
---

# File Hygiene Audit

Find temporary or misplaced repository files. This does not clean caches or prove dead code.

## Rules

1. Read repository instructions, docs/history, and the relevant directory first. Explicit policy wins. Keep plans or docs only in a documented or clearly established location; a `docs`-like name alone is not enough. Without a planning policy, only clearly temporary agent plans are candidates.
2. Retain staged or modified work, normal docs, configuration, manifests, source, tests, assets, files outside the root, symlinks, secrets, Git data, and dependency, cache, build, or generated directories.
3. Move a planning file only to an explicitly named destination. Verify it exists, accepts the file, is writable, and has no conflict. Do not guess, overwrite, or transfer across hosts. A tracked source also needs an explicit rule.
4. Trash only with explicit cleanup authority, not an audit, report, or "fix findings" request, and two independent signals, one proving it is disposable. Signals include an untracked agent artifact outside a retained location, clearly temporary or debug content, no relevant reference after checking configuration, or a rule that rejects the file type. Age, filename, untracked state, or missing text references alone do not count.
5. Before cleanup, resolve the exact path, confirm it is inside the intended repository, recheck Git state, and skip symlinks. Never use wildcards or recursive targets.
6. Use the owning host's trash or recycle bin. Never permanently delete, empty trash, or fall back to `rm`, `Remove-Item`, `git clean`, `shutil.rmtree`, or equivalent. If safe trash is unavailable, leave the file and report it.
7. Report every candidate's path, evidence, and outcome: retained, relocated, trashed, or ambiguous/blocked. List every trashed file so the user can restore it.

Use `dead-code-audit` for unused code, `docs-sync` for maintained docs, and `clean-stale-worktrees` for branches or worktrees. Use P2 only for material safety, execution, or misleading-documentation risk; use P3 for ordinary cleanup. When invoked by `audit-codebase`, return findings, policy evidence, cleanup actions, and validation evidence without choosing the aggregate verdict.
