# Writing readable plans

Keep the fixed fields in [the shared format](shared-format.md) exact. Around
them, choose the Markdown form that helps a reader find and understand the
information. Small plans should stay small. Delete sections that do not apply.

| Information | Useful form |
| --- | --- |
| Purpose, scope, explanation or tradeoff | Short connected paragraphs |
| A distinct topic | A descriptive heading |
| Comparable options or repeated short records | A table |
| Actions that must happen in order | A numbered list |
| Independently tracked tasks | Checkboxes |
| Short parallel items | Bullets |
| Commands, configuration or request/response examples | Fenced blocks |
| A relationship or flow that is difficult to explain in prose | A small diagram |

These are choices, not quotas. Do not add a table or diagram just to use one.
Split a table cell that becomes a multi-topic narrative into a section instead.
Respect repository lint rules: when repeated subheadings are disallowed, choose
names such as Parser checks and Browser checks rather than disabling the rule.

## Phase details

Keep `### P<n>: <name>` as the phase boundary. Use deeper headings for scope,
prerequisites, steps, validation, evidence and rollback when they hold useful
information. A scope paragraph and numbered steps may be enough. Keep phase
state in the README table, not in a second status block here.

Write only work-specific instructions. Generic execution, audit and cleanup
policy belongs in the skills that own it; include a packet-specific constraint
or exception when the next person needs it. Do not copy template instructions,
empty headings or placeholder text into a generated plan.

## Evidence that stays readable

Use a table for short comparable results and headed records for longer context.
Each record retains the requirement/check, date, tested source, method, expected
and actual result, relevant environment/dependencies and limits. A table may
link to a shared method or environment immediately above it. Preserve exact
source revisions and the distinction between supplied results and checks run
by the current agent. Unrun required checks remain pending.

Count records, not Markdown bullets, when applying the existing more-than-three
evidence-record trigger for an implementation plan. One result split across
several paragraphs remains one record. A heading or table does not hide how
many results the packet holds.

When updating a plan, keep information in its owning section. Replace current
instructions in place; history belongs in the Log. Split growing explanations
into descriptive subsections while retaining prior results, rationale and
limitations. Reformatting must not change requirements, IDs, state or evidence
meaning. Before closing a change, reconcile delivered behavior and accepted
design into the repository's existing maintained product docs.

## Visual aids

A diagram is encouraged where it explains faster than prose, and never
required. A small one-file plan usually needs none, and a plan never gets a
diagram just to fill it out.

- **Which kind.** A plain-text tree in a `text` code block for files and
  folders. Otherwise a Mermaid diagram in a `mermaid` code block:
  - components and their boundaries: a flowchart of boxes, with a
    `subgraph` for each boundary;
  - a flow across parts, such as a request through two services: a
    sequence diagram;
  - stored data: an ER diagram;
  - types and how they relate: a class diagram;
  - a lifecycle, such as the states of an order: a state diagram;
  - hosts and services: a deployment diagram drawn as a flowchart, with a
    `subgraph` for each host;
  - decision logic: a flowchart.
- **Where it lives.** With the design it explains, which is mostly SADD.md.
  A UI or CLI sketch goes in a `text` code block in SRD.md's Expected
  Experience. The README holds at most one overview diagram. In a one-file plan, a diagram sits in the
  section it explains.
- Keep each diagram small and use the plan's own names. The
  [SADD template](../assets/default-packet/SADD.md) shows examples in HTML
  comments.
