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

<!-- When the plan has SRD.md, this section holds only the line
`The requirements and their checks are in [SRD.md](SRD.md).` Delete this note. -->
- REQ-001: <observable behavior>. Check: `<command or test>` → <expected result>

## Open questions

- Open question: <question> (blocks <phase or requirement IDs>; waits on @<handle>)

## Merge requests

<!-- A new plan has no merge requests yet: delete this section, and add it
when the first one opens. It is optional: one row per merge request or pull
request for a phase, closed and replaced ones included; a phase may have
several. Merge request is `!12`, `#34` or the full URL. State is `Open`,
`Merged @ <commit>` or `Closed — <reason>`. A Note may say `stacked on !11`.
Delete this note. -->
| Phase | Merge request | State | Note |
| --- | --- | --- | --- |
| P1 | !<number> | Open | |

## Log

- <YYYY-MM-DD> Created.
