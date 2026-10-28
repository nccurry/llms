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
  otherwise use the full packet and define input, error, and compatibility behavior.
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
   - If the repository specifies a template or planning workflow, use it. Its
     file names, location, lifecycle, and required sections take priority.
   - Otherwise, use [the default packet](assets/default-packet/README.md) for
     substantial work. For bounded work that still needs a durable plan, use
     [the compact plan](assets/compact-plan.md). Small fixes may need only
     investigation, repair, and focused checks.
   - Do not invent lifecycle folders, file names, ledgers, or approval steps
     when neither the repository nor the user asks for them. One exception:
     a completed packet moves to `done/` under the plans folder, unless the
     repository has its own convention, so finished plans don't sit beside
     active ones.
   - Store a durable packet with the repository's other durable planning docs.
     If there is no clear location, state the proposed location before writing.

3. Build the selected plan or packet.
   - For the compact form, keep the information in one document; do not create
     the full packet files below.
   - The full default packet contains [README.md](assets/default-packet/README.md),
     [SRD.md](assets/default-packet/SRD.md), [SADD.md](assets/default-packet/SADD.md),
     and [IMPLEMENTATION_PLAN.md](assets/default-packet/IMPLEMENTATION_PLAN.md).
   - Add [FIXTURES.md](assets/default-packet/FIXTURES.md) only when stable fixtures, example inputs, API
     inventories, or visual reference cases will help implementation.
   - If an optional file is omitted, remove its link from the generated packet.
   - Remove default sections that do not apply. Add repository-specific
     sections only when they record a real constraint or decision.
   - Give each kind of information one home. README owns orientation and a
     replaceable current-work block; SRD owns requirements, public contracts,
     risks and open questions; SADD owns design and decisions; the implementation
     plan owns phases, acceptance ownership, status and evidence. Link to existing
     schemas or evidence stores instead of copying their contents. Fixtures hold
     stable inputs and expected results, not another results ledger.

4. Write clear requirements and design.
   - Give each required behavior a stable ID, acceptance criteria, and a
     concrete validation method.
   - Record scope, non-scope, risks, assumptions, and open questions. Identify
     the work each unresolved question blocks and any permitted temporary
     assumption. Record the source revision inspected and relevant source/tests.
     For prerequisites, name the needed capability, its owner, and an availability
     check. Planning approval alone does not prove implementation is available.
     For moving upstream targets, date the inspected revision without silently
     fixing the product target to that snapshot.
   - When maintaining an approved packet, update affected sections in place.
     Preserve requirement IDs and decision rationale, reconcile superseded text,
     and keep status and evidence concise in their owning sections. Do not
     restate the skill's general workflow in the packet. Keep requirements
     and design focused on approved behavior and decisions, without raw logs or
     session narration. A new agent must be able to find approved scope, current
     design, and remaining work without the conversation. Distinguish proposed
     changes from approved requirements; do not silently weaken or defer
     acceptance to match the implementation. Replace the current-work block
     as work changes; do not append competing checkpoints. Remove superseded
     instructions from current sections, keeping only useful rationale in
     decisions or history outside the active reading path.
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
   - Track implementation, verification, delivery, and required records separately.
     A merged change does not close unverified acceptance; missing paperwork does
     not imply that implementation or tests need repeating.
   - Record each result once with a requirement/check ID, tested source (including
     relevant uncommitted changes), date, relevant dependencies and environment,
     exact method, expected result, actual result and limits. Link to an unchanged
     method or an existing evidence store when sufficient. Required skipped or
     unavailable checks remain incomplete.
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
     fails keeps acceptance open. Do not mark unselected phases complete.
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
   - Run repo-appropriate documentation checks and `git diff --check` when
     available.
   - For a new full packet, or one whose requirements or design changed
     substantially, run [review-and-fix-plc](../review-and-fix-plc/SKILL.md)
     before handoff unless the user declines. An independent reader catches
     gaps the author can't see. Skip it for compact plans and for routine
     Current Work updates.
