# Choosing and growing packet files

## Adding files

A plan starts as the README alone. Add a file only when one of its
triggers holds. Each trigger names a kind of information, not the size of
the work. The counts in them are more than 8 requirements for SRD.md, more
than 3 evidence records for IMPLEMENTATION_PLAN.md, and more than one
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
  needs more than 3 records below the `## Phases` table.
- **FIXTURES.md** when checks need test data the repository does not
  already hold, such as sample files, recorded API responses, expected CLI
  output or screenshots, and more than one requirement or phase uses it.

Only approved work counts toward a trigger. Adding a file for approved work
needs no approval, even when a one-file plan becomes a folder. A proposal
that would add scope stays an `Open question:` line in the README and adds
no file until the user approves it. A file holds only the information its
trigger names; it is never added because the work is large or to fill out
the packet.

## Growing a packet

When a skill updates an existing plan, and a trigger in
[Adding files](packet-files.md#adding-files) holds for a file the plan lacks, including
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
   [Lifecycle folders](shared-format.md#lifecycle-folders) says for a move.
2. Copy the new file's template, such as
   [SRD.md](../assets/default-packet/SRD.md), and delete the sections that do
   not apply.
3. Move the information into it, so it has one home: delete it from the
   README section or file where it was, and link to it from the part of the
   packet that uses it. Log lines are history and stay as written.
   - Requirements move with their IDs, text and checks unchanged, so moving
     one does not change it. Each gets Priority `Must` unless the plan says
     otherwise. `## Done when` then keeps only the pointer line the
     [requirements rules](shared-format.md#requirements-and-checks) give.
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
[Ending a packet](shared-format.md#ending-a-packet) says.
