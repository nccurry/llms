# Harbor export requirements

- Status: Approved; @sam signed off on 2026-11-03.

## Requirements

| ID | Priority | Requirement | Check |
| --- | --- | --- | --- |
| REQ-001 | Must | `harbor export` writes one CSV row per booking. | `task test -- export` → passes |
| REQ-002 | Must | An empty day writes only the header row. | `task test -- export_empty` → passes |

## Traceability

| Requirement | Design section | Phase |
| --- | --- | --- |
| REQ-001 | [Decisions](SADD.md#decisions-and-alternatives) | P1 |
