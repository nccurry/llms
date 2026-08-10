---
name: plain-language-audit
description: Audit abstraction names, code comments, docstrings, READMEs, and Markdown documentation for LLM-style word salad, vague or overly abstract prose, unclear terminology, and non-idiomatic names. Use when the user asks for plain-English clarity, a word-salad review, clearer naming, or conventional language and framework terminology.
---

# Plain-Language Audit

## Workflow

1. Identify the review scope from the user request or current changes.
2. Read repository instructions, style guidance, and nearby code and documentation before judging terminology.
3. Identify the language, framework, and relevant documentation conventions.
4. Inspect abstraction names in folders, files, modules, types, functions, parameters, configuration keys, APIs, and tests; inspect code comments, docstrings, READMEs, and relevant Markdown documentation.
5. Judge a proposed replacement against deliberate repository conventions first, then language, standard-library, framework, and common ecosystem terminology.
6. Report only wording that has a concrete contextual defect. Offer a specific replacement that is plainer or more idiomatic.

## Review Criteria

Flag a name or sentence only when it:

- Hides the actor, action, object, ownership, or boundary that a maintainer needs to understand.
- Uses invented, metaphorical, or overly abstract terminology when an established term communicates the role more directly.
- Introduces needless jargon without defining it where readers need the meaning.
- Names an abstraction in a way that conflicts with the demonstrated meaning of that abstraction in the repository or ecosystem.
- Makes a comment or document less clear than direct, concrete language would be.

Do not use a banned-word list. A word is not a defect solely because it is technical, formal, unfamiliar, or sometimes used as jargon. Preserve established product, business, protocol, and external API vocabulary. Do not propose changes to quotations, prescribed names, or compatibility-sensitive public contracts without evidence that the name itself is wrong.

Treat a local convention as authoritative only when it is deliberate and coherent. Do not preserve a local naming pattern that conflicts with the language or framework without an explicit repository reason.

## Routing Boundaries

- Use this skill for plain-language clarity and conventional terminology across names, comments, and documentation.
- Use `abstraction-quality-audit` for ownership, file-tree structure, layering, dependency direction, and abstraction cost.
- Use `code-quality-audit` for control flow, cohesion, implementation idiom, and general maintainability.
- Use `docs-sync` when the question is whether documentation covers a code change rather than whether its language is clear.

## Output Contract

Lead with findings in impact order:

- `P2`: Wording or naming materially blocks safe understanding or change in an important path.
- `P3`: A concrete clarity or terminology defect that should be corrected but does not materially block work.

For each finding, include severity, confidence, a tight file and line reference, the specific wording or name, evidence for the applicable repository or ecosystem standard, its impact, and a direct plain-English or idiomatic replacement. Use high confidence for demonstrated local or official conventions and medium confidence for strong contextual evidence. Put candidates without sufficient evidence under blind spots.

If no actionable findings exist, say so. Name the files and conventions inspected. Keep audit-only requests read-only. If fixes are authorized, make the smallest wording or naming change that corrects the defect; request direction before renaming a public contract or changing unrelated behavior.
