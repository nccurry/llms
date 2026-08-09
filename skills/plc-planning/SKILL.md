---
name: plc-planning
description: Draft and maintain Plan-Led Change documentation with Software Requirements Documents (SRD) and Software Architecture and Design Documents (SADD). Use when Codex is asked to plan a large feature, public API change, cross-package refactor, architecture change, phased delivery, or requirements-backed design package, especially under docs/llms/plans/plcs.
---

# PLC Planning

## Overview

Use this skill to create or update a Plan-Led Change packet: a requirements
document, architecture/design document, phased delivery plan, and validation
matrix that can guide later implementation branches.

## Workflow

1. Inspect the repo first.
   - Read root and scoped `AGENTS.md` files.
   - Look for `docs/llms/plans/`, `docs/llms/plans/plcs/`, and existing
     templates.
   - Prefer repo-local templates over generic structure.

2. Choose the planning shape.
   - Use `docs/llms/plans/` for durable ordinary implementation plans.
   - Use `docs/llms/plans/plcs/` when the work needs an SRD and SADD.
   - Keep ignored `/plans/` paths for local scratch only.

3. Write the SRD.
   - Include purpose, references, scope, system overview, requirement IDs,
     acceptance criteria, quality attributes, phased delivery, traceability,
     risks, assumptions, and validation.
   - Requirements must be testable and should avoid vague phrases such as
     "works well" unless paired with measurable acceptance criteria.

4. Write the SADD.
   - Include goals, constraints, context, building blocks, runtime/data flow,
     APIs/schemas, quality attribute design, test architecture, phases,
     decisions, risks, and deferred work.
   - Keep core architecture small and composable before describing larger
     convenience APIs.

5. Define bounded audit gates.
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

## References

Read `references/plc-source-guide.md` when external SRD/SADD template sources
or planning terminology need to be cited or refreshed.
