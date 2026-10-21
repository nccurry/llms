---
name: plc-planning
description: Draft and maintain Plan-Led Change documentation with requirements, design, phases, and validation. Use for large features, public API changes, cross-package refactors, architecture changes, or phased delivery.
---

# PLC Planning

## Overview

Use this skill to create or update a planning package. "Plan-Led Change" is
one name for this work; a repository may instead call it a plan, proposal,
spec, RFC, design note, implementation plan, or feature brief. The package
records requirements, design decisions, implementation phases, and validation
evidence.

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
   - Otherwise, use `assets/default-packet/` as the starting point.
   - Do not invent lifecycle folders, file names, ledgers, or approval steps
     when neither the repository nor the user asks for them.
   - Store a durable packet with the repository's other durable planning docs.
     If there is no clear location, state the proposed location before writing.

3. Build the packet.
   - The default packet contains `README.md`, `SRD.md`, `SADD.md`, and
     `IMPLEMENTATION_PLAN.md`.
   - Add `FIXTURES.md` only when stable fixtures, example inputs, API
     inventories, or an acceptance matrix will help implementation.
   - If an optional file is omitted, remove its link from the generated packet.
   - Remove default sections that do not apply. Add repository-specific
     sections only when they record a real constraint or decision.

4. Write clear requirements and design.
   - Give each required behavior a stable ID, acceptance criteria, and a
     concrete validation method.
   - Record scope, non-scope, risks, assumptions, and open questions.
   - When maintaining an approved packet, update affected sections in place.
     Preserve requirement IDs and decision rationale, reconcile superseded text,
     and keep status and evidence concise in the existing work list or
     status/evidence sections. Record each result once and link to it elsewhere;
     do not restate the skill's general workflow in the packet. Keep requirements
     and design focused on approved behavior and decisions, without raw logs or
     session narration. A new agent must be able to find approved scope, current
     design, and remaining work without the conversation. Distinguish proposed
     changes from approved requirements; do not silently weaken or defer
     acceptance to match the implementation.
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
     data flow, interfaces, and test design.
   - Avoid overly abstract LLM word salad in plan content, proposed abstraction
     or variable names, descriptions, and comments. Use plain English and
     direct words that name the actor, action, system part, and result.
   - Avoid vague claims such as "works well" unless the packet gives a
     pass/fail measure.

5. Plan delivery and review.
   - Divide the work into useful phases with dependencies, validation, and
     exit criteria.
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
     fix every supported actionable finding in scope, including P3. Use
     focused read-only specialist reviewers against the same stabilized
     revision, in waves of at most three; the parent verifies evidence,
     combines findings, and owns fixes/checks. Missing required evidence
     remains incomplete. Do not require this skill to interpret the plan.
   - Keep the audit bounded: one initial aggregate pass and at most one final
     aggregate verification, refreshing affected reviews/checks and preserving
     valid evidence. Separate outside-scope debt from required repairs; do not
     create unrelated cleanup or repeat unchanged full audits.

6. Validate before handoff.
   - Check that every major requirement maps to design and tests.
   - Check links and headings.
   - Run repo-appropriate documentation checks and `git diff --check` when
     available.

Use `assets/default-packet/` only when the repository has no planning template
or documented equivalent, whatever it is called.
