# Shared PLC format

[The default packet's README](../assets/default-packet/README.md) holds the
shared template, and [the compact plan](../assets/compact-plan.md) is the same
README as one file. These rules are its contract. Other skills link here rather than repeat them.

## Words

- **Packet status words:** Planned, In progress, Blocked, Complete,
  Archived, Superseded.
- **Status follows the work:** Planned until work on a phase starts, then
  In progress. Blocked, Complete, Archived and Superseded follow their own
  rules.
- **Approved:** what the user asked for or accepted, in the plan or the
  conversation. Anything an agent adds beyond it is an `Open question:`
  line until the user accepts it. There is no separate approval step.
- **Phase state words, in order:**
  - Planned;
  - In progress;
  - Implemented: done on a branch or in an open merge request;
  - Merged: on the branch the work is delivered to, usually `main`. A merge
    into an integration branch is still Implemented;
  - Verified: its acceptance checks passed on the merged code;
  - Live: released or deployed.
- **Priority words:** High, Medium, Low. A packet with no Priority line
  is Medium.
- **Side states:** Blocked, Deferred, Dropped. Deferred and Dropped need the
  user's approval, in the plan or the conversation.
- **Parts.** A phase's parts are the tasks in its plan section and each of
  its requirements that no listed task builds. When one requirement or task
  names work that can be built separately, such as a function and the call
  that uses it, each piece is a part in its place. A part has started when
  a commit or uncommitted change does some of its work; until then it is
  Planned, even when every branch has merged. A started part stays In
  progress until all of its work is done.
- **A phase whose parts differ** gets its word in these steps:
  1. When every part has a side state, the phase is Blocked if any part is
     Blocked, otherwise Deferred if any is Deferred, otherwise Dropped.
  2. Otherwise, leave Deferred and Dropped parts out. Count a Blocked part
     as Planned when none of its work has started, and as In progress when
     some has.
  3. The phase takes the first of the remaining parts' words in the order
     above. If that is Planned and any part is In progress or later, the
     phase is In progress.

  Its note names each merged part with its merge request or commit, each
  part not yet merged, and each part with a side state:
  `In progress — REQ-001 merged @ abc1234; REQ-002 not started`, or, for a
  task split into a function and its call,
  `In progress — parse_config merged @ abc1234; its call from reload not started`.
- **A part moved to its own row** leaves its old phase: write
  `moved to P<n>` in the old phase's note, and choose the old phase's word
  from the parts it still holds. A part recorded only as an
  `Open question:` line stays a part of its phase.
- **Merged is not Verified.** A phase whose parts have all merged, but whose
  checks have not passed on the merged code, stays Merged, its note naming
  the checks still to pass. A check that does not exist because its work
  was never built marks a part not started, not a check still to pass.
- **Older words.** Tools still accept these in older text; new text uses the
  words above.
  - For packets: Draft, Ready and Proposed (Planned); In-progress,
    Developing, Reviewing and Active (In progress); Completed, Closed and
    Done (Complete).
  - For phases: Not started, Pending and Todo (Planned); Active and Started
    (In progress); Delivered (Merged); Complete, Completed, Done, Accepted
    and Passed (Verified).
- A word matches when it starts the text, ignoring case and Markdown
  emphasis.

## Rules

### Order and format

- Sections go in this order: title, summary, `## Current Work`,
  `## Phases`, `## Done when`, `## Open questions`, `## Merge requests`
  when the plan records them, any repository-specific sections, then
  `## Log` last.
- Plain Markdown with `- Key: value` lines and no front matter. The format
  check and other tools find each line by its exact key name and read the
  value after the colon, so keep both as written here.

### Fixed fields

Tools find these by their exact text, so each template, and every plan file
made from one, keeps them as written here:

- `README.md` and `compact-plan.md`: the section headings in
  [Order and format](shared-format.md#order-and-format) and the `- Key:` lines in
  [Current Work](shared-format.md#current-work), spelled as they are there, the
  `## Phases` table header `| Phase | Name | Owner | State |`, and the
  `## Merge requests` table header `| Phase | Merge request | State | Note |`.
- `SRD.md`: the requirements table header
  `| ID | Priority | Requirement | Check |`. The format check reads the IDs
  in its first column.
- `SADD.md`: the decisions table header
  `| Decision or option | Status | Reason |`.
- `IMPLEMENTATION_PLAN.md`: one `### P<n>: <name>` heading for each phase,
  with the ID its `## Phases` row has.
- `FIXTURES.md`: the fixture table header
  `| ID | Area | Input and conditions | Expected result | Requirements |`.

### Title and summary

- The title is `# <ID> <name>` when the repository numbers its packets, such
  as `PLC-012`; otherwise it is the name alone.
- One or two sentences sit directly under the title.

### Current Work

- It is the one status block, directly after the summary. Skills replace its
  content each time, so it holds only its keys and the "Where the work
  lives" table. The one exception is a finished packet's historical-record
  line (see [Ending a packet](shared-format.md#ending-a-packet)).
- Status, Owner and Last updated come first, in that order, under exactly
  those names. Then Next action, Blocker, Depends on, Current state and
  Resume check. Keep each of these keys, and write `None` when one does not
  apply.
- Status starts with a packet status word; a note may follow ` — `.
- Owner names every person by `@handle`; a team name may stay beside the
  handles.
- Last updated starts with the date, as `YYYY-MM-DD`.
- Priority, when present, starts with a priority word; a note may follow
  ` — `. Leave it out for the default, Medium. Boards sort by it.
- Optional keys: `Priority`, `Selected work`, and, when packets replace one
  another, `Replaces: <path>` on the new packet and `Superseded by: <path>` on
  the old one.
- At most 12 keys, each kept to one or two lines. History goes to the Log.
- "Where the work lives" has one row per checkout: its path, its branch, the
  person or agent working there, and its State: in progress, waiting,
  locked, or kept, with the reason. With no checkouts, it has one `None` row.

### Phases

- The README `## Phases` table is the one place phase state lives. No other
  file holds the packet's status or a phase's state.
- One row per phase, with every cell present.
- New packets use IDs `P1`, `P2`, and `P2a` for sub-phases. Existing packets
  keep their IDs.
- Owner is a `@handle`, or blank for the packet owner.
- The State cell holds a phase state word and, after ` — `, a short note.
  Longer notes and follow-ups go below the table, not in rows.
- When a state changes, the note names the merge request or commit:
  `Merged — !12 @ abc1234`.
- Verified and Live need evidence in the note: the check that passed and the
  commit or CI run it passed on, such as
  `Verified — task test → 112 passed @ abc1234`, or a CI link.
- Fuller evidence for a packet without IMPLEMENTATION_PLAN.md goes below
  the table, one record per result naming the phase ID:
  `- P1: task test → 112 passed @ abc1234, 2026-11-03`. A packet with
  IMPLEMENTATION_PLAN.md keeps it under the phase's heading there.

### Requirements and checks

- Each requirement says what is true when it is done, and names a check: a
  command, a test, or a written manual procedure, with its expected result.
  EARS wording ("WHEN … the system SHALL …") is optional.
- A packet without SRD.md lists requirements under `## Done when`. A packet
  with SRD.md keeps its requirements in SRD.md, and its `## Done when` holds
  only one line pointing there. If the repository has its own README
  template whose `## Done when` line points to SRD.md, use that line;
  otherwise use
  `The requirements and their checks are in [SRD.md](SRD.md).`
- IDs are never renumbered, reused or renamed. A dropped requirement or phase
  stays where it is, marked Dropped with a [reason](shared-format.md#reasons), and new ones
  take the next number.

### Reasons

- A Dropped requirement or phase, and an Archived or Superseded packet, has a
  note that starts with a reason word: superseded, duplicate, obsolete or
  won't do. For example: `Dropped — superseded by P3`.

### Open questions

- Each unresolved point is one `Open question:` line in the README, naming
  what it blocks and whom it waits on:
  `- Open question: Should the cap be configurable? (blocks P2; waits on @sam)`.
- A question about a detail of approved work blocks only that detail, never
  the behavior the user approved. Current Work's Blocker names each open
  question that blocks the next action, and only those.
- When it is answered, delete the line and add a dated `Decision:` line to
  the Log. Also record the decision in SADD.md's decisions table when
  SADD.md exists, or when it meets SADD.md's trigger in
  [Adding files](packet-files.md#adding-files), adding SADD.md as
  [Growing a packet](packet-files.md#growing-a-packet) says if the packet has none. The
  Log line then links to the table.

### Merge requests

- `## Merge requests` is optional. Recording merge requests is encouraged,
  not required, and a plan without the section is valid. Delete it when
  unused.
- One row per merge request or pull request: a phase may have several, in
  parallel, in a stack, or replacing one another. Closed and replaced ones
  keep their rows, so the table keeps the history. Each phase's note in
  `## Phases` still names its merge request or commit.
- Phase is an ID from the `## Phases` table. Merge request is `!12`, `#34`
  or the full URL. State is `Open`, `Merged @ <commit>` or
  `Closed — <reason>`.
- When you open a merge request for a phase, add its row and a
  `Plan: <packet ID or slug> <phase>` line to its description, such as
  `Plan: PLC-012 P2`. Both are optional. When the plan lives in another
  repository than the code, name it: `Plan: <repo> PLC-012 P2`.
- For a stacked merge request, the row's Note may say `stacked on !11`, so
  the chain can be rebuilt after the host retargets on a merge.
- Plan IDs stay out of merge request titles and commit messages. A tool that
  reads the table treats a row as the most certain link, and any other clue
  (the description, labels, the branch name, a ticket key) as a best-effort
  guess. A merge request with none of them is simply untracked.
- When the work has no PLC, skip all of this. If it follows another kind of
  plan, such as a ticket or an issue checklist, record the same facts in that
  plan's own place; when there is no plan, leave them out.
- A status update refreshes each row's State from the host, and offers
  rows for merge requests it finds by their branch or their `Plan:` line.

### Log

- `## Log` is only ever added to: one dated line per state change, decision
  or surprise, newest last. A line about a merge names its merge request or
  commit.
- It is the packet's history; Current Work is its present.

### Lifecycle folders

- `planned/`, `in-progress/`, `completed/` and `archived/`, under the plans
  folder. A one-file plan is a `plc-*.md` file in one of them.
- When Status changes between Planned and In progress, move the packet to
  `planned/` or `in-progress/` only when the repository already uses those
  folders. A finished packet always moves to `completed/`, and an abandoned
  or replaced one to `archived/`, as [Ending a packet](shared-format.md#ending-a-packet)
  says.
- Move a packet with `git mv`, keeping its folder or file name. Create the
  target folder first if it is missing, so the packet lands inside it. A
  one-file plan moves together with its side files, such as
  `plc-012-retry-srd.md`.
- After a move, update the links into the packet, and every relative link
  out of it that no longer resolves, including links to sibling packets.
- Finished plans that older versions of these skills put in another folder
  stay where they are; move them to `completed/` when convenient, with their
  links.

### Ending a packet

- A finished packet moves to `completed/`. Its Current Work starts with the
  line "Historical record as of <commit>; the code is the current truth.",
  naming the commit that finished it. After that the packet is not edited,
  with one exception: a single dated Log line may record cleanup that
  `plc-wrapup` could not finish. New scope opens a new packet, and so does
  a later failure of one of its requirements: the new plan names the old
  packet and the requirement.
- A packet the user drops moves to `archived/` with Status Archived and a
  reason; one that another plan replaces also moves there, with Status
  Superseded and a `Superseded by:` line. Its unfinished work is not
  merged.

## Rules across fields

The format check's `--strict` mode reports these five:

1. Status does not match the lifecycle folder:
   - `planned/` needs Planned or Blocked;
   - `in-progress/` needs In progress or Blocked;
   - `completed/` needs Complete;
   - `archived/` needs Archived or Superseded.
2. Status is Blocked, but the Blocker line is missing or `None`.
3. A phase is Verified or Live with no evidence note after ` — `.
4. A Dropped phase, or an Archived or Superseded packet, has a note that does
   not start with a reason word.
5. A packet in `completed/`, or checked with `--lifecycle completed`, has a
   phase that is not Verified, Live, Deferred or Dropped. A plans-folder run
   skips `completed/`, so packets finished earlier are not rechecked.

## Format check

`scripts/format_check.py` in this skill's folder checks packets against the
template. It needs Python 3.10 or later and nothing else:

```sh
python3 <skill-dir>/scripts/format_check.py --packet <packet> --strict
python3 <skill-dir>/scripts/format_check.py --packet <packet> --strict --lifecycle completed
python3 <skill-dir>/scripts/format_check.py <plans folder> --people "Alex Kim=alex"
```

- `--packet` checks one packet folder or one-file plan, in any lifecycle
  folder. A plans folder checks every packet in its `planned/` and
  `in-progress/` folders, and skips flat design files such as
  `plc-012-retry-srd.md`.
- Default mode checks the structure: the summary, one Current Work with its
  first keys, known words, an Owner `@handle`, a Priority that starts with
  a priority word when present, a Log, and status only in the README. In
  IMPLEMENTATION_PLAN.md, SRD.md or SADD.md, a phase table with state is a
  finding, and so is a `- Status:` or `- State:` line that
  starts with a packet status word or a phase state word, or a
  `- Lifecycle:` line that starts with a packet status word. A line such as
  `- Status: Approved; …` is not status. When SRD.md exists, these are
  findings too: a `## Done when` that is missing or has no line naming
  SRD.md, one that holds more than one paragraph or list item (a wrapped
  line counts once), and a requirement ID there from any table in SRD.md
  whose first column is `ID`. In `## Merge requests`, these are findings:
  a section without the table `| Phase | Merge request | State | Note |`, or
  with more than one table; a row whose cell count differs from the
  header's; a row whose phase is not in `## Phases`; and a Merge request or
  State cell that is not one of the forms in
  [Merge requests](shared-format.md#merge-requests). It ignores
  HTML comments and fenced code blocks. `--strict` adds the rules across
  fields.
- `--lifecycle <folder>` checks a packet as if it were in that lifecycle
  folder, for example before a finished packet moves to `completed/`.
- `--people` takes `NAME=HANDLE` pairs (HANDLE may start with `@`) and
  reports an Owner line that names one of them without the handle. Put plans
  folders before `--people`.
- It prints one line per finding. Exit 0 means nothing was found, 1 means
  findings, and 2 means a bad path or argument, nothing to check, or a file
  it could not read.
