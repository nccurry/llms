# Converting an old-shape packet

Use this when an active packet is not yet in the
[shared template](shared-format.md). Signs of an older shape:

- no single `## Current Work` block directly after the summary;
- status in a `## Lifecycle` or `## Status` section, or in more than one
  place;
- phase state in a table in IMPLEMENTATION_PLAN.md, such as the older
  skill's Phase Status table;
- a `Lifecycle status:` or `Folder:` line.

Convert the packet first, then update it. Never add a second status block
beside the old one. "Convert" here means changing the format in place;
"move" means only a `git mv` to another folder.

## Before you start

- Convert only active packets: those in `planned/` or `in-progress/`, and
  those with no lifecycle folder that are not Complete. Leave completed and
  archived packets as they are, apart from links that a move changes. List a
  packet with no lifecycle folder as an owner case.
- Skip a packet that other people's work in progress is changing, and tell
  whoever owns that work. Such work is an open merge request's branch,
  another worktree's branch or commit, or uncommitted edits you did not
  make. The packet you are updating for its own work is yours to convert.
- Don't reword text. The only edits are moving whole lines and the format
  edits below. Five steps change what the packet says: M1's duplicate rule
  deletes lines, M5 adds a pointer line where a moved table was (and
  removes a heading the move left empty), M7 removes old status lines, M8
  adds a `## Done when` line, and E6 can add evidence. List each line they
  touch for the owner's review.
- An owner case is a point only the packet's owner can settle. Leave the
  text as it is, and list the case in your report and as an
  `Open question:` line. Never guess one. Owner cases include a status that
  disagrees with its packet or folder, a missing owner, a stale note, and a
  packet with no summary.

## Line moves

1. **M1. One Current Work block.** Make one `## Current Work` block directly
   after the summary.
   - Move into it, first and in order, the lines that give the status, the
     owner and the last-updated date.
   - Rename keys only as the table below allows.
   - Move a wrapped item with its continuation lines.
   - A `Status:` paragraph becomes a `- Status:` item.
   - Remove an old status heading only when its section is left empty.
   - When Current Work and an older section hold the same key, keep the
     Current Work line and delete the older one, unless the owner decides
     otherwise.

   | Old key | New key |
   | --- | --- |
   | `State` | `Status` when it starts with a packet status word; otherwise `Current state` |
   | `Owners` | `Owner` |
   | `Updated` | `Last updated` |
   | `Next step` | `Next action` |
   | `Blockers`, `Blocker / owner` | `Blocker` |
   | `Current phase`, `Progress` | `Current state` |

2. **M2. Handles.** Add `@handle`s beside names already in the Owner line,
   from a name-to-handle map the owner approved. A name with no handle in
   the map is an owner case.
3. **M3. Last updated.** Add a date-first `- Last updated:` line from the
   newest date the status text gives, keeping the line the date came from.
4. **M4. Summary.** Move the first paragraph of `## Summary` up to sit
   directly under the title. A packet with no `## Summary` and no paragraph
   under its title is an owner case.
5. **M5. Phases.** Move the packet's phase table that has a State or Status
   column, whole, under a new `## Phases` heading in the README. A link in a
   moved row to a heading in the file the table came from gains that file's
   name: `[P1](#p1-parse)` becomes `[P1](IMPLEMENTATION_PLAN.md#p1-parse)`.
   When the table came from another file, remove the table's heading, such
   as `## Phase Status`, if the table was the only thing under it, and write
   the line
   `Phase state lives in the README's [Phases](README.md#phases) table.`
   in that file where the table was. A table moved within the README needs
   no such line. A packet with two such tables is an owner case.
6. **M6. Log.** Add `## Log` at the end. Its first line comes from the
   `Created:` line, when there is one. Then add
   `- <date> Converted to the shared PLC template (format only).`
7. **M7. Old status lines.** Remove `Folder:` lines (the path says it). In
   other files, remove `Lifecycle status:` lines, and `- Lifecycle:` lines
   that start with a packet status word, as the format check reports them
   (the README holds the status). A line whose word disagrees with the
   README's Status is an owner case: leave it and list it.
8. **M8. Done when.** When the README has no `## Done when` and the packet
   has SRD.md, add `## Done when` in the template's
   [section order](shared-format.md#order-and-format), holding only the line the
   [requirements rules](shared-format.md#requirements-and-checks) choose. When
   the README has no `## Done when` and the packet has no SRD.md, even if
   its requirements sit under another heading, list it as an owner case:
   add no `## Done when`, and don't write requirements for it.

## Format edits

E3 is not used.

1. **E1. State words.** Put a state word in front of each status note or
   phase cell, keeping the old text after ` — `.
2. **E2. State column.** Add a State column where a phase table has none.
3. **E4. Owner decisions on state.** Write a state change the owner decided
   as `<word> — was: <old text>`.
4. **E5. Owner decisions on folders.** Move a packet the owner decided to
   move, together with the links that point at it. Superseded and abandoned
   packets go to `archived/`.
5. **E6. Evidence.** Give each Verified or Live cell its evidence after
   ` — `, taken from what its packet already records. When the cell already
   names it, only the separator changes. When the packet records no check,
   leave the cell as it is and list it as an owner case; the owner may
   change the word to Merged.

## The older skill's phase table

The older skill's Phase Status table has Implementation, Verification,
Delivery and Evidence record columns, but no State or Status column. Add a
State column at the end (E2), then move the table (M5). Find a row's parts
in its phase section, as the [Words](shared-format.md#words) list defines them.
The row's word is the latest one its own cells support:

- Live when Delivery records a release or deployment;
- Verified when all of the phase's parts are on the final target and
  Verification records a check that passed on them;
- Merged when all of the phase's parts are on the final target;
- otherwise Implemented, In progress or Planned. A row with only some of its
  parts merged follows the Words rule for a phase whose parts differ.

When the cells disagree, the row is an owner case.

## Check the result

Run the [format check](shared-format.md#format-check) on the packet, first in
default mode and then with `--strict`. Each finding left must be one of the
owner cases you listed. Report those cases, and each line M1 or M7 deleted
or M5, M8 or E6 added.
