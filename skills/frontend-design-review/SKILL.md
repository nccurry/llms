---
name: frontend-design-review
description: Review rendered frontend UI for design quality, UX flow, accessibility, responsive behavior, visual polish, design-system compliance, and Figma fidelity. Use for UI PR reviews, design reviews, component reviews, visual QA, accessibility checks, and product interface critique.
---

# Frontend Design Review

Use this skill to evaluate existing frontend work. Focus on what users see and do, then connect findings to code or design-system evidence.

## Workflow

1. Identify the review target: PR, branch diff, route, component, screenshot, Figma link, deployed URL, or local app.
2. Read local design and product guidance first: `AGENTS.md`, design-system docs, Storybook, token files, accessibility rules, existing screens, and Figma references if provided.
3. Inspect the implementation in context. Prefer rendered browser review and screenshots over source-only judgment when a runnable app is available.
4. Review the core user task: entry point, information hierarchy, primary action, feedback, exit/cancel path, and error recovery.
5. Check design-system compliance: components, variants, tokens, spacing, typography, colors, theming, and documented exceptions.
6. Check craft: responsive layout, state coverage, copy, motion, density, contrast, keyboard navigation, focus, and visible affordances.
7. Compare against Figma or screenshots when available. Note exact mismatches and whether they are acceptable design-system substitutions.
8. Report findings first, ordered by user impact.

## Review Criteria

Evaluate:

- Frictionless use: the main task is obvious, efficient, and not split across unnecessary steps.
- Visual hierarchy: headings, grouping, spacing, density, and action prominence guide the eye.
- Design system fit: existing components and tokens are used consistently.
- Fidelity: implementation matches approved Figma specs or has documented deviations.
- Accessibility: keyboard operation, focus visibility, labels, contrast, reduced motion, target size, zoom, and screen-reader semantics.
- Responsiveness: mobile, tablet, desktop, long text, empty data, and high-density data remain usable.
- Trust: loading, empty, error, destructive, confirmation, and AI-generated-content states are clear and actionable.
- Polish: no overlaps, clipping, jitter, broken alignment, awkward wrapping, or generic visual filler.

## Routing Boundaries

- Use `frontend-design` when creating or redesigning UI.
- Use `figma-implement-design` when implementing from a Figma source.
- Use `visual-code-audit` when reviewing source-code presentation rather than rendered UI.

## Output Contract

Lead with findings ordered by severity:

- `P1`: Blocks task completion, breaks accessibility, violates a critical design-system contract, or creates serious user confusion.
- `P2`: Significant UX, responsive, fidelity, or polish issue that should be fixed before shipping.
- `P3`: Smaller visual, copy, state, or consistency improvement.

Each finding must include the affected screen/component, evidence inspected, why it matters to the user, and a concrete fix direction. Include screenshots, routes, or file references when available.

If no meaningful issues are found, say so clearly and state what was inspected, which viewports or states were checked, and what remains unverified.
