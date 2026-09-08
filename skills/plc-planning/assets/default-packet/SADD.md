# <Feature> Architecture And Design

## Design Goal

State the chosen design and its main tradeoff.

## Context And Boundaries

Name the affected components. State what each owns and what remains outside its
responsibility.

## Alternatives

| Option | Decision | Reason |
| --- | --- | --- |
| <option> | <chosen or rejected> | <reason> |

## Building Blocks

| Component | Responsibility | Changed behavior |
| --- | --- | --- |
| <component> | <responsibility> | <change> |

## Runtime And Data Flow

Describe the main path from input to result. Include failure, retry, restart,
or recovery paths when they change behavior.

## Interfaces And Data

Define changed APIs, commands, schemas, records, files, configuration, and
invalid-input behavior. Explain how the design supports the public summary and
expected-experience examples in `SRD.md`. Do not repeat those examples here.

## Quality And Safety

Describe the design choices for the quality attributes in `SRD.md`. Include
trust boundaries, concurrency, cancellation, recovery, and resource limits
when they apply.

## Test Design

Map unit, integration, end-to-end, visual, or manual checks to the design.

## Deferred Work

| Item | Reason | Follow-up trigger |
| --- | --- | --- |
| <item or none> | <reason> | <when to revisit> |
