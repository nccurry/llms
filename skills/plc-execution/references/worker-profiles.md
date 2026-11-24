# Assignment and review by model

Apply the profile named by the selected wrapper to the shared
[child assignment](child-assignment.md) and [parent review](parent-review.md).
The PLC defines scope, evidence, and the delivery endpoint.

## Bounded workers

For Luna and Haiku, give one bounded behavior change or a set of closely
related edits. Include the relevant source entry points, owned paths, and
checks that will prove the result. Give the worker enough context to follow
usage across file boundaries. For a coupled block, settle the interface or
implementation decision before dispatch and keep the block with one owner.

For review, compare the handoff with every assigned acceptance check, including
behavior the diff may have omitted. For a repair, identify the concrete
finding and the check or observation that will verify the fix. Follow the
wrapper's model and escalation rules.

## Terra

Give Terra a focused change and the relevant behavior checks. When output is
visual, include the design or current rendering, the target surfaces, and any
relevant viewports or states. Ask for representative before-and-after rendered
evidence where useful. Review the rendered result and its underlying behavior.

## Coherent phases

For Sol, Sonnet, and Opus, assign a coherent phase or block with clear interface
ownership, consumers, and failure paths. Give the worker room to choose the
implementation within the agreed constraints. Review changes to contracts and
assumptions against connected code and verify the affected integration paths.

## Astra and Fable managers

Spend manager effort on architecture decisions, cross-repository contracts,
and difficult acceptance calls. Give workers concrete assignments after
settling decisions they depend on. Use handoffs and specific findings to steer
implementation and keep routine choices with the owner.
