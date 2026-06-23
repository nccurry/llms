---
name: figma-implement-design
description: Implement production UI code from a Figma design with visual fidelity. Use when the user provides a Figma URL, selected Figma node, design frame, component spec, or asks to translate Figma designs into repository code while preserving layout, tokens, assets, states, and accessibility.
---

# Figma Implement Design

Use this skill when Figma is the source of truth and the deliverable is code in the user's repository.

## Preconditions

- Prefer a Figma URL with file key and node id, or an explicitly selected node in a connected Figma desktop MCP session.
- If no Figma access or screenshot is available, ask for a Figma link, exported screenshot, or exact design spec before implementing visual details.
- If the user wants to edit the Figma file itself, use a Figma-authoring workflow instead of this skill.

## Workflow

1. Parse the Figma URL or selected node. Extract the file key and node id when present.
2. Fetch structured design context from the Figma MCP server when available. If the response is large, fetch metadata first, then fetch the specific child nodes needed.
3. Capture a screenshot or exported visual reference for the same node. Treat it as the visual source of truth.
4. Collect assets from the Figma payload or export. Use provided asset URLs or files directly; do not substitute placeholder icons or new icon packages when real assets are available.
5. Inspect the repository's design system, existing components, token files, theme variables, layout primitives, and Storybook/examples before writing UI.
6. Map Figma styles to project conventions:
   - Components: reuse or extend existing components first.
   - Tokens: map colors, type, spacing, radii, shadows, and breakpoints to existing tokens when close.
   - Layout: preserve Figma constraints, auto-layout intent, hierarchy, and responsive behavior.
   - Assets: preserve names and purpose without hardcoding local machine paths.
7. Implement incrementally, matching the design while keeping code idiomatic for the project.
8. Validate against the visual reference with browser screenshots or rendered inspection at the relevant breakpoints.

## Fidelity Rules

- Prefer visual parity for spacing, alignment, typography, colors, states, and asset placement.
- Prefer the project's design system when a token/component mismatch is minor; document meaningful deviations.
- Do not blindly paste generated Figma code if it conflicts with the repository's framework, architecture, accessibility, or component conventions.
- Implement all visible variants and states represented by the frame or component.
- Preserve accessibility: semantic elements, labels, focus order, contrast, reduced motion, and keyboard operation.

## Routing Boundaries

- Use `frontend-design` for original UI design without Figma as source of truth.
- Use `frontend-design-review` to critique an implementation against Figma or a design system.
- Use `docs-sync` if the design implementation changes documented behavior or screenshots.

## Output Contract

Report the Figma source, component/token mappings used, assets added or reused, deviations from the design, and validation performed. If exact parity is not possible, state why and what remains to compare.
