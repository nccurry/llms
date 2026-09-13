---
name: design-for-change
description: "Plan, design, and implement changes with clear responsibilities, adaptable boundaries, and straightforward tests. Use before and during new work; not for retrospective audits."
---

# Design for Change

Use during planning and implementation. Build the smallest solution that stays clear and easy to change.

- Give each unit a clear job; group related behavior.
- Favor loose coupling: add boundaries only for real variation or external dependencies. Keep core rules separate from UI, frameworks, storage, and transport when useful.
- Keep abstractions non-leaky: APIs should not expose implementation or infrastructure details. Keep effects at the edges for testability.
- Prefer direct local code over speculative layers, interfaces, or configuration.
- Organize around ownership and the main flow; preserve the user's scope and conventions.

Before finishing: Is the main flow obvious? Can a likely change stay local? Can key behavior be tested without infrastructure?

This guides new work; it is not a retrospective audit or rewrite.
