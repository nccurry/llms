---
name: explain-technical-choices
description: "Help a user answer an agent's unclear technical question by explaining the options, concrete effects, and tradeoffs. Use when the user needs context before making a choice."
---

# Explain Technical Choices

Help the user understand a technical decision that another agent has put to them. Make the choice clear enough that they can answer it with confidence.

## Ground the explanation

Read the agent's exact question and the surrounding conversation. Inspect only the plan, code, diff, configuration, or other material needed to understand the choice. If that material is unavailable, say what is unknown. Do not present an invented example as current behavior.

Apply [plain-english](../plain-english/SKILL.md) to the response. When an example from the work would clarify an option, follow [work-visual-summary](../work-visual-summary/SKILL.md) for a small, source-backed code, command, config, API, or UI example. Label proposed or illustrative examples clearly. Keep the examples focused on the decision.

## Explain the decision

- Restate what the agent needs the user to decide and why the choice matters now. Define any term the user needs to understand it.
- For each viable option, show what would happen in practice. Compare the benefits, costs, risks, and ease of changing course later that matter to this choice. Use the same concrete scenario across options when that makes the difference clearer.
- Separate facts found in the work from assumptions and unanswered questions. If a missing fact could change the answer, name the fact and how to get it.
- Say which option you recommend when the evidence and the user's stated priorities support one. Explain the reason and the condition under which you would choose differently. If the choice depends on a user preference, explain the preference instead of deciding it for them.
- If the agent can make the choice from requirements already given, say so and suggest a direct answer. Do not turn a routine implementation choice into a new user decision.

For several questions, handle each separately and show any dependency between them. End with a short answer the user could send to the agent, or a precise follow-up question when essential information is missing. Do not change the implementation or send the answer to another agent unless the user asks.
