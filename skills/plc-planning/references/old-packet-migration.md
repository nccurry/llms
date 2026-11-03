# Moving an old-shape packet

Use this when an active packet is not yet in the
[shared template](../SKILL.md#shared-template). Signs of an older shape:

- no single `## Current Work` block directly after the summary;
- status in a `## Lifecycle` or `## Status` section, or in more than one
  place;
- phase state in a table in IMPLEMENTATION_PLAN.md, such as the older
  skill's Phase Status table;
- a `Lifecycle status:` or `Folder:` line.

Move the packet first, then update it. Never add a second status block
beside the old one.

## Before you start

- Move only active packets: those in `planned/` or `in-progress/`, and those
  with no lifecycle folder that are not Complete. Leave completed and
  archived packets as they are, apart from links a move changes. List a
  packet with no lifecycle folder for the owner to place.
- Skip a packet that other live work is changing, and tell that work's
  owner. Live work is an open merge request's branch, a worktree's branch or
  commit, or uncommitted edits you did not make. The packet you are updating
  for its own work is yours to move.
- Don't reword text. The only edits are moving whole lines and the format
  edits below. Two of them delete or add text: M1's duplicate rule and E6's
  evidence. List each line they touch for the owner's review.
- Owner decisions are never guessed. A status that disagrees with its packet
  or folder, a missing owner, a stale note, and a packet with no summary go
  to the owner. List each one.

## Moves

| Step | Edit |
| --- | --- |
| M1 | Make one `## Current Work` block directly after the summary. Move into it, first and in order, the lines that give the status, the owner and the last-updated date. Rename keys only as this list allows: `State` to `Status` (when it starts with a packet status word) or `Current state`; `Updated` to `Last updated`; `Next step` to `Next action`; `Blockers` and `Blocker / owner` to `Blocker`; `Current phase` and `Progress` to `Current state`. Move a wrapped item with its continuation lines. A `Status:` paragraph becomes a `- Status:` item. Remove an old status heading only when its section is left empty. When Current Work and an older section hold the same key, keep the Current Work line and delete the older one, unless the owner decides otherwise. |
| M2 | Add `@handle`s beside names already in the Owner line, from a name-to-handle map the owner approved. A name with no handle in the map is an owner case. |
| M3 | Add a date-first `- Last updated:` line from the newest date the status text gives, keeping the line the date came from. |
| M4 | Move the first paragraph of `## Summary` up to sit directly under the title. A packet with no `## Summary` and no paragraph under its title is an owner case. |
| M5 | Move the packet's phase table that has a State or Status column, whole, under a new `## Phases` heading in the README. A link in a moved row to a heading in the plan's own file gains that file's name: `[P1](#p1-parse)` becomes `[P1](IMPLEMENTATION_PLAN.md#p1-parse)`. A packet with two such tables is an owner case. |
| M6 | Add `## Log` at the end. Its first line comes from the `Created:` line, when there is one; then add `- <date> Moved to the shared PLC template (format only).` |
| M7 | Remove `Folder:` lines (the path says it) and `Lifecycle status:` lines in other files (the README holds the status). |

## Format edits

| Step | Edit |
| --- | --- |
| E1, E2 | Put a state word in front of each status note or phase cell, keeping the old text after ` — `. Add a Status column where a phase table has none. |
| E4, E5 | Apply owner decisions: write a state change as `<word> — was: <old text>`, and move folders together with the links that point at them. Superseded and abandoned packets go to `archived/`. |
| E6 | Give each Verified or Live cell its evidence after ` — `, taken from what its packet already records. When the cell already names it, only the separator changes. When the packet records no check, the owner decides; the word may be Merged. |

The older skill's Phase Status table has Implementation, Verification,
Delivery and Evidence record columns but no State or Status column. Add a
Status column at the end (E2), then move the table (M5). Its word is the
highest rung the row's own cells support: Live when Delivery records a
release or deployment, Verified when Verification records a passed check,
Merged when the change is on the target branch, then Implemented, In
progress or Planned. When the cells disagree, the row is an owner case.

## Check the result

Run the [format check](../SKILL.md#format-check) on the packet. Default mode
should print only the cases left open for the owner, and `--strict` only the
owner cases you list. Report each owner case, and each line that M1 deleted
or E6 added.
