---
name: frontend-design
description: Design and implement distinctive, production-grade frontend UI. Use when creating or substantially reshaping an app screen, page, component, dashboard, landing page, or interactive experience where visual direction, UX flow, copy, responsiveness, accessibility, and polish matter.
---

# Frontend Design

Use this skill when the deliverable is new or substantially redesigned frontend UI. Create an interface with a clear product point of view, not a generic template.

## Workflow

1. Identify the product, audience, main user task, constraints, and success criteria from the prompt and repository context.
2. Read local design guidance first: `AGENTS.md`, design-system docs, Storybook, component directories, design tokens, theme files, existing pages, and brand assets.
3. Choose a compact design direction before coding:
   - Purpose: the single job this screen must do.
   - Tone: the visual and interaction personality that fits the product.
   - Palette: 4-6 named tokens or CSS variables.
   - Type: display, body, and utility roles using project-approved fonts when available.
   - Layout: information hierarchy and responsive structure.
   - Signature: one memorable design move tied to the product's subject matter.
4. Check the plan against the common generic defaults: centered hero, vague cards, ornamental gradients, one-note palettes, empty marketing copy, and arbitrary animation.
5. Implement using the project's framework, routing, state, components, tokens, and data patterns.
6. Make the first viewport useful. For apps and tools, show the working experience first instead of a marketing splash unless the user explicitly asked for a landing page.
7. Add complete states: loading, empty, error, disabled, hover, focus, selected, success, destructive, and mobile states where relevant.
8. Validate with screenshots or browser inspection when practical, including desktop and mobile widths.

## Design Criteria

Check whether the interface:

- Has one clear primary task and action hierarchy.
- Uses project components and tokens before inventing new ones.
- Feels specific to the domain through layout, copy, typography, imagery, data, or interaction.
- Uses restraint: one signature visual idea, disciplined supporting elements.
- Treats copy as interface material: direct verbs, sentence case, no filler, consistent action names.
- Supports keyboard navigation, visible focus, sufficient contrast, responsive layout, and reduced-motion preferences.
- Avoids decorative UI cards, nested cards, arbitrary blobs, generic gradients, and hero-scale type inside compact controls.
- Keeps text from overlapping or overflowing at realistic mobile and desktop sizes.

## Routing Boundaries

- Use `figma-implement-design` when Figma is the source of truth.
- Use `frontend-design-review` when evaluating an existing UI rather than creating or reshaping it.
- Use `visual-code-audit` when the request is about source-code readability instead of rendered interface quality.

## Output Contract

For implementation work, summarize the design direction, meaningful UI changes, and validation performed. If validation could not be run, say what remains to inspect.

For design-only requests, provide a concise design brief with purpose, tone, palette, typography roles, layout, signature element, key states, and acceptance criteria.
