# <Feature> Requirements

## Purpose

<!-- State the user, developer, or business problem and the required outcome. -->

## Scope

- In scope: <list>
- Out of scope: <list>
- Constraints: <compatibility, security, platform, or dependency limits>

## Current System And Prerequisites

<!-- Record the source revision inspected and link to relevant code, tests, and
existing contracts. Distinguish observed behavior from proposed changes.
For each prerequisite, name the required capability, its owner, how to check
that it is available, and the requirements it blocks. A planned or approved
sibling document alone does not prove its implementation is available.
For a moving upstream target, record the revision and date checked; do not
silently turn that snapshot into a fixed product target. -->

## Requirements

<!-- Use one observable behavior or constraint per requirement. Each names a check
that can be run: a command or test, and its expected result. EARS wording
("WHEN … the system SHALL …") is optional. -->

<!-- IDs are permanent: never renumber, reuse or rename them. A dropped requirement
stays where it is, marked `Dropped — <reason>`, and a new one takes the next
number. -->

| ID | Priority | Requirement | Check |
| --- | --- | --- | --- |
| REQ-001 | Must | <observable behavior or constraint> | `<command or test>` → <expected result> |

## User Experience And Public Surface

<!-- Summarize behavior a user, API consumer, operator, or integrator can observe.
When this change has no public surface, delete this section and Expected
Experience. -->

| Surface | Action or input | Expected result | Compatibility |
| --- | --- | --- | --- |
| <CLI, API, configuration, UI, or other surface> | <action or input> | <visible result> | <new, changed, unchanged, or migration> |

## Expected Experience

<!-- Add short examples for each changed public surface. Include error, empty, or
permission behavior when it matters. Use only the headings that apply. -->

### CLI

```text
$ <command>
<expected output>
```

### API

```http
<request>

<response>
```

### Configuration

```text
<key>=<value>
```

### UI Flow

1. <user action>
2. <visible result>
3. <error or empty-state behavior, when relevant>

## Public Contracts

<!-- Define changed APIs, commands, configuration, schemas, files, and observable
state transitions, including invalid-input behavior. Link to an existing
schema or contract when it already defines these details; do not maintain a
second definition. Internal implementation choices belong in `SADD.md`. -->

## Quality Attributes

| Attribute | Scenario | Pass/fail measure |
| --- | --- | --- |
| <performance, reliability, security, usability, or maintainability> | <workload and conditions> | <measure> |

## Traceability

<!-- Phase state lives in the README `## Phases` table; phase details and evidence
live in `IMPLEMENTATION_PLAN.md`. -->

| Requirement | Design section | Phase |
| --- | --- | --- |
| REQ-001 | <SADD section> | <phase ID> |

## Risks And Assumptions

<!-- Open questions go in the README's `## Open questions` section, one
`Open question:` line each. Record adopted decisions in `SADD.md` and remove
superseded instructions from current sections. -->

| Item | Type | Affected requirements or phases | Blocks work? | Owner | Resolution or permitted assumption |
| --- | --- | --- | --- | --- | --- |
| <item> | <risk or assumption> | <IDs> | <yes: name blocked work, or no> | <owner> | <check, decision needed, or safe temporary assumption and its limits> |
