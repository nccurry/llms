---
name: plc-planning
description: Drafts and maintains change plans, specs, and PLC packets with requirements, design, delivery steps, and acceptance evidence. Use when asked to create or update a durable plan for a substantial change. Small fixes and review-only requests do not need this authoring workflow.
---

# PLC Planning

## Overview

Use this skill to create or update a planning package. "Plan-Led Change" is
one name for this work; a repository may instead call it a plan, proposal,
spec, RFC, design note, implementation plan, or feature brief. The package
records requirements, design decisions, implementation phases, and validation
evidence.

## Examples

- "Make a PLC for a new configuration format": use the repository's template;
  otherwise start from the default packet's README and add SRD.md for the
  input, error, and compatibility behavior.
- "Save a short plan for this bounded refactor": use the repository's format;
  otherwise use the compact plan with the affected behavior and proving checks.
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
     a packet folder whose README holds the shared template. For a one-file
     plan, use [the compact plan](assets/compact-plan.md), the same README as
     a single `plc-<slug>.md` file. Small fixes may need only investigation,
     repair, and focused checks.
   - Do not invent file names, ledgers, or approval steps when neither the
     repository nor the user asks for them. Keep the packet in the
     [lifecycle folder](#rules) that matches its status; a finished packet
     moves to `completed/` under the plans folder, so finished plans don't sit
     beside active ones.
   - Store a durable packet with the repository's other durable planning docs.
     If there is no clear location, state the proposed location before writing.

3. Build the selected plan or packet.
   - Size it to the work. Start with the README alone, and add a file only
     when the work needs that much detail:
     - [SRD.md](assets/default-packet/SRD.md) when the requirements need public
       contracts, risks, or more than a short `## Done when` list;
     - [SADD.md](assets/default-packet/SADD.md) when design choices or
       alternatives need a record;
     - [IMPLEMENTATION_PLAN.md](assets/default-packet/IMPLEMENTATION_PLAN.md)
       when a phase needs more detail or evidence than its row and note;
     - [FIXTURES.md](assets/default-packet/FIXTURES.md) only when stable
       fixtures, example inputs, API inventories, or visual reference cases
       will help implementation.
   - Link each added file from the README. When SRD.md holds the
     requirements, `## Done when` links to them instead of listing them. When
     IMPLEMENTATION_PLAN.md exists, link each phase row to its heading there.
   - Status lives in the README: `## Current Work` for the packet, the
     `## Phases` table for each phase, and `## Log` for history. No other file
     holds status or phase state.
   - Delete sections that do not apply; never leave `N/A`, `TBD`, or empty
     headings. Add repository-specific sections only when they record a real
     constraint or decision.
   - Give each kind of information one home. The README owns the summary,
     status, phase state, open questions, the Log, and a small packet's
     requirements; SRD owns requirements with their checks, public contracts,
     and risks; SADD owns design and decisions; the implementation plan owns
     phase details and evidence. Link to existing schemas or evidence stores
     instead of copying their contents. Fixtures hold stable inputs and
     expected results, not another results ledger.

4. Write clear requirements and design.
   - Give each required behavior a permanent ID and a check that can be run:
     a command or test, and its expected result.
   - Record scope, non-scope, risks, assumptions, and open questions. Identify
     the work each unresolved question blocks and any permitted temporary
     assumption. Record the source revision inspected and relevant source/tests.
     For prerequisites, name the needed capability, its owner, and an availability
     check. Planning approval alone does not prove implementation is available.
     For moving upstream targets, date the inspected revision without silently
     fixing the product target to that snapshot.
   - An active packet in an older shape moves to the shared template first,
     following [old-packet migration](references/old-packet-migration.md).
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
     concise validation outcomes in the packet's existing sections. Commit
     updates with the work. Delete temporary notes when no longer useful.
     Raw receipts, logs, binaries, and caches need no archive after an MR merges
     or a checkout closes. Keeping unfinished source does not require keeping
     unused build output; name the active need for any retained output.
     Do not make live worktrees or ignored output the only location for
     information a successor needs.
   - When a change affects a CLI, API, configuration, UI, or other public
     surface, summarize the action, expected result, and compatibility in the
     SRD. Add short expected-experience examples for each changed surface.
     Include error, empty, or permission behavior when it matters. Write
     `None` for internal-only work.
   - Explain the chosen design, relevant alternatives, changed boundaries,
     data flow, interfaces, and test design. Identify fixed contracts, safety
     rules, and ownership boundaries; distinguish suggested implementations
     from required decisions and leave routine internal choices open.
   - Use plain English and names that identify the actor, action, system part,
     and result. Replace vague claims such as "works well" with pass/fail measures.

5. Plan delivery and review.
   - Name the selected delivery's concrete endpoint. Divide it into useful
     phases with exact prerequisites, validation, and exit criteria. Before
     expanding it, consider reuse, deletion, or a narrower deliverable.
   - For work across packets or repositories, assign each shared acceptance
     obligation one owner. Children prove their contributions; the parent owns
     the integrated outcome. Name the authoritative contract and accepted
     decision or revision each consumer follows. Depend on the needed capability,
     not every remaining phase of a sibling packet.
   - Track each phase on the [state ladder](#words) in the README `## Phases`
     table, with the evidence notes the [Phases rules](#rules) require. A
     Merged phase does not close unverified acceptance; a missing record does
     not mean the work or its tests need repeating.
   - Record each result once with a requirement/check ID, tested source (including
     relevant uncommitted changes), date, relevant dependencies and environment,
     exact method, expected result, actual result and limits: under its phase
     in IMPLEMENTATION_PLAN.md, or in the phase note of a README-only packet.
     Link to an unchanged method or an existing evidence store when sufficient.
     Required skipped or unavailable checks remain incomplete.
   - For difficult hardware, performance, or platform checks, prove the method
     early with a representative case and a known failure. Ordinary checks that
     already work do not need a separate qualification phase.
   - State the execution boundary in the generated plan: discoveries do not add
     requirements or phases automatically. Significant expansion beyond existing
     authorization needs user approval before adoption or implementation,
     including new deliverables, contract/architecture changes, or substantially
     greater cumulative work. Routine repairs within approved scope can proceed.
   - Define a finish: close selected work once its requirements and required
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
   - For a new full packet, or one whose requirements or design changed
     substantially, run [review-and-fix-plc](../review-and-fix-plc/SKILL.md)
     before handoff unless the user declines. An independent reader catches
     gaps the author can't see. Skip it for compact plans and for routine
     Current Work updates.

## Shared template

[The default packet's README](assets/default-packet/README.md) holds the
shared template. The words and rules below are its contract. Other skills
refer to this list instead of repeating it.

### Words

- **Packet status words:** Planned, In progress, Blocked, Complete,
  Archived, Superseded.
- **Phase state words, in order:**
  - Planned;
  - In progress;
  - Implemented: done on a branch or in an open merge request, including a
    merge into an integration branch;
  - Merged: on the target branch, usually `main`;
  - Verified: its acceptance checks passed on the merged code;
  - Live: released or deployed.
- **Side states:** Blocked, Deferred, Dropped. Deferred and Dropped need
  approval in the plan or the conversation.
- **Merged is not Verified.** An unchecked phase stays Merged, with what is
  missing in the note.
- **Older words.** Tools that read packets also accept these in older text;
  new text uses the words above.
  - For packets: Draft, Ready and Proposed (Planned); In-progress,
    Developing, Reviewing and Active (In progress); Completed, Closed and
    Done (Complete).
  - For phases: Not started, Pending and Todo (Planned); Active and Started
    (In progress); Delivered (Merged); Complete, Completed, Done, Accepted
    and Passed (Verified).
- A word matches when it starts the text, ignoring case and Markdown
  emphasis.

### Rules

**Order and format**
- Sections go in this order: title, summary, `## Current Work`,
  `## Phases`, `## Done when`, `## Open questions`, any repository-specific
  sections, then `## Log` last.
- Plain Markdown with `- Key: value` lines and no front matter. Tools read
  it strictly.

**Title and summary**
- The title is `# <ID> <name>` when the repository numbers its packets, such
  as `PLC-012`; otherwise it is the name alone.
- One or two sentences sit directly under the title.

**Current Work**
- It is the one status block, directly after the summary. Skills replace its
  content each time, so it holds only its keys and the "Where the work
  lives" table.
- Status, Owner and Last updated come first, in that order, under exactly
  those names. Then Next action, Blocker, Depends on, Current state and
  Resume check.
- Status starts with a packet status word; a note may follow ` — `.
- Owner names every person by `@handle`; a team name may stay beside the
  handles.
- Last updated starts with the date.
- Optional keys: `Selected work`, and, when packets replace one another,
  `Replaces: <path>` on the new packet and `Superseded by: <path>` on the old
  one.
- At most 12 keys, each kept to one or two lines. History goes to the Log.

**Phases**
- The README `## Phases` table is the one place phase state lives. No other
  file has a phase table with a State or Status column.
- One row per phase, with every cell present. Follow-ups and notes go below
  the table, not in rows.
- New packets use IDs `P1`, `P2`, and `P2a` for sub-phases. Existing packets
  keep their IDs.
- Owner is a `@handle`, or blank for the packet owner.
- State starts with a phase state word; a short note may follow ` — `.
- When a state changes, the note names the merge request or commit:
  `Merged — !974 @ abc1234`.
- Verified and Live need evidence in the note: the check that passed and
  where it ran, such as `Verified — task test → 112 passed @ abc1234`, or a
  CI link.

**Requirements and checks**
- Each requirement says what is true when it is done, and names a check that
  can be run: a command or test, and its expected result. EARS wording
  ("WHEN … the system SHALL …") is optional.
- A README-only packet lists requirements under `## Done when`; a larger one
  keeps them in SRD.md.
- IDs are never renumbered, reused or renamed. A dropped requirement or phase
  stays where it is, marked `Dropped — <reason>`, and new ones take the next
  number.

**Open questions**
- Each unresolved point is one `Open question:` line in the README, naming
  whom it waits on.
- When it is answered, delete the line and add a dated `Decision:` line to
  the Log.

**Log**
- `## Log` is only ever added to: one dated line per state change, decision
  or surprise, newest last.
- It is the packet's history; Current Work is its present.

**Ending a packet**
- Dropped, Archived and Superseded notes start with a reason word:
  superseded, duplicate, obsolete or won't do.
- A finished packet moves to `completed/`. Its Current Work starts with the
  line "Historical record as of <commit>; the code is the current truth."
  After that it is not edited, and new scope opens a new packet.

**Other files**
- IMPLEMENTATION_PLAN.md holds phase details and evidence under
  `### P1: <name>` headings, with no state table of its own.
- SRD.md holds requirements with their checks. SADD.md holds design and
  decisions.

**Lifecycle folders**
- `planned/`, `in-progress/`, `completed/` and `archived/`, under the plans
  folder.
- A one-file plan is a `plc-*.md` file in a lifecycle folder.

### Rules across fields

The format check's strict mode reports these:

- The folder disagrees with the status:
  - `planned/` needs Planned or Blocked;
  - `in-progress/` needs In progress or Blocked;
  - `completed/` needs Complete;
  - `archived/` needs Archived or Superseded.
- Status is Blocked, but the Blocker line is missing or `None`.
- A phase is Verified or Live with no note after ` — `.
- A Dropped, Archived or Superseded note does not start with a reason word.
- A packet in `completed/` has a phase that is not Verified, Live, Deferred
  or Dropped. This applies when a packet moves there, not to packets already
  there.

### Format check

`scripts/format_check.py` in this skill's folder checks packets against the
template. Run it with Python 3 and no other dependencies:

```sh
python3 <skill-dir>/scripts/format_check.py --packet <packet> --strict
python3 <skill-dir>/scripts/format_check.py <plans folder> --people "Alex Kim=alex"
```

- `--packet` checks one packet folder or one-file plan, in any lifecycle
  folder. A plans folder checks every packet in its `planned/` and
  `in-progress/` folders, and skips flat design files such as `*-srd.md`.
- Default mode checks the structure: the summary, one Current Work with its
  first keys and known words, a Log, and phase state only in the README
  `## Phases` table. `--strict` adds the rules across fields.
- `--people` takes `NAME=HANDLE` pairs and reports an Owner line that names
  one of them without the handle. Put plans folders before `--people`.
- It prints one line per finding. Exit 0 means nothing was found, 1 means
  findings, and 2 means a bad path or bad arguments.
