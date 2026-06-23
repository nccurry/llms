---
name: docs-sync
description: Check and update documentation after code, API, CLI, configuration, behavior, or UI changes. Use when docs may be stale, when preparing a PR, when public behavior changes, or when the user asks to sync README, guides, examples, screenshots, changelogs, or generated docs with implementation.
---

# Docs Sync

Use this skill to keep documentation aligned with actual behavior. Start from repository truth, then update only docs that should change.

## Workflow

1. Identify the change scope from the user request, branch diff, PR, commits, or changed files.
2. Read local documentation rules first: `AGENTS.md`, README, docs contributor guides, docs build config, API docs tooling, changelog policy, and release process.
3. Classify documentation impact:
   - Public API, CLI, config, environment variables, schemas, routes, errors, permissions, or workflows changed.
   - User-visible UI, screenshots, examples, install/setup steps, troubleshooting, or migration behavior changed.
   - Internal-only implementation changed with no docs impact.
4. Find docs that mention changed names, commands, flags, endpoints, screens, config keys, examples, or old behavior. Use structured docs tooling when available, then `rg`.
5. Compare docs against implementation, tests, generated help, schemas, screenshots, or examples.
6. Update docs with the smallest accurate change. Prefer precise, task-oriented wording over broad rewrites.
7. Run docs validation when available: docs build, link checker, snippet tests, generated API docs, screenshot update command, or markdown lint.

## Writing Criteria

Documentation should:

- Say what users can do, what changed, and what to run or click next.
- Keep commands, flags, paths, examples, config keys, and screenshots accurate.
- Use consistent names for the same action across UI, code, docs, and release notes.
- Separate stable instructions from temporary implementation notes.
- Include migration notes for breaking or behavior-changing updates.
- Avoid documenting internals unless the reader needs them.
- Avoid stale promises such as "coming soon", old limitations, or outdated screenshots.

## Routing Boundaries

- Use `release-readiness` when preparing a versioned release, tag, or public changelog.
- Use `frontend-design-review` when the main concern is whether screenshots or UI are visually correct.
- Use `code-quality-audit` when docs drift reveals unclear or unstable implementation behavior.

## Output Contract

For audits, lead with documentation gaps ordered by user impact and include the changed behavior, affected docs, evidence, and exact update needed.

For edits, summarize which docs were updated, what behavior they now reflect, validation run, and docs still needing owner review or screenshots.

If no docs updates are needed, say so clearly and name the code paths, docs, and searches inspected.
