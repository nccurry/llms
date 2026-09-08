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

## Interfaces And Data

List changed APIs, commands, configuration, schemas, files, UI behavior, and
state transitions. Write `None` when no public surface changes.

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
