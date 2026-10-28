# Proposal: measuring skills from real sessions

Status: proposal, not approved. Date: 2026-10-24. Revised after two
independent reviews; their findings are listed at the end.

## Goals and limits

- Measure skills mainly from **real sessions**, not invented fixtures.
- Write **nothing into project repos or their git history** for measurement.
  The PLC packet stays what it is: the plan and its records, not a log.
- See how skill edits, models, and harness versions change results over time.
- Cover Claude Code and Codex on this Windows machine. WSL and other machines
  are out of scope for now. They could be added later by running the miner
  there.

## The data already exists

| Source | Where | What it holds | Gaps |
| --- | --- | --- | --- |
| Claude Code transcripts | `~/.claude/projects/<folder>/<session>.jsonl`, with child transcripts in `<session>/subagents/` | Every prompt, tool call and command. On every record: cwd, branch, harness version. Per assistant message: model, tokens, active skill (`attributionSkill`). Also `Skill` calls, permission decisions, errors and interrupts. A `skill_listing` per session, which in newer sessions includes a `digests` list | No cost field. Usage repeats across records of one request. Only the branch is recorded, not the commit |
| Codex rollouts | `~/.codex/sessions/YYYY/MM/DD/` and `~/.codex/archived_sessions/`, from 2026-10-09 | Prompts, commands with exit codes and durations, file diffs, tokens, the model per turn, the CLI version, and git commit and branch at start. Skills you name appear as a message of kind `skills.selected_skill_instructions` | No skill name field: the name is in that message's text. Child threads are separate files that repeat the parent's earlier messages |
| Your repos (read-only) | git history and worktrees | What merged and what remains | — |

**How much history there is.** Checked locally:
- **Claude:** all 27 sessions started in the desktop app, which is exempt
  from the 30-day transcript cleanup. The oldest is from 2026-10-19, so
  Claude history is about five days long.
- **Codex:** history reaches back to 2026-10-09.

So the first baseline is mostly Codex.

**Which skill version ran.** This is only reliably known from the install
log (below) onward. The `digests` in Claude's `skill_listing` exist only in
newer sessions, and it isn't known what they hash. Treat them as a hint at
most. Mark older sessions "version unknown".

## Where measurement data lives

One folder outside every repo and outside any cloud-synced folder:

```text
~/.agent-metrics/
  installs.jsonl     each skills:install run: time, host, target folder, llms commit,
                     dirty flag, digest per skill
  sessions.jsonl     one line per session and skill, written by the miner
  scans.jsonl        repo scan results
  grades.jsonl       your hand grades: session, skill, question, pass/fail, note
  miner-state.json   what the miner has already read
```

- **Schema version:** every line carries a `schema` field.
- **Session lines** also carry the host, harness version, model, session or
  thread ID, cwd, branch and campaign.
- **No prompt text or file contents.** Commands appear only as counts or
  pattern names.
- **Data for judge models:** none leaves the machine unless you start a judge
  or replay run yourself.

## The miner

A script in `llms`, run as `task metrics:mine`. Run it by hand to start; add a
Windows scheduled task later if you want it weekly. It reads transcripts,
updates `sessions.jsonl`, and prints the summary below.

**Reading rules:**
- **Incremental.** Claude files are keyed by session ID, Codex by thread ID,
  each with size and modification time. Keying by path would re-read Codex
  files when they move to `archived_sessions/`.
- **No double counting.** Group Codex child threads under their parent
  session, and skip the parent messages each child repeats. Attach Claude
  child transcripts to their parent session. Confirm the exact field names on
  real files when building this.
- **Tokens:** Claude repeats usage across records of one request, so count
  each `requestId` once. For Codex, use per-turn totals, never the sum of turn
  and running totals. Cost comes from a price table.
- **Skill use:**
  - Claude, started by the model: a `Skill` tool call.
  - Claude, named by you: a slash-command message or a `skill_mention`
    attachment.
  - Codex, named by you: the `skills.selected_skill_instructions` message,
    with the name parsed from its text.
  - Codex, chosen by the agent: a completed command whose parsed form is a
    read of a `SKILL.md`. Don't search the raw text for "SKILL.md": it appears
    in every rollout through the skill list.
- **Campaign:** from the cwd. That is `<repo>-wt/<campaign>/`, the Claude
  desktop worktree folder `<repo>/.claude/worktrees/<name>`, or a root that
  the repo's AGENTS.md sets. Otherwise from the branch name.
- **Format changes:** record unknown record types instead of failing. Test
  the parser on sample lines saved from each host version.

### The first summary

One row per host and skill:

| Column | Meaning |
| --- | --- |
| Version | Digest prefix from `installs.jsonl`, or "unknown" |
| Uses | Sessions where the skill ran |
| Started by | Model vs you |
| Tokens, time | Median per use |
| Your turns after start | User messages after the skill began, until the session went quiet |
| Interrupts | Interrupts within two turns of the skill starting |
| Errors | Tool errors and non-zero exit codes while the skill was active (Claude), or in the session (Codex) |
| Risky git | Matches for force-push, `reset --hard`, `clean -f`, `stash`, `checkout -- .`, `branch -D`, and `worktree remove --force` |
| Models | Model mix across those uses |

Below the table: the five sessions per skill with the most turns after start
or the most errors, with their transcript paths. Read those first, and turn
the worst into replays.

Explicit permission rejections and edits you changed by hand are not in
v1. Both are near zero here in auto mode: 6 rejections in 4,225 decisions,
and no edits changed by hand.

### What it can and can't answer

| Question | v1 measure | How |
| --- | --- | --- |
| Do skills trigger correctly? | Started by model vs by you, per skill. "Never fired when it should have" needs labeled prompts, so it is not in v1 | Script |
| Friction | Turns after start, interrupts, errors | Script |
| Forbidden actions | Risky git matches, from all past sessions | Script |
| Cost | Tokens and time per use | Script |
| Did they clean up? | See the repo scan | Script |
| Was a good PLC written? | Your grades in `grades.jsonl`; later a judge with checked rubrics | Manual, then judge |
| Did agents execute against it? | Requirement states at close need a parser for each repo's packet format; unapproved scope changes need a judge | Later |
| Code quality | CI results need `gh`/`glab`; `audit-codebase` findings are free text | Later |

v1 ships only the script rows.

## The repo scan

`task metrics:scan` walks `~/Programming` read-only and writes one line per
repo. It follows the cleanup rules your skills already use: **a branch is
kept when its idle checkout is removed**, so a remaining branch is not a
failure by itself.

It counts:
- checkouts by place: campaign folders, `.claude/worktrees/`, and anywhere else
- unlocked checkouts with uncommitted changes, and their age
- locked checkouts and their lock reasons
- **delivered branches still present**, meaning merged into the target, with
  their checkout gone
- undelivered branches kept, as a neutral count
- in-progress packets with no commits in 14 days

## Reading changes over time

Real-session numbers are **trend signals**, not proof that an edit helped:
- **Small samples:** most skills get few uses a week.
- **Other changes at the same time:** models and harness versions changed
  four times in five days here.

Every comparison shows the version, model and harness side by side, and flags
rows where more than the skill changed. Use **replays** to decide whether a
specific edit helped.

## Replays: tests built from real sessions

1. Pick a session from the summary's worst-five list, and write down the
   right answer. This is a few minutes of manual work per case.
2. The replay records the repo, the commit at the time, the prompt, and your
   right answer. It lives in `~/.agent-metrics/replays/`.
   - **Codex** records the commit at session start.
   - **Claude** records only the branch, so use the last commit on that branch
     before the prompt's timestamp.
3. To run one:
   - create a detached worktree at that commit in a temporary folder
   - run the skill version under test with `claude -p` or `codex exec`, using a
     separate `CLAUDE_CONFIG_DIR` or `CODEX_HOME` so the run stays out of your
     real history
   - grade the answer, then remove the worktree

## 0. Immediate improvements

1. **Make the GitNexus hook fire on PowerShell in Claude.** Its matcher is
   `Grep|Glob|Bash`, but Claude on this machine often runs PowerShell (198
   PowerShell calls against 21 Bash in one sampled session). Claude
   Code's docs say to match `Bash|PowerShell`. Codex is fine: its shell matches
   as `Bash`.
2. **Make the bundled scripts runnable.** Agents can't run `uv` or Python
   here: `uv` isn't found in agent shells, even though the pinned folder is in
   `env.PATH` in `~/.claude/settings.json`, and `python` doesn't work. So
   `worktree_report.py` never ran in the eval runs. Have the skills call the
   pinned `uv.exe` by absolute path, the way the hooks call `node.EXE`, or port
   the report to Node.
3. **Keep CLI transcripts.** Set `cleanupPeriodDays` high in
   `~/.claude/settings.json`, for example 3650. Desktop sessions are already
   exempt; this protects any terminal sessions.
4. **Put the main use case first in each description.** Both vendors say so.
   Codex's skill-list budget is not a problem: 2% of a 272,000-token window is
   far more than your roughly 9,100 characters.
5. **Put each skill's must-follow rules near the top.** After compaction,
   Claude keeps up to 5,000 tokens per skill within 25,000 in total, filled
   from the most recently used skill first. A skill loaded early in a long PLC
   session can be dropped entirely, so key rules belong in the packet too.
6. **Make `agents:configure` safe for future hooks on Codex.** Codex records
   trust per hook position, as in `hooks.json:pre_tool_use:0:0`. Adding a hook
   group before the GitNexus one changes its key, and Codex then silently
   skips the GitNexus hook until you trust it again. Add new groups after
   existing ones, and report any trust keys that changed. The Codex hook also
   starts `powershell.exe` before `node` on every shell call; calling
   `node.EXE` directly would save a process start each time.

## 1. Hooks

**v1 needs no new hooks.** The transcripts already record the cwd, branch,
versions, model, and every command, so the miner can find risky git commands
across all past sessions. A log-only guard would mostly repeat that.

Add a **git guard** only when you want it to refuse commands. By then the
miner will show how often each risky pattern happens and whether it was
legitimate.

**What the guard refuses:**
- force-push to a default branch
- `git reset --hard`, `git clean -fdx`, `git stash`, or `git checkout -- .` in
  a primary checkout with uncommitted changes

**What it never refuses**, because your skills allow these:
- `git branch -D` after delivery proof
- one `git worktree remove --force` once the remaining changes are understood
- worktrees outside the default layout

**How to build it:**
- Write it in Node, called directly.
- Match on `Bash|PowerShell`.
- Run `git status` only when a pattern matches.
- Deny with `permissionDecision: "deny"` and a reason, which both hosts
  support. Never use `ask`: Codex runs the command anyway.
- Print nothing else, and never set `onFailure: "block"`.
- Have it write a line to a heartbeat file, so `doctor` can see it ran.

Hooks that would not help here:
- **Session-end snapshots:** they don't fit the 1–3 second limits.
- **A status-ask counter or a compaction log:** the transcripts already hold
  that.

## Where to start, in order

1. Fix the GitNexus matcher and the scripts' access to `uv`, and set
   `cleanupPeriodDays` (improvements 1–3).
2. Have each `skills:install` target write a line to `installs.jsonl`.
3. Build `task metrics:mine` with the summary above. Run it over existing
   history: mostly Codex since 2026-10-09, plus about five days of Claude.
4. Build `task metrics:scan`.
5. Read the worst-five sessions per skill. Grade a few in `grades.jsonl`, and
   turn the worst into replays.
6. Decide on the guard in deny mode, a judge for plan quality, and
   packet-format parsers only for questions the summary can't answer.

## Review findings applied

**First review:**

| Finding | Change |
| --- | --- |
| The guard would block actions the skills allow | Deny only clear-cut cases; others never denied |
| Session-end snapshots don't fit the 1–3 second limits | Dropped |
| Codex records skills you name | Used by the miner; receipts dropped |
| The Codex skill-list budget was wrong | "Trim to fit" removed |
| `uv` is in `env.PATH` but not visible to shells | Call it by absolute path |
| Codex hooks are on by default but need trust | Trust handling added |
| Fail-safe hook behavior was missing | Hook rules added |
| Ask counter and compaction log repeat transcripts | Moved into the miner |
| Skill version keyed to the git commit | Keyed to the installed digest |
| Miner cost, folders, child transcripts, format drift | Miner rules added |
| Privacy | No prompt text or arguments stored |
| Replays would pollute history | Separate config folders |
| Sample size and confounders | Real data treated as trends |
| "Corrections" text matching is unreliable | Replaced with structural signals |
| Campaign and session boundaries | Rules added |
| Retention details | Corrected |
| Compaction can drop early skills | Stated |

**Second review** (each checked locally or in the docs; where my check
disagreed with the reviewer, the table says so):

| Finding | Change |
| --- | --- |
| Transcripts don't reliably show the skill version. The reviewer said `skill_listing` has no digests; I found a `digests` field in 16 records, from newer sessions only | Versions are known from `installs.jsonl` onward; older sessions are "unknown" |
| "Branches left" counted correct behavior as failure; the branch is kept by design | Count delivered branches and dirty unlocked checkouts instead |
| Claude desktop worktrees live in `<repo>/.claude/worktrees/` (8 such project folders here) | Added to the scan and the campaign rule |
| Codex child threads and archived files would double count | Key by thread ID; skip repeated parent messages. My sample didn't show the reviewer's exact field names, so check them when building |
| Several measures can't be computed from the named source | Each row marked script, manual, judge, or later; v1 ships script rows only |
| The v1 hooks mostly repeat the transcripts | v1 has no hooks; the guard comes later, in deny mode |
| New hooks can silently break the GitNexus hook's trust on Codex | Improvement 6 |
| Rejections and changed edits are near zero in auto mode | Replaced by turns after start, interrupts and errors |
| `cleanupPeriodDays` protects little here: all Claude sessions are desktop | Stated; the baseline is mostly Codex |
| Redacting arguments would hide force-push flags | Commands become pattern names, not stored text |
| gitleaks is not pinned in this repo | Dropped; nothing secret is stored |
| The GitNexus hook doesn't match PowerShell in Claude | Improvement 1 |
| The uv diagnosis. The reviewer said the PATH copies `.codex/tmp` folders; I found none in the settings PATH | Call `uv.exe` by absolute path |
| Installs differ per host | Host and target folder added to `installs.jsonl` |
| Open questions: how runs are triggered, where grades live, replay commits, the heartbeat | Answered in the relevant sections |
| The summary was unspecified | Columns and the worst-five list defined |

## Sources

- Claude Code hooks: https://code.claude.com/docs/en/hooks.md
- Claude Code data retention: https://code.claude.com/docs/en/data-usage.md#data-retention
- Claude Code skills: https://code.claude.com/docs/en/skills
- Codex hooks: https://learn.chatgpt.com/docs/hooks.md
- Codex skills: https://learn.chatgpt.com/docs/build-skills
- OpenAI, Testing Agent Skills Systematically with Evals (2026-01-22):
  https://developers.openai.com/blog/eval-skills
- Anthropic, Demystifying evals for AI agents (2026-01-09):
  https://anthropic.com/engineering/demystifying-evals-for-ai-agents
