# <Feature> Architecture And Design

## Design Goal

State the chosen design and its main tradeoff.

## Context And Boundaries

Name the affected components. State what each owns and what remains outside its
responsibility. Link to the public contracts in `SRD.md` or their existing source.

## Decisions And Alternatives

| Decision or option | Status | Reason |
| --- | --- | --- |
| <decision or alternative> | <proposed, accepted, rejected, or deferred> | <tradeoff and authority when approval is needed> |

## Fixed Constraints And Implementation Choices

Name the public contracts, safety rules, and ownership boundaries that must
hold. Leave routine internal choices open unless a concrete constraint requires
them. Distinguish a suggested implementation from a required design decision.

## Building Blocks

| Component | Responsibility | Changed behavior |
| --- | --- | --- |
| <component> | <responsibility> | <change> |

## Runtime And Data Flow

Describe the main path from input to result. Include failure, retry, restart,
or recovery paths when they change behavior. Explain internal data and state
ownership without repeating public contract definitions or experience examples.

## Quality And Safety

Describe the design choices for the quality attributes in `SRD.md`. Include
trust boundaries, concurrency, cancellation, recovery, and resource limits
when they apply.

## Test Design

Explain which unit, integration, end-to-end, visual, or manual checks prove the
design. Use existing test facilities where they suffice. Put commands, expected
results, and actual evidence in `IMPLEMENTATION_PLAN.md`.

## Deferred Work

| Item | Reason | Follow-up owner or trigger |
| --- | --- | --- |
| <item or none> | <reason> | <owner or when to revisit> |

Required acceptance cannot be moved here merely to declare completion.
