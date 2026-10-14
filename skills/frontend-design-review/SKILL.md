---
name: frontend-design-review
description: "Review rendered component-based UI for usability, accessibility, resizing, and design fidelity in web or native apps. Use for UI critique or visual QA, not source-code formatting."
---

# Frontend Design Review

Review what users see and do, then connect findings to component/layout code
and project standards. Discover the framework's actual behavior in source and
docs; do not assume a particular toolkit or browser-only implementation.

## Workflow

1. Establish the target: diff, route, screen/component, screenshot, design
   reference, deployed app, or local host.
2. Read relevant agent, product, design, token, component, and accessibility
   guidance. Inspect the implementation with connected layout and state owners.
3. Prefer rendered review through the available browser or native host.
   A screenshot proves only the shown state; source-only inspection cannot
   establish usable rendering, focus order, or runtime interactions.
4. Exercise the main task, feedback, cancellation, and failure recovery.
   Compare supplied design references and existing component conventions.
5. Check relevant viewport/window sizes, long content, empty/dense data, text
   scale, input modes, and state transitions.
6. Report evidenced findings in user-impact order.

## Review criteria

- Main task/action hierarchy, direct copy, and useful loading/error/empty states.
- Existing components, variants, tokens, typography, spacing, and themes used
  consistently; approved designs preserved or deviations explained.
- Parent/child layout ownership and reusable component boundaries remain clear.
- Flex direction, gap, wrapping, grow/shrink, basis, min/max sizes, alignment,
  and justification produce the intended hierarchy.
- Text and flexible panels can shrink appropriately; fixed constraints do not
  clip content or hide actions. Scroll/overflow has one clear owner and bounds.
- Resizing, long/localized labels, content scaling, and dynamic data avoid
  overlap, clipping, jitter, awkward wrapping, and inaccessible controls.
- Platform input conventions, keyboard operation, focus, labels, contrast,
  semantics, target sizes, and reduced motion are usable where supported.

Validate flex properties against the actual layout engine. Browser defaults
and CSS spellings are not evidence for native component behavior.

For visual regressions, use the capture catalog's reference paths and check
which platform/backend and state each image proves. Compare their update history
when a new default differs from old references. Review intended changes against
the authorized design before regeneration; cross-platform similarity or matching
before/after images alone does not establish acceptance. Keep unverified affected
variants explicit rather than treating a reference refresh on one as universal.

## Routing and report

Use `frontend-design` for new/redesigned UI, `figma-implement-design` for
implementation from Figma, and `visual-code-audit` for source presentation.

Report each finding with screen/component, inspected evidence, user impact, and
concrete correction. Use P1 for blocked tasks or critical accessibility/design
contracts, P2 for significant usability/layout defects, and P3 for smaller
evidenced inconsistencies. Include routes, source, and screenshots when useful.

If no issue is found, state exactly which sizes, states, and interactions were
checked and what remains unverified. When delegated by `audit-codebase`, return
read-only findings/evidence; the parent owns the aggregate verdict and fixes.
