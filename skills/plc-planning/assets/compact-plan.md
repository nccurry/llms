<!-- Compact plan: the shared PLC template as a single file. Save it as
`plc-<slug>.md` in a lifecycle folder such as `planned/`. When the work
needs more detail, make a `<slug>/` folder, move this file into it as
`README.md`, and add SRD.md (requirements, contracts and risks), SADD.md
(design and decisions) or IMPLEMENTATION_PLAN.md (phase details and
evidence) from plc-planning's default packet. Delete this note. -->

# <ID> <Feature name>

<One or two sentences: what this delivers and why. Plan lists and status
boards show this.>

## Current Work

- Status: Planned
- Owner: @<handle>, or a team name with its people's handles
- Last updated: <YYYY-MM-DD>, `<branch>` at `<short commit>`
- Next action: <one concrete step, or None>
- Blocker: <what is needed and who owns it, or None>
- Depends on: <packet IDs or folder names, comma-separated, or None>
- Current state: <one or two lines: what is done, merged, verified or waiting>
- Resume check: <the first command to run and its expected result>

Where the work lives:

| Checkout | Branch | Owner | State |
| --- | --- | --- | --- |
| None | | | |

## Phases

| Phase | Name | Owner | State |
| --- | --- | --- | --- |
| P1 | <name> | @<handle> | Planned |

## Done when

- REQ-001: <observable behavior>. Check: `<command or test>` → <expected result>

## Open questions

- Open question: <question> (blocks <phase or requirement IDs>; waits on @<handle>)

## Log

- <YYYY-MM-DD> Created.
