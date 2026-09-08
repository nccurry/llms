# <Feature> Requirements

## Purpose

State the user, developer, or business problem and the required outcome.

## Scope

- In scope: <list>
- Out of scope: <list>
- Constraints: <compatibility, security, platform, or dependency limits>

## Current System

Name the current code, behavior, interfaces, data, and tests affected by this
work.

## Requirements

Use one observable behavior or constraint per requirement.

| ID | Priority | Requirement | Acceptance criteria |
| --- | --- | --- | --- |
| REQ-001 | Must | <observable behavior or constraint> | <objective evidence> |

## User Experience And Public Surface

Summarize behavior a user, API consumer, operator, or integrator can observe.
Write `None` when this change has no public surface.

| Surface | Action or input | Expected result | Compatibility |
| --- | --- | --- | --- |
| <CLI, API, configuration, UI, or other surface> | <action or input> | <visible result> | <new, changed, unchanged, or migration> |

## Expected Experience

Add short examples for each changed public surface. Include error, empty, or
permission behavior when it matters. Use only the headings that apply.

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

## Interfaces And Data

Define the exact changed APIs, commands, configuration, schemas, files, and
state transitions behind the public summary. State invalid-input behavior.

## Quality Attributes

| Attribute | Scenario | Pass/fail measure |
| --- | --- | --- |
| <performance, reliability, security, usability, or maintainability> | <when it matters> | <measure> |

## Phased Delivery

| Phase | Goal | Requirements | Exit criterion |
| --- | --- | --- | --- |
| 1 | <smallest useful result> | REQ-001 | <validation result> |

## Traceability

| Requirement | Design section | Validation method | Evidence |
| --- | --- | --- | --- |
| REQ-001 | <SADD section> | <test, command, review, or inspection> | <link or result> |

## Risks, Assumptions, And Open Questions

| Item | Type | Impact | Owner | Resolution plan |
| --- | --- | --- | --- | --- |
| <item> | <risk, assumption, or question> | <impact> | <owner> | <plan> |

## Validation And Definition Of Done

- [ ] Each Must requirement has objective evidence.
- [ ] The implemented design matches `SADD.md` or the difference is recorded.
- [ ] Remaining risks and follow-up work are recorded.
