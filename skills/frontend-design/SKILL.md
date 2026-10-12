---
name: frontend-design
description: "Design and implement new or substantially redesigned component-based UI for web or native apps. Use for screens, pages, and components needing visual and interaction design."
---

# Frontend Design

Create an interface with a clear purpose using the project's component and
layout system. Discover framework APIs and project facts in source and local
docs rather than imposing a web framework or a particular native toolkit.

## Workflow

1. Identify audience, main task, constraints, and success criteria from the
   request and repository.
2. Read local agent/design guidance, component examples or catalogs, tokens,
   themes, existing screens, and assets.
3. Choose hierarchy, tone, typography roles, layout, and relevant states before
   coding. Reuse approved components, variants, and palette; add new design
   elements only when they serve this product.
4. Implement with the existing component, routing, state, data, and lifecycle
   patterns. Define who owns layout, input, and state instead of duplicating
   responsibilities across parent and child components.
5. Make the initial view useful for the main task. Use direct copy, consistent
   action names, and loading/empty/error/disabled/selected/focus states as needed.
6. Inspect rendered output using the app's supported browser, preview, screenshot,
   or native host. Check relevant narrow/wide sizes, long text, and content scale.

## Component and flexbox layout

Use the framework's existing layout primitives and documented flexbox semantics.
Do not assume CSS names or browser defaults in a native component system.

- Let the parent own flow, spacing, alignment, and available size; let reusable
  components express intrinsic content and meaningful constraints.
- Select row/column direction, gap, wrapping, alignment, and justification for
  the actual information hierarchy. Avoid manual positions for ordinary flow.
- Define grow, shrink, basis/intrinsic size, and min/max constraints deliberately.
  Check default minimum sizes when flexible text or panels refuse to shrink.
- Give scrolling and overflow to a clear owner. Check nested layouts have the
  bounds they need; do not hide overflow to conceal an unreachable action.
- Reuse component variants and tokens. Avoid copying a screen-specific layout
  into a shared component or inventing wrappers for every spacing adjustment.
- Check resizing, localization/long labels, empty/dense data, text scaling, and
  dynamic content. Fixed sizes need a real platform/product reason.

## Design and acceptance

Support the platform's input conventions, keyboard navigation, visible focus,
labels, contrast, and relevant accessibility/reduced-motion behavior. Keep the
main action clear and controls usable at realistic sizes. Use purposeful visual
hierarchy instead of decorative cards, arbitrary gradients, or marketing filler
inside an application.

Use `figma-implement-design` when Figma is the source of truth,
`frontend-design-review` for existing rendered UI, and `visual-code-audit` for
source formatting.

For implementation, show representative component/layout examples, meaningful
behavior, and the rendered states/sizes checked. Name validation gaps.
For design-only work, provide the proposed hierarchy, component reuse, layout
behavior, states, and acceptance criteria.
