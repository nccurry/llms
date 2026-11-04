# Harbor export requirements

- **Lifecycle:** Draft

## Requirements

| ID | Priority | Requirement | Check |
| --- | --- | --- | --- |
| REQ-001 | Must | `harbor export` writes one CSV row per booking. | `task test -- export` → passes |
| REQ-002 | Must | An empty day writes only the header row. | `task test -- export_empty` → passes |
