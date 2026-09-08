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
   - Remove default sections that do not apply. Add repository-specific
     sections only when they record a real constraint or decision.

4. Write clear requirements and design.
   - Give each required behavior a stable ID, acceptance criteria, and a
     concrete validation method.
   - Record scope, non-scope, risks, assumptions, and open questions.
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
   - Use this policy in generated plans, templates, examples, phase exits, and
     acceptance criteria: Fix all P1/P2 findings. Fix P3 findings when
     inexpensive or explicitly required; otherwise record them. Rerun affected
     specialists after fixes and run one aggregate verification after
     convergence.
   - Do not require `resolve all findings`, `rerun until perfect`, or equivalent
     unbounded cleanup unless the user explicitly requires zero findings.

6. Validate before handoff.
   - Check that every major requirement maps to design and tests.
   - Check links and headings.
   - Run repo-appropriate documentation checks and `git diff --check` when
     available.

Use `assets/default-packet/` only when the repository has no planning template
or documented equivalent, whatever it is called.
