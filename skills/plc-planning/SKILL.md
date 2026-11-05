---
name: plc-planning
description: Drafts and maintains change plans, specs, and PLC packets with requirements, design, delivery steps, and acceptance evidence. Use when asked to create or update a durable plan for a change, small or large. Work the user wants done without a plan, and review-only requests, do not need it.
---

# PLC Planning

## Overview

Use this skill to create or update a planning package. "Plan-Led Change" is
one name for this work; a repository may instead call it a plan, proposal,
spec, RFC, design note, implementation plan, or feature brief. The package
records requirements, design decisions, implementation phases, and validation
evidence.

## Examples

- "Make a PLC for a new configuration format": start from the shared
  template, with the repository's file names, location, and extra sections
  when it has them, and add SRD.md for the input, error, and compatibility
  behavior.
- "Save a short plan for this bounded refactor": use the compact plan, the
  same template as one file, with the affected behavior and proving checks.
- "Review this PLC without editing it": report findings; do not run this
  authoring workflow or change the packet.

For a reload change, a useful requirement is "Invalid input leaves the active
configuration unchanged." Its design validates before replacing state, and its
acceptance check submits invalid input and verifies the prior state is retained.
Record the check's actual result only after running it.

## Workflow

1. Find the repository's planning format.
   - Read root and scoped `AGENTS.md` files.
   - Look for planning guides, templates, and existing planning packages
     anywhere in the repository. Search using relevant names such as `plan`,
     `proposal`, `spec`, `requirements`, `design`, `architecture`,
     `implementation`, `change`, `RFC`, `ADR`, `roadmap`, and `feature`; do
     not rely on `PLC` alone.
   - Treat a repository's documented packet shape as a template, even when it
     is described in a README instead of separate template files.

2. Choose the packet source.
   - Every plan uses the [shared template](#shared-template). If the
     repository specifies a template or planning workflow, use its file names,
     location, and extra required sections on top of it: the shared sections
     come first, and the repository's own sections go before `## Log`. A
     repository whose rules require the full packet for PLC-sized work keeps
     that rule. If its template is still in an older shape, follow the shared
     template and tell the user.
   - Otherwise, start from [the default packet](assets/default-packet/README.md),
     a packet folder whose README holds the shared template, or from
     [the compact plan](assets/compact-plan.md), the same README as a single
     `plc-<slug>.md` file. Choose a folder when a trigger in
     [Adding files](#adding-files) holds or the repository keeps every plan
     in a folder; otherwise choose the one-file plan. A one-file plan
     becomes a folder when a trigger holds later, as
     [Growing a packet](#growing-a-packet) says. Small fixes may need only
     investigation, repair, and focused checks.
   - Do not invent file names, ledgers, or approval steps when neither the
     repository nor the user asks for them. Keep the packet in the
     [lifecycle folder](#lifecycle-folders) that matches its status, so
     finished plans don't sit beside active ones.
   - Store a durable packet with the repository's other durable planning docs.
     If there is no clear location, state the proposed location before writing.

3. Build the selected plan or packet.
   - Start with the README alone, and add SRD.md, SADD.md,
     IMPLEMENTATION_PLAN.md or FIXTURES.md only for a trigger in
     [Adding files](#adding-files) that already holds; then the plan starts
     as a folder. Put each kind of information in its file, as step 3 of
     [Growing a packet](#growing-a-packet) says. A new plan's Log needs only
     its Created line. A packet with SRD.md, SADD.md, and
     IMPLEMENTATION_PLAN.md is a full packet.
   - Delete sections that do not apply; never leave `N/A`, `TBD`, or empty
     headings. Add repository-specific sections only when they record a real
     constraint or decision.
   - Give each kind of information one home. The README owns the summary,
     status, phase state, open questions, the Log, and the requirements of a
     packet without SRD.md; SRD owns requirements with their checks, public
     contracts, and risks; SADD owns design and decisions; the implementation
     plan owns phase details and evidence. Link to existing schemas or
     evidence stores instead of copying their contents. Fixtures hold stable
     inputs and expected results, not another results ledger.

4. Write clear requirements and design.
   - Write each required behavior as a requirement with a permanent ID and a
     check, as the [requirements rules](#requirements-and-checks) describe.
   - Record scope, non-scope, risks, assumptions, and open questions. In a
     plan without SRD.md, scope limits go in the summary. A risk the plan
     must track and a prerequisite to confirm go where
     [Adding files](#adding-files) sends them; an assumption the plan must
     track is such a risk. Identify the work each unresolved question blocks
     and any permitted temporary assumption. Record the source revision
     inspected and relevant source/tests. For prerequisites, name the needed
     capability, its owner, and an availability check. Planning approval
     alone does not prove implementation is available. For moving upstream
     targets, date the inspected revision without silently fixing the
     product target to that snapshot.
   - Convert an active packet in an older shape to the shared template first,
     following [old-packet conversion](references/old-packet-migration.md).
     Don't add a second status block beside the old one.
   - When maintaining an approved packet, update affected sections in place.
     Preserve requirement IDs and decision rationale, reconcile superseded text,
     and keep status and evidence concise in their owning sections. Do not
     restate the skill's general workflow in the packet. Keep requirements
     and design focused on approved behavior and decisions, without raw logs or
     session narration. A new agent must be able to find approved scope, current
     design, and remaining work without the conversation. Distinguish proposed
     changes from approved requirements; do not silently weaken or defer
     acceptance to match the implementation. Replace Current Work as work
     changes and add history to `## Log`; do not append competing
     checkpoints. Remove superseded instructions from current sections,
     keeping only useful rationale in decisions or the Log.
   - Put useful implementation notes, adopted decisions, remaining work, and
     concise validation outcomes in the sections that own them, adding a file
     when [Growing a packet](#growing-a-packet) calls for one. Commit
     updates with the work. Delete temporary notes when no longer useful.
     Raw receipts, logs, binaries, and caches need no archive after an MR merges
     or a checkout closes. Keeping unfinished source does not require keeping
     unused build output; name the active need for any retained output.
     Do not make live worktrees or ignored output the only location for
     information a successor needs.
   - When a change affects a CLI, API, configuration, UI, or other public
     surface, summarize the action, expected result, and compatibility in the
     SRD. Add short expected-experience examples for each changed surface.
     Include error, empty, or permission behavior when it matters. For
     internal-only work, delete those SRD sections.
   - Explain the chosen design, relevant alternatives, changed boundaries,
     data flow, interfaces, and test design. Identify fixed contracts, safety
     rules, and ownership boundaries; distinguish suggested implementations
     from required decisions and leave routine internal choices open.
   - Use plain English and names that identify the actor, action, system part,
     and result. Replace vague claims such as "works well" with pass/fail measures.

5. Plan delivery and review.
   - Name the selected delivery's concrete endpoint. Divide it into useful
     phases, each proved by its requirements' checks. Write a phase's
     prerequisite, ordered steps, other exit criterion or rollback plan only
     when it has one, in IMPLEMENTATION_PLAN.md, as
     [Adding files](#adding-files) says. Before expanding it, consider reuse,
     deletion, or a narrower deliverable.
   - For work across packets or repositories, assign each shared acceptance
     obligation one owner. Children prove their contributions; the parent owns
     the integrated outcome. Name the authoritative contract and accepted
     decision or revision each consumer follows. Depend on the needed capability,
     not every remaining phase of a sibling packet.
   - Track each phase with a [phase state word](#words) in the README
     `## Phases` table, with the evidence notes the [Phases rules](#phases)
     require. A Merged phase does not close unverified acceptance; a missing
     record does not mean the work or its tests need repeating.
   - Record each result once with a requirement/check ID, tested source (including
     relevant uncommitted changes), date, relevant dependencies and environment,
     exact method, expected result, actual result and limits: under its phase
     in IMPLEMENTATION_PLAN.md, or, in a packet without that file, in the
     phase's note or the bullets below the README's `## Phases` table.
     Link to an unchanged method or an existing evidence store when sufficient.
     Required skipped or unavailable checks remain incomplete.
   - For difficult hardware, performance, or platform checks, prove the method
     early with a representative case and a known failure. Ordinary checks that
     already work do not need a separate qualification phase.
   - Discoveries do not add requirements or phases automatically.
     Significant expansion beyond existing authorization needs user approval before adoption or implementation,
     including new deliverables, contract/architecture changes, or substantially
     greater cumulative work. Routine repairs within approved scope can proceed.
     This boundary and the finish below are `plc-execution`'s defaults; write
     them into the plan only where this work differs.
   - The default finish: close selected work once its requirements and required
     checks pass, authorized delivery is verified, and cleanup is completed or
     explicitly accounted for. Optional outside-scope follow-ups do not extend
     execution or reopen completed work. Evidence that an existing requirement
     fails keeps acceptance open. Do not mark unselected phases Verified.
     For a retained checkout, name its owner, unfinished work or active
     dependency, and release condition. Avoid blanket preservation instructions
     that carry every draft and receipt into the next session.
   - For behavior that varies by platform/backend, map affected variants to
     proving checks and acceptance owners. Record deferrals and the prerequisite
     that revisits them; one passing variant does not verify the others.
   - When audit gates apply, record strict acceptance in the generated plan:
     fix every supported actionable finding in scope, including P3. Name the
     required review domains and acceptance standards, and keep model choices,
     worker counts and scheduling in the execution workflow. Missing required
     evidence remains incomplete. Do not require this skill to interpret the plan.
   - Run focused checks during implementation and broader checks at meaningful
     integration/delivery boundaries. State which evidence a behavior, dependency,
     environment change or discovered defect invalidates and why before repeating
     the affected check or review. A changed commit hash alone does not invalidate
     unaffected evidence; repository-required CI and post-merge checks still apply.
     Failures keep dependent acceptance open while independent work may proceed.
     If only a required record is missing, reconcile valid results into it first;
     rerun only for missing, insufficient or invalidated evidence. Do not waive
     required reviews, checks or records.
   - Keep the audit bounded: at most three consecutive passes total, including
     the initial pass, across handoffs and integration. Re-audit only for a
     verified serious finding or substantial change that invalidates prior
     review; repeat only affected specialists unless several domains require
     the full suite. Verify routine repairs with diff inspection and affected
     checks, preserving valid evidence. At the limit, stop audit delegation,
     continue authorized repairs/checks, and report unresolved findings or
     missing evidence without claiming `PASS`. Separate outside-scope debt
     from required repairs; do not create unrelated cleanup.

6. Validate before handoff.
   - Check that every major requirement maps to design and tests.
   - Check links and headings.
   - Run the [format check](#format-check) on the packet with `--strict`, and
     fix what it reports.
   - Run repo-appropriate documentation checks and `git diff --check` when
     available.
   - Run the [independent review](#independent-review) when it applies.
   - When this work has a ticket or the project uses tickets, run
     [manage-tickets](../manage-tickets/SKILL.md) once the user accepts the
     plan.

## Shared template

[The default packet's README](assets/default-packet/README.md) holds the
shared template, and [the compact plan](assets/compact-plan.md) is the same
README as one file. The words and rules below are its contract. Other skills
refer to this section instead of repeating it.

### Words

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

### Rules

#### Order and format

- Sections go in this order: title, summary, `## Current Work`,
  `## Phases`, `## Done when`, `## Open questions`, any repository-specific
  sections, then `## Log` last.
- Plain Markdown with `- Key: value` lines and no front matter. The format
  check and other tools find each line by its exact key name and read the
  value after the colon, so keep both as written here.

#### Fixed fields

Tools find these by their exact text, so each template, and every plan file
made from one, keeps them as written here:

- `README.md` and `compact-plan.md`: the section headings in
  [Order and format](#order-and-format) and the `- Key:` lines in
  [Current Work](#current-work), spelled as they are there, and the
  `## Phases` table header `| Phase | Name | Owner | State |`.
- `SRD.md`: the requirements table header
  `| ID | Priority | Requirement | Check |`. The format check reads the IDs
  in its first column.
- `SADD.md`: the decisions table header
  `| Decision or option | Status | Reason |`.
- `IMPLEMENTATION_PLAN.md`: one `### P<n>: <name>` heading for each phase,
  with the ID its `## Phases` row has.
- `FIXTURES.md`: the fixture table header
  `| ID | Area | Input and conditions | Expected result | Requirements |`.

#### Adding files

A plan starts as the README alone. Add a file only when one of its
triggers holds. Each trigger names a kind of information, not the size of
the work. The counts in them are more than 8 requirements for SRD.md, more
than 3 evidence bullets for IMPLEMENTATION_PLAN.md, and more than one
requirement or phase using the same test data for FIXTURES.md.

- **SRD.md** when the work adds or deliberately changes a public contract:
  anything people or programs outside the code rely on, such as a CLI
  command, flag, exit status or output format, an API, a configuration key
  or file format, or a UI flow. A bug fix is not a contract change: for
  example, an existing flag that now rejects, with a clear error, input it
  never handled correctly, such as a limit below 1 that printed nothing.
  Also when the plan must track a risk until it is handled:
  something that could make the work fail or cause harm, such as data loss
  or a dependency that may not be ready, with an owner and a check. A
  question one person can answer is an `Open question:` line, not a risk.
  Also when `## Done when` would list more than 8 requirements.
- **SADD.md** for a decision where another option was considered and
  rejected, such as a different library or storage format, with the reason.
  Also when the change alters how two or more modules or services connect,
  adds a third-party dependency, adds or changes stored data (such as a
  database table or file format), changes who can read or do what, sets a
  performance target, or needs a data or configuration migration.
- **IMPLEMENTATION_PLAN.md** when a phase needs written instructions beyond
  its requirements and their checks: a prerequisite to confirm, ordered
  steps, an exit criterion or a rollback plan. Also when a phase's evidence
  needs more than 3 bullets below the `## Phases` table.
- **FIXTURES.md** when checks need test data the repository does not
  already hold, such as sample files, recorded API responses, expected CLI
  output or screenshots, and more than one requirement or phase uses it.

Only approved work counts toward a trigger. Adding a file for approved work
needs no approval, even when a one-file plan becomes a folder. A proposal
that would add scope stays an `Open question:` line in the README and adds
no file until the user approves it. A file holds only the information its
trigger names; it is never added because the work is large or to fill out
the packet.

#### Growing a packet

When a skill updates an existing plan, and a trigger in
[Adding files](#adding-files) holds for a file the plan lacks, including
for what this update records, add the file in the same update. When the
repository has its own templates and file names, use them; otherwise use
this skill's `assets/default-packet/`.

1. A one-file plan becomes a folder first. In its lifecycle folder, create
   `<slug>/`, since `git mv` does not create it, then run
   `git mv plc-<slug>.md <slug>/README.md`. Its side files move in under
   the packet's names: `git mv plc-<slug>-srd.md <slug>/SRD.md`, a
   `-prd.md` file to `SRD.md` too, a `-sadd.md` file to `SADD.md`, and a
   `-plan.md` or
   `-implementation-plan.md` file to `IMPLEMENTATION_PLAN.md`. A file that
   arrives this way is not one the plan lacks, so it needs no new copy of
   the template. Update the links into and out of the moved files, as
   [Lifecycle folders](#lifecycle-folders) says for a move.
2. Copy the new file's template, such as
   [SRD.md](assets/default-packet/SRD.md), and delete the sections that do
   not apply.
3. Move the information into it, so it has one home: delete it from the
   README section or file where it was, and link to it from the part of the
   packet that uses it. Log lines are history and stay as written.
   - Requirements move with their IDs, text and checks unchanged, so moving
     one does not change it. Each gets Priority `Must` unless the plan says
     otherwise. `## Done when` then keeps only the pointer line the
     [requirements rules](#requirements-and-checks) give.
   - A public contract goes to SRD.md: its definition, including
     invalid-input behavior, in Public Contracts; a row in User Experience
     And Public Surface; and examples in Expected Experience. A risk goes to
     its Risks And Assumptions table.
   - A decision that meets SADD.md's trigger goes to SADD.md's decisions
     table. The Log line this update adds for it links there; older Log
     lines stay as written. Other design facts go to the SADD.md section
     that covers them.
   - A phase's details and evidence go under its `### P<n>: <name>` heading
     in IMPLEMENTATION_PLAN.md, and its `## Phases` row links to that
     heading.
   - Fixtures go to FIXTURES.md, linked from the requirements or phases
     that use them.
4. Add one dated Log line naming the file added and why:
   `- 2026-11-04 Added SRD.md: the new --max-age flag is a public contract.`

A packet in `completed/` never grows; new scope opens a new packet, as
[Ending a packet](#ending-a-packet) says.

#### Independent review

An independent reader catches gaps the author can't see. Before handing a
plan off, run [review-and-fix-plc](../review-and-fix-plc/SKILL.md), unless
the user declines, when:

- a plan is new, whatever its shape: one file, a README-only folder or a
  full packet;
- an update adds, changes or drops approved scope: a requirement or its
  check, a public contract, a tracked risk, a design decision, or a phase or
  its prerequisites, including a new SRD.md or SADD.md that
  [Growing a packet](#growing-a-packet) adds for it.

For an update, name the change, so the review covers it and the parts of the
plan that depend on it. Skip the review when an update changes only the
plan's records (Current Work, Log lines, phase states, evidence or links),
only moves information into a new file, or records a gap in existing scope
as its own phase row. Run it once per change; fixing its findings does not
call for another review.

#### Title and summary

- The title is `# <ID> <name>` when the repository numbers its packets, such
  as `PLC-012`; otherwise it is the name alone.
- One or two sentences sit directly under the title.

#### Current Work

- It is the one status block, directly after the summary. Skills replace its
  content each time, so it holds only its keys and the "Where the work
  lives" table. The one exception is a finished packet's historical-record
  line (see [Ending a packet](#ending-a-packet)).
- Status, Owner and Last updated come first, in that order, under exactly
  those names. Then Next action, Blocker, Depends on, Current state and
  Resume check. Keep each of these keys, and write `None` when one does not
  apply.
- Status starts with a packet status word; a note may follow ` — `.
- Owner names every person by `@handle`; a team name may stay beside the
  handles.
- Last updated starts with the date, as `YYYY-MM-DD`.
- Optional keys: `Selected work`, and, when packets replace one another,
  `Replaces: <path>` on the new packet and `Superseded by: <path>` on the old
  one.
- At most 12 keys, each kept to one or two lines. History goes to the Log.
- "Where the work lives" has one row per checkout: its path, its branch, the
  person or agent working there, and its State: in progress, waiting,
  locked, or kept, with the reason. With no checkouts, it has one `None` row.

#### Phases

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
  the table, one bullet per result starting with the phase ID:
  `- P1: task test → 112 passed @ abc1234, 2026-11-03`. A packet with
  IMPLEMENTATION_PLAN.md keeps it under the phase's heading there.

#### Requirements and checks

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
  stays where it is, marked Dropped with a [reason](#reasons), and new ones
  take the next number.

#### Reasons

- A Dropped requirement or phase, and an Archived or Superseded packet, has a
  note that starts with a reason word: superseded, duplicate, obsolete or
  won't do. For example: `Dropped — superseded by P3`.

#### Open questions

- Each unresolved point is one `Open question:` line in the README, naming
  what it blocks and whom it waits on:
  `- Open question: Should the cap be configurable? (blocks P2; waits on @sam)`.
- When it is answered, delete the line and add a dated `Decision:` line to
  the Log. Also record the decision in SADD.md's decisions table when
  SADD.md exists, or when it meets SADD.md's trigger in
  [Adding files](#adding-files), adding SADD.md as
  [Growing a packet](#growing-a-packet) says if the packet has none. The
  Log line then links to the table.

#### Log

- `## Log` is only ever added to: one dated line per state change, decision
  or surprise, newest last. A line about a merge names its merge request or
  commit.
- It is the packet's history; Current Work is its present.

#### Lifecycle folders

- `planned/`, `in-progress/`, `completed/` and `archived/`, under the plans
  folder. A one-file plan is a `plc-*.md` file in one of them.
- When Status changes between Planned and In progress, move the packet to
  `planned/` or `in-progress/` only when the repository already uses those
  folders. A finished packet always moves to `completed/`, and an abandoned
  or replaced one to `archived/`, as [Ending a packet](#ending-a-packet)
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

#### Ending a packet

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

### Rules across fields

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

### Format check

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
  first keys, known words and an Owner `@handle`, a Log, and status only in
  the README. In IMPLEMENTATION_PLAN.md, SRD.md or SADD.md, a phase table
  with state is a finding, and so is a `- Status:` or `- State:` line that
  starts with a packet status word or a phase state word, or a
  `- Lifecycle:` line that starts with a packet status word. A line such as
  `- Status: Approved; …` is not status. When SRD.md exists, these are
  findings too: a `## Done when` that is missing or has no line naming
  SRD.md, one that holds more than one paragraph or list item (a wrapped
  line counts once), and a requirement ID there from any table in SRD.md
  whose first column is `ID`. It ignores HTML comments and fenced code
  blocks. `--strict` adds the rules across fields.
- `--lifecycle <folder>` checks a packet as if it were in that lifecycle
  folder, for example before a finished packet moves to `completed/`.
- `--people` takes `NAME=HANDLE` pairs (HANDLE may start with `@`) and
  reports an Owner line that names one of them without the handle. Put plans
  folders before `--people`.
- It prints one line per finding. Exit 0 means nothing was found, 1 means
  findings, and 2 means a bad path or argument, nothing to check, or a file
  it could not read.
