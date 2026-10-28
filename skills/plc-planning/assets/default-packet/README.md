# <Feature> PLC

## Current Work

Replace this block as work changes; do not append successive checkpoints.
Per-phase state lives in the
[Phase Status](IMPLEMENTATION_PLAN.md#phase-status) table.

- Status: <Draft | Ready | In progress | Complete>
- Owner: <person, team, or role>
- Last updated: <YYYY-MM-DD>, `<branch>` at `<short commit>`
- Selected work: <requirement IDs and phases authorized for this delivery>
- Current state: <what is implemented, verified, delivered, or awaiting a record>
- Next action: <one concrete step, or none>
- Blocker: <what is needed and who owns it, or none>
- Resume check: <command or inspection and expected result; link to the plan>

Where the work lives (a worktree lock, not this table, holds a checkout
against cleanup):

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| `<repo>-wt/<campaign>/<checkout>` | `<branch>` | <agent, session, or person> | <in progress, integration, or locked: reason> |

## Summary

State the problem, intended outcome, and smallest useful result. Link to the
[scope](SRD.md#scope) and [delivery plan](IMPLEMENTATION_PLAN.md); keep detailed
requirements, decisions, phase status, and evidence in their owning files.

## Packet

- [SRD.md](SRD.md): requirements, public contracts, risks, and open questions
- [SADD.md](SADD.md): design, ownership, decisions, and tradeoffs
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): delivery order, acceptance,
  current phase status, and verification evidence
- [FIXTURES.md](FIXTURES.md): optional stable inputs and expected results;
  remove this link when the file is omitted
