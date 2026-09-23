---
name: plc-alignment-audit
description: Check completed implementation against the PLC document or plan guiding the current work. Use during a full audit when the session is working from a plan.
---

# PLC Alignment Audit

If the current work has no guiding PLC document or plan, report `not applicable`.

Otherwise, read the plan and the implementation in the audit scope. For each requirement, design choice, and phase marked complete or included in the work completed so far, check that the code and tests match it. Report missing, partial, or conflicting work with the plan reference and implementation evidence. Do not treat planned future work as a gap.

State which plan and completed phases you checked. If the plan or implementation evidence is unavailable, name the blind spot. Return findings to `audit-codebase` using its severity and confidence rules; leave the aggregate verdict to that skill.
