---
name: manage-tickets
description: "Creates, links, updates and closes tickets in the project's tracker (Jira, GitHub or GitLab issues, or another) the way the project already does it, and keeps plans and tickets pointing at each other. Acts only when the user asks, gives a ticket key, or the project's rules or history show tickets are used; otherwise does nothing. Use when the user asks to file, link, update or close a ticket; the planning, start, MR and wrap-up skills also call it at their events."
---

# Manage Tickets

Keep the project's tickets in step with the work, in the project's own
style. Other skills call this at their events; the user can also call it
directly.

Load [plain-english](../plain-english/SKILL.md) and
[verify-before-claiming](../verify-before-claiming/SKILL.md) first.

## 1. Decide whether to act

Act only when one of these holds:

- the user asks for a ticket action;
- the user, the plan or the branch gives a ticket key, such as `PROJ-123`
  or `#42`;
- the project's written rules or its history (step 2) show that its work
  is tracked in tickets.

Otherwise do nothing and say nothing about tickets. Never guess or make up
a key: a key comes from the user, the plan, the branch, or the tracker
itself.

A write to a tracker is seen by other people. Make it when the user asked
for it or the project's rules require it; otherwise propose it, with the
exact text, and wait.

## 2. Learn the project's style

Read these in order, and stop at the first that settles each question
(where the key goes, its form, which events change status):

1. **Written rules:** `AGENTS.md` and `CLAUDE.md`, and the files they point
   to; `CONTRIBUTING*`; MR, PR and issue templates; CI jobs that check MR
   titles, branch names or commit messages. Note a job marked
   `allow_failure` or not required: it is a preference, not a rule.
2. **Plans** that already track tickets, such as a key beside a phase.
3. **History:** where the key sits in recent MR titles and commit
   subjects, `Refs:` or `Closes` trailers, branch names, and the user's
   recent tickets.
4. **Ask once**, when nothing above settles it, and suggest recording the
   answer in `AGENTS.md` so nobody has to ask again.

Written rules win over history. When they disagree, for example rules that
say commits carry no ticket keys while recent commits do, follow the rules
and tell the user about the contradiction.

## 3. Link plan and ticket both ways

When there is a plan, put the key beside its phase (or in Current Work for
a one-phase plan), and put the plan's path in the ticket. Before creating a
ticket, search the tracker by key, by the plan's path and by title, and
link the existing one when found. A key beside a phase also lets a tool
match merge requests that carry the key to that phase. With no plan, keep the
key in the ticket and the merge request as the project's rules say.

## 4. Act on the event

| Event | What to do |
| --- | --- |
| Plan accepted | Create the ticket, or link the one that exists. |
| Work starts | Move it to in progress only if the rules say so. |
| MR opened | Put the key in the MR title, branch or body in the project's form. |
| MR merged, or wrap-up | Close or move it on only as the rules say, and only if the tracker's own automation has not already done it. |
| Work partly done or dropped | Add a comment saying what merged and what is left or dropped. Don't close it. |

On GitHub, closing keywords such as `Closes #42` close the issue only when
the MR merges into the default branch. For an MR that delivers part of a
ticket, use a reference that does not close it, such as `Refs #42`.

Read the ticket's state before each write and again after it, so you don't
repeat what automation already did and can confirm what changed.

## 5. Use the tools available

Try, in order: a `jira` CLI, `glab`, `gh`, then an MCP server for the
tracker. The [Jira](references/jira.md), [GitHub](references/github.md)
and [GitLab](references/gitlab.md) notes list common commands. With none
available, or no login, write out the ticket text, comment or MR title for
the user to paste, and say it was not sent.

## 6. Report

Name each ticket touched, with its key and link, what changed, and its
state read back after the change. List proposed writes that were not made,
and any contradiction found in step 2.
