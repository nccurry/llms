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
   - Every plan uses the [shared template](references/shared-format.md). If the
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
     [Adding files](references/packet-files.md#adding-files) holds or the repository keeps every plan
     in a folder; otherwise choose the one-file plan. A one-file plan
     becomes a folder when a trigger holds later, as
     [Growing a packet](references/packet-files.md#growing-a-packet) says. Small fixes may need only
     investigation, repair, and focused checks.
   - Do not invent file names, ledgers, or approval steps when neither the
     repository nor the user asks for them. Keep the packet in the
     [lifecycle folder](references/shared-format.md#lifecycle-folders) that matches its status, so
     finished plans don't sit beside active ones.
   - Store a durable packet with the repository's other durable planning docs.
     If there is no clear location, state the proposed location before writing.

3. Build the selected plan or packet.
   - Start with the README alone, and add SRD.md, SADD.md,
     IMPLEMENTATION_PLAN.md or FIXTURES.md only for a trigger in
     [Adding files](references/packet-files.md#adding-files) that already holds; then the plan starts
     as a folder. Put each kind of information in its file, as step 3 of
     [Growing a packet](references/packet-files.md#growing-a-packet) says. A new plan's Log needs only
     its Created line. A packet with SRD.md, SADD.md, and
     IMPLEMENTATION_PLAN.md is a full packet.
   - Delete sections that do not apply; never leave `N/A`, `TBD`, or empty
     headings. Add repository-specific sections only when they record a real
     constraint or decision.
   - Choose structure with [writing guidance](references/writing.md); preserve it
     as the plan grows. Keep generic workflow policy in skills; put only
     work-specific constraints and exceptions in the packet.
   - Give each kind of information one home. The README owns the summary,
     status, phase state, open questions, the Log, and the requirements of a
     packet without SRD.md; SRD owns requirements with their checks, public
     contracts, and risks; SADD owns design and decisions; the implementation
     plan owns phase details and evidence. Link to existing schemas or
     evidence stores instead of copying their contents. Fixtures hold stable
     inputs and expected results, not another results ledger.

4. Write clear requirements and design.
   - Write each required behavior as a requirement with a permanent ID and a
     check, as the [requirements rules](references/shared-format.md#requirements-and-checks) describe.
   - Record scope, non-scope, risks, assumptions, and open questions. In a
     plan without SRD.md, scope limits go in the summary. A risk the plan
     must track and a prerequisite to confirm go where
     [Adding files](references/packet-files.md#adding-files) sends them; an assumption the plan must
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
     when [Growing a packet](references/packet-files.md#growing-a-packet) calls for one. Commit
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
     [Visual aids](references/writing.md#visual-aids) says when a diagram helps.
   - Use plain English and names that identify the actor, action, system part,
     and result. Replace vague claims such as "works well" with pass/fail measures.

5. Plan delivery and review.
   - Name the selected delivery's concrete endpoint. Divide it into useful
     phases, each proved by its requirements' checks. Write a phase's
     prerequisite, ordered steps, other exit criterion or rollback plan only
     when it has one, in IMPLEMENTATION_PLAN.md, as
     [Adding files](references/packet-files.md#adding-files) says. Before expanding it, consider reuse,
     deletion, or a narrower deliverable.
   - For work across packets or repositories, assign each shared acceptance
     obligation one owner. Children prove their contributions; the parent owns
     the integrated outcome. Name the authoritative contract and accepted
     decision or revision each consumer follows. Depend on the needed capability,
     not every remaining phase of a sibling packet.
   - Track each phase with a [phase state word](references/shared-format.md#words) in the README
     `## Phases` table, with the evidence notes the [Phases rules](references/shared-format.md#phases)
     require. A Merged phase does not close unverified acceptance; a missing
     record does not mean the work or its tests need repeating.
   - Record each result once with a requirement/check ID, tested source (including
     relevant uncommitted changes), date, relevant dependencies and environment,
     exact method, expected result, actual result and limits: under its phase
     in IMPLEMENTATION_PLAN.md, or, in a packet without that file, in the
     phase's note or the records below the README's `## Phases` table.
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
   - Compare the final section order with [Order and format](references/shared-format.md#order-and-format).
     Custom sections such as Design notes follow all shared sections; when
     Open questions remains, it comes before Design notes. The format checker
     does not enforce this order, so inspect it separately.
   - Run the [format check](references/shared-format.md#format-check) on the packet with `--strict`, and
     fix what it reports.
   - Run repo-appropriate documentation checks and `git diff --check` when
     available.
   - Run the [independent review](#independent-review) when it applies.
   - When this work has a ticket or the project uses tickets, run
     [manage-tickets](../manage-tickets/SKILL.md) once the user accepts the
     plan.

## Shared template

Read [the shared format](references/shared-format.md) when writing or updating
a packet. It owns the exact fields, state words, section order and checker rules.
Read [choosing and growing files](references/packet-files.md) before adding a
file or moving information between files. Use [writing guidance](references/writing.md)
when composing or reorganizing explanations, steps, comparisons and evidence.

The [compact example](references/examples/compact.md) and
[substantial phase example](references/examples/phase.md) show finished invented
content. Read the example that fits; neither is another required packet shape.

## Independent review

An independent reader catches gaps the author can't see. Before handing a
plan off, run [review-and-fix-plc](../review-and-fix-plc/SKILL.md), unless
the user declines, when:

- a plan is new, whatever its shape: one file, a README-only folder or a
  full packet;
- an update adds, changes or drops approved scope: a requirement or its
  check, a public contract, a tracked risk, a design decision, or a phase or
  its prerequisites, including a new SRD.md or SADD.md that
  [Growing a packet](references/packet-files.md#growing-a-packet) adds for it.

For an update, name the change, so the review covers it and the parts of the
plan that depend on it. Skip the review when an update changes only the
plan's records (Current Work, Log lines, phase states, evidence or links),
only moves information into a new file, or records a gap in existing scope
as its own phase row. Run it once per change; fixing its findings does not
call for another review.
