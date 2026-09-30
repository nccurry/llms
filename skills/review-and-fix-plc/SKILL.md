---
name: review-and-fix-plc
description: "Have a subagent review a written PLC, then fix supported findings in the plan. Use for a requested review-and-revision pass, not implementation or review-only requests."
---

# Review and Fix a PLC

Use the PLC named by the user, including all files in its planning packet. If its location is unclear, search the repository's planning docs before asking. Read the request and repository planning conventions. Check current source or authoritative docs when the PLC makes factual claims about existing behavior.

1. Send one subagent a **read-only** review assignment with the PLC paths, the user's goal, and relevant repository context. Give it the source material, not your own assessment or proposed fixes. Ask it to check accuracy, requirements coverage, consistency across files, design soundness and simplicity, risks and failure cases, phase dependencies, and whether acceptance and validation are concrete. It should report only actionable findings, each with a precise PLC location, supporting evidence, impact, and a proposed correction. It must distinguish verified facts from assumptions and leave the files untouched.
2. As the parent, inspect each finding against the current PLC and its supporting source. Edit the PLC to fix supported findings, including related contradictions elsewhere in the packet. Reject unsupported findings with a short reason. Preserve the user's scope and the repository's planning format. If a correction requires a material decision that the request and evidence cannot settle, ask the user and continue independent fixes.
3. Recheck the edited packet's requirements, design, phases, validation methods, and links. Run available documentation checks when useful. Report the fixes, any unresolved decisions, and the checks actually performed. Do not claim the PLC is ready based only on the subagent's report.

Apply [plain-english](../plain-english/SKILL.md) and [verify-before-claiming](../verify-before-claiming/SKILL.md). Give the subagent their resolved absolute paths and ask it to apply them too. If subagent tools are unavailable, report that the independent review could not be performed rather than presenting a self-review as one.
