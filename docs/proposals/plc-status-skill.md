# Proposal: `plc-status` skill

Status, 2026-10-27: **superseded** by [checkpoint-and-wrap-up.md](checkpoint-and-wrap-up.md). `plc-status` is now `plc-checkpoint`, and `wrap-this-up` merges unfinished work too.
Earlier status, 2026-10-24: built.
- `plc-status` reports, then brings the PLC records up to date.
- `wrap-this-up` handles closing only; its Checkpoint mode is removed.
- Seven runnable eval cases, with results, are in
  `tests/skill-evals/plc-status/README.md`.

## Problem

Mid-way through a PLC you keep asking some version of "where are we, what have
we done, what's left, and is the PLC up to date". Real examples from your Codex
and Claude sessions:

- "Summarize what we've done, what's left to do from what we planned, how much
  we need to finish to be "done" and what, if anything, we're blocked on"
  (sent to 8 parallel sessions at once on 2026-10-18)
- "Now summarize what we've done and what's left. Make sure the PLCs we're
  working against are up to date"
- "make sure the PLC is up to date, given what is already implemented, update
  anything stale"
- "Summarize what we've done, what's next, and what we're waiting for. Fact
  check that any dependencies haven't been implemented yet"
- "what's left to do that we planned or can I close this agent session"

Each answer is improvised, so its sections and depth change from session to
session. The survey of your sessions and packets found these repeated misses:

| Miss | Example seen |
| --- | --- |
| The packet on `main` is behind the packet in the active worktree | game2 PLC 08: `main` says every requirement is "Pending"; `game2-wt/plc08/implementation` says P1/P2 are handed off for audit |
| Local `main` is behind `origin/main` | dungeon-draft-tactics: local `main` lacks merged PRs #101 and #102 |
| The packet contradicts itself | devops runner-update: header says U2 hosted delivery is pending; phase table says U2 was delivered in PR 71 |
| Waits on other repos were overstated | comms Foundations: the agent claimed it was waiting on Roci features that were already on Roci `main` |
| Decisions made in chat never reach the packet | dungeon-draft-tactics: "Two calls I'm making on my own: Drop the Cost line…" |
| Deployed or live state is left out | devops runner MVP: your next question was whether hosts run the latest version |
| No clear answer to "can I close this session?" | devops runner MVP |
| Jargon left unexplained | devops job-containers: your next question was "what's a job container" |

## Proposal

One skill, `plc-status`, that you can run at any point during a PLC. It does
two things, in order:

1. **Reports where things stand,** in one fixed shape, checking every claim
   against git, the PR/MR host and the code, not only the packet's checkboxes.
2. **Brings the PLC records up to date** where the evidence shows they are
   stale.

It never closes work. Closing (merging, pushing, removing worktrees and
branches) stays with `wrap-this-up`.

### How it fits with the other skills

| You want to… | Skill |
| --- | --- |
| Know where we are, what's left, and whether I can close this session | `plc-status` |
| Make sure the PLC is up to date | `plc-status` |
| Just see the status, change nothing ("just tell me", "don't touch anything") | `plc-status`, report only |
| Finish: deliver, merge, clean up | `wrap-this-up` |
| Remove stale worktrees and branches | `clean-stale-worktrees` |
| Check the code against the completed requirements, as a review | `plc-alignment-audit` |
| Know whether one command finished | No skill; answer directly |

`wrap-this-up` loses its Checkpoint mode. Its closeout still reconciles the
records as its first step, following the same rules as `plc-status`. Its
cleanup-only mode stays.

### Where the facts come from

Checked in this order. When sources disagree, the source that proves the fact
wins, and the disagreement is reported as drift.

1. **Every copy of the packet:** local `main`, `origin/main`, the
   integration branch, and each campaign worktree. The report says which copy
   is newest.
2. **Git.** Fetch first, then the campaign's branches and worktrees,
   including older locations: `.claude/worktrees`, `~/.codex/worktrees`, and
   `~/Programming/worktrees`. For each, it reports uncommitted changes, commits
   ahead of and behind the target, locks, and last activity.
3. **PRs/MRs** through `gh` or `glab`. Squash merges make branches look
   unmerged; PR state settles it.
4. **Checks.** A "verified" claim needs a check that ran on the current
   commit.
5. **This conversation and child reports,** for decisions and scope calls.
6. **Other repos,** for dependencies only, checked on their `origin/main`.

### One set of states

Every requirement and phase is sorted onto one ladder, with the packet's own
wording quoted beside it:

`planned → in progress → implemented (on a branch) → merged → verified → live`

Side states: `blocked`, `deferred (approved)`, `dropped (approved)`. `live` is
used only when the PLC requires hosted, installed or deployed acceptance.
Merged and verified are never combined, and a local pass is reported apart
from hosted CI.

### The report

Fixed order. Every section is always present, with "None" when empty.

1. **Headline:** one sentence with counts by state, and "can I close this
   session?" answered yes, no, or "yes after X".
2. **Where we are:** the current phase, active work, and its owner.
3. **Done:** requirement or phase, state, evidence, and the packet's wording
   when it differs.
4. **In flight:** branches and worktrees with their state.
5. **Left:** split into "can start now" and "waiting on", each wait
   fact-checked.
6. **Scope added since the plan started.**
7. **Decisions since the work started:** each marked recorded or not.
8. **Open questions and blockers,** with questions for you first.
9. **What you can try now.**
10. **To close out:** a checklist, ending with an offer to run `wrap-this-up`
    when the work is ready.
11. **Drift and blind spots:** where the packet disagreed with the evidence,
    and what couldn't be checked.
12. **Records updated:** what this run changed in the packet, and where.

The brief version has the headline, Left, Blockers, To close out, and Records
updated. With several PLCs in progress, it gives one headline line per packet
and offers a full report for one.

### Updating the records

After the report, unless you asked for a report only:

- **What it may change:** the status and evidence parts of the packet. That
  means phase and requirement states, completion-map evidence, the Decisions
  and Open Questions tables, and contradictions between packet copies.
- **What it never changes:** approved requirements or design text. Where the
  evidence conflicts with them, it records the conflict as an open question
  or a labeled proposal for you to decide. An example is code that dropped a
  field a requirement asks for.
- **Decisions made in chat** are recorded in the Decisions table, with their
  status ("accepted" when you approved them in chat, "proposed" otherwise).
- **Where it edits:** in the checkout that holds the newest copy of the
  packet. It skips a checkout another agent is actively writing in, and says
  so in the report.
- **Commits:** only the packet files, in their own commit on that work
  branch. On the default branch it asks before committing.
- **Packet rules:** it follows the existing rules from `plc-planning`: update
  sections in place, keep requirement IDs and rationale, record each result
  once, and keep logs and session narration out.
- **Never:** code changes, merges, pushes, rebases, branch switches, or adding
  or removing worktrees.

### Files

```text
skills/plc-status/
  SKILL.md                         about 140 lines
  agents/openai.yaml               implicit invocation on
  references/report-template.md    the 12 sections with one filled example
  references/dependency-check.md   prompt for a subagent that checks one other repo
```

- **Loads:** `plain-english`, `verify-before-claiming`, and `plc-planning`,
  for packet discovery and the packet rules.
- **Script:** reuses `clean-stale-worktrees/scripts/worktree_report.py`, and
  must call the pinned `uv.exe` by its absolute path. On this machine `uv` and
  Python are not on the agents' PATH, so in the eval runs every agent fell
  back to plain git commands.
- **Gotchas section** in SKILL.md:
  - squash merges look unmerged
  - the main checkout's packet lags the worktree's copy
  - local `main` lags `origin/main`
  - state cells are sentences
  - old worktrees live outside the campaign folder
  - "verified" may refer to an older commit
  - "waiting" dependencies may be done already
  - a packet can contradict itself
  - chat decisions are often missing from the packet

### Frontmatter

```yaml
---
name: plc-status
description: Use when the user asks where a PLC or planned piece of work stands or wants its records brought up to date - "where are we", "what have we done", "what's left", "is the PLC up to date", "what are we blocked on", "can I close this session". Reports progress checked against git and PRs, then updates stale status, evidence and decisions in the packet. Does not merge, push, or clean up; wrap-this-up closes work.
argument-hint: "[plc-path-or-id]"
---
```

`argument-hint` is a Claude Code–only key, now on the validator's list. It
does no harm in Codex. `context: fork` is not used, because you want the
answer in the session you're working in.

## Evaluation

### What exists

Five runnable cases are in `tests/skill-evals/plc-status/`. Each has a
`case.yaml`, a `fixture/build.py` that builds real git repos, and graders.
A unit test builds every fixture and checks its trap.

First run (2026-10-24, one run each, with and without the skill, on the
read-only version):

| Case | With | Without |
| --- | --- | --- |
| packet-drift | 6/6 | 5.5/6 |
| origin-ahead | 6/6 | 6/6 |
| chat-decision | 5/5 | 4.5/5 |
| cross-repo-wait | 5/5 | 5/5 |
| near-miss-wrap-up | pass | pass |

Every run with the skill chose it without being told to. The fixtures were
small, so the version without the skill found most facts too. The difference
was the shape and the close-out steps.

### Changes for the new behavior

| Case | New expectation |
| --- | --- |
| packet-drift | Reports P1 implemented, and updates `main`'s stale packet copy, or the worktree copy if that is where work continues. The commit holds only packet files |
| origin-ahead | Reports P1 merged. The local packet is behind `origin`, so it says to pull rather than editing an old copy |
| chat-decision | Records both chat decisions in the Decisions table as accepted, since you said "ok, merge it". Adds an open question about the cost requirement. Requirement text is not changed |
| cross-repo-wait | Marks P2 no longer blocked, citing the timekit commit |
| near-miss-wrap-up | Unchanged: "Wrap this up" goes to `wrap-this-up` |
| new: report only | "Where are we? Don't change anything" changes no files |
| new: active writer | Another agent is editing the worktree's packet: report only, and say why |

The shared read-only grader becomes a **"no closing actions" grader**. It
allows commits that touch only packet files. It fails on code changes, merges,
pushes, branch changes, or added or removed worktrees. A new grader checks
that requirement and design text are unchanged.

In `tests/skill-evals.md`, "Make sure the PLC is up to date" moves from
`wrap-this-up` to `plc-status`. The `wrap-this-up` checkpoint rows are
rewritten as `plc-status` update rows.

## Decisions

| Question | Decision |
| --- | --- |
| Name | `plc-status` |
| Does it update the PLC? | Yes, by default. It takes over checkpoint from `wrap-this-up` |
| Where do decisions come from? | This conversation and child reports. Other transcripts are left out: slower and noisier |
| Read-only enforcement | Not applicable now. Its limits (no closing actions) are enforced by instructions and evals |

## Still open

- **A home for scope added after approval.** The packet template has Decisions
  and Open Questions tables, but nowhere to record scope added after approval.
  A "Changes since approval" table in `plc-planning`'s template would give
  `plc-status` one place to write it. That is a separate change.

## Work to do for the approved change

1. **`plc-status`:** add the record-update step, the 12th report section,
   the report-only switch, and the new description. Call `uv.exe` by its
   absolute path.
2. **`wrap-this-up`:** remove Checkpoint mode, and point record reconciliation
   at the shared rules.
3. **Evals:** update the five cases and graders, add the two new cases, and
   rewrite the related rows in `tests/skill-evals.md`.
4. Run `skills:validate` and the unit tests, then rerun the evals with and
   without the skill.

## Repo-wide follow-ups (not part of this skill)

- Measuring skills from real sessions: see `measuring-skills.md`.
- `metadata.version` and a license file per skill.
- Checks in CI that every skill loads in Claude Code and Codex.
- A shared runner for skill evals.

## Sources

- Anthropic, Skill authoring best practices:
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Agent Skills specification: https://agentskills.io/specification
- Claude Code skills: https://code.claude.com/docs/en/skills
- Codex skills: https://learn.chatgpt.com/docs/build-skills
- GitHub Spec Kit `/speckit-analyze`:
  https://github.com/github/spec-kit/blob/main/templates/commands/analyze.md
- OpenSpec `status` and `/opsx:verify`: https://github.com/Fission-AI/OpenSpec
- Kiro specs (Sync Files): https://kiro.dev/docs/specs/
- BMAD sprint status: https://docs.bmad-method.org/plan/break-work-into-stories-and-track-it/
- Nygard, Documenting Architecture Decisions:
  https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- DORA metrics: https://dora.dev/guides/dora-metrics/
