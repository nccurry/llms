# plc-checkpoint eval cases

Thirteen runnable cases for [`plc-checkpoint`](../../../skills/plc-checkpoint/SKILL.md),
modeled on the case shape in trailofbits/skills: each case folder has a
`case.yaml`, a `fixture/build.py` that creates its git repositories, and
Markdown graders. They live here, not in the skill folder, because the
installer copies the whole skill folder into each agent.

| Case | What it checks |
| --- | --- |
| [morning-refresh](morning-refresh/case.yaml) | Yesterday's Current Work is stale; P1 merged into integration since. Report the change, tidy P1, rewrite Current Work, keep Owner and the Replaces link, add a Log line |
| [packet-drift](packet-drift/case.yaml) | `main`'s packet says nothing has started; the worktree's copy and commits show P1 implemented |
| [origin-ahead](origin-ahead/case.yaml) | P1 merged on `origin/main`; local `main` is behind. Tidy the merged worktree and branches |
| [dirty-finished](dirty-finished/case.yaml) | P1 merged, but its worktree has untracked notes: keep it |
| [chat-decision](chat-decision/case.yaml) | Two scope calls made in the conversation are missing from the packet, and the merged code no longer meets SHOP-001: record the gap, never tick it |
| [cross-repo-wait](cross-repo-wait/case.yaml) | The plan waits on another repo whose `origin/main` already has the work: unblock P2 and keep the Depends on line |
| [plan-in-other-repo](plan-in-other-repo/case.yaml) | The plan lives in a separate plans repo: commit Current Work there, push nothing |
| [ad-hoc](ad-hoc/case.yaml) | No plan: report from the conversation and git, create nothing |
| [report-only](report-only/case.yaml) | "Just tell me, don't change anything" must change nothing |
| [active-writer](active-writer/case.yaml) | Another agent's uncommitted packet edits must be left alone |
| [old-shape](old-shape/case.yaml) | The packet is in an older shape: convert it to the shared template first, ending with one `## Current Work`, then update it. P1 stays In progress, because nobody built its call from `save_booking`; if that call moves to its own row, P1 must be Merged or Verified |
| [grow-plan](grow-plan/case.yaml) | The user approved a new `--max-age` CLI flag for an in-progress one-file plan. The flag is a public contract, so the plan becomes a `tide-cache/` folder whose `SRD.md` holds TIDE-001, moved unchanged, and the new flag's requirements with their checks, `## Done when` keeps only the pointer line, and a dated Log line names `SRD.md` |
| [near-miss-wrap-up](near-miss-wrap-up/case.yaml) | "Wrap this up" must go to `plc-wrapup` |

`check_state.py` compares a fixture with the `_snapshot.json` and
`_expect.json` its build script wrote:
- **Required:** removing each finished worktree, local branch, and remote
  branch listed in `_expect.json`.
- **Allowed:** plan record edits under `docs/plans/`, and commits that touch
  only those files. A packet file moved unchanged, as a lifecycle move does,
  is reported as a move.
- **Violations:** removing anything else, pushes, merges, new branches or
  worktrees, code edits, and a changed or removed requirement row in an
  existing `SRD.md` or `-srd.md` or `-prd.md` side file. Added rows and
  columns are allowed, also in a moved or renamed copy.
- **Packet text**, for a case whose `_expect.json` has `packet_content`
  (old-shape and grow-plan): a phase's state word, lines that must or must
  not be in `IMPLEMENTATION_PLAN.md`, the `## Done when` line and place,
  and no removed worktree still listed in "Where the work lives". For
  grow-plan: the one-file plan gone, the requirement rows `SRD.md` must
  hold by ID, each with its text and a check, a dated Log line, and, once
  those pass, the shipped format check in strict mode.

It prints JSON and exits 1 on a violation. The outcome graders then judge the
report and the plan edits, and [plan-record.md](graders/plan-record.md) holds
the shared template's rules for any plan edit: one `## Current Work`, Owner
and links kept, state words with the commit in each changed phase note, a
dated Log line per state change, Verified only with evidence, and gaps
recorded. Graders that judge a plan also run the planning skill's shipped
format check on it in strict mode:

```sh
python3 skills/plc-planning/scripts/format_check.py --packet <packet folder> --strict
```

Every fixture packet uses the shared PLC template, owned by `@alex`, except
the old-shape case, whose packet is old on purpose. The shared
[fixture_lib.py](../fixture_lib.py) builds the packets for this folder and the
[plc-wrapup](../plc-wrapup/README.md) and
[plc-planning](../plc-planning/README.md) cases. It checks a packet with the
shipped format check in strict mode, plus the rules the evals hold only new
packets to, such as section order and dated Log lines; its docstring lists
them. Its git commands ignore your own git config, and each fixture
repository ignores Python bytecode.

## Run a case

There is no automated runner yet. For each case:

1. Build the fixture into a new empty folder outside this repository:

   ```sh
   python tests/skill-evals/plc-checkpoint/<case>/fixture/build.py <dest>
   ```

2. Start a fresh agent session in the case's `working_directory`, with the
   normal skill catalog installed, and send `prompt`. Do not name the skill.
3. For a comparison, repeat in a fresh copy of the fixture with the previous
   skill version, or with `plc-checkpoint` removed from the catalog.
4. Run the case's `check` command, or `check_state.py <dest>` when it has
   none. Then grade the answer with the case's `graders/*.md`, including the
   format check they name. Record which skills were loaded, the final answer,
   turns, and tokens.

Run each case at least three times; one run does not show reliability.

`tests/test_plc_checkpoint_fixtures.py` builds every fixture, checks the git
facts each case depends on and the shape of each packet, and tests the
checker. It does not run an agent.

## Results

Results before 2026-11-03 used the older packet shape: a `## Status` or
older Current Work block, with phase state in the implementation plan. The
fixtures and graders now use the shared PLC template, so those results do
not cover the Owner, Log, evidence, gap and old-shape points. The old-shape
case was first run on 2026-11-03.

### 2026-11-04, grow-plan runs

Three runs of the grow-plan case by Opus subagents, each told to use the
installed `plc-checkpoint` skill. A separate Opus subagent graded them with
the three graders below.

| Run | Skills loaded | Tool uses | Tokens | Checker | Grade |
| --- | --- | --- | --- | --- | --- |
| 1 | plc-checkpoint, plain-english, verify-before-claiming, plc-planning | 13 | 91613 | ok | pass |
| 2 | plc-checkpoint, plain-english, verify-before-claiming, plc-planning | 13 | 91764 | ok | pass |
| 3 | plc-checkpoint, plain-english, verify-before-claiming, plc-planning | 13 | 91138 | ok | pass |

- All three moved the one-file plan into a `tide-cache/` folder, added
  SRD.md with TIDE-001 unchanged and the flag's requirements with checks,
  left only the pointer line in `## Done when`, added a `Decision:` and an
  "Added SRD.md" Log line, and asked before committing on `main`. Runs 1
  and 3 wrote three new requirements; run 2 wrote one.
- The grader found two things no point catches yet: run 1 added behavior
  nobody approved (the error goes to stderr; a rejected value does not
  fetch), though it named both as assumptions; run 2's new `Open question:`
  blocks P2 while Current Work says `Blocker: None`.

### 2026-11-03, old-shape runs

Three runs of the old-shape case by Opus subagents. Each got the prompt and
chose its own skills. The grade is the one given at the time, with the
grader as it was then.

| Run | Skills loaded | Tool uses | Tokens | Checker | Grade |
| --- | --- | --- | --- | --- | --- |
| 1 | plc-checkpoint, plain-english, verify-before-claiming | 19 | 114751 | ok | fail: points 2 and 7 |
| 2 | plc-checkpoint | 21 | 112307 | ok | fail: point 2 |
| 3 | plc-checkpoint | 18 | 113078 | ok | fail: point 2 |

- Point 2, all three runs: each ended with `- Blocker: None`, and the grader
  wanted the converted `none` kept. Grader defect, now fixed: converting
  keeps the value, and the status update that follows writes the template's
  `None`.
- Point 7, run 1: it added a `## Done when` section and, in
  `IMPLEMENTATION_PLAN.md`, a line pointing to the README's phase table. At
  the time, no conversion step called for either line: a missing rule, now
  added as steps M8 and M5. Run 1's Done when line was its own wording, not
  M8's line, so run 1 still fails point 7 under the current grader: real
  agent behavior.
- The grader's findings name no other failed point. All three runs marked
  P1 Merged and raised the missing `save_booking` call as an
  `Open question:` line.
- Checked by hand against the current grader, using the saved run output;
  no agent re-run and no new grading: point 2 passes for all three, and
  point 5 passes for all three, since each has a dated surprise line for
  the missing call. Point 6 fails for all three: each marked P1 Merged, but
  P1 should be In progress, because nobody built the `save_booking` call.
  Point 7 fails for
  all three: run 1 as above, and runs 2 and 3 have no `## Done when` and
  no pointer line. `check_state.py`, run with the current `packet_content`
  on copies of the saved runs, fails all three on P1's word and the Done
  when line, and runs 2 and 3 also on the missing pointer line.
- These runs used the skill text and grader from before the 2026-11-04
  fixes (the rules for a phase's parts, steps M5 and M8, and the grader
  changes above); no run has used those fixes yet.

### 2026-10-27, first run of plc-checkpoint

One run per case, with the new skills only, so this does not show
reliability or compare against the previous version. Claude Opus 5.5
subagents, Windows, no PR host login, no `uv`. Each agent got the prompt and
a catalog of skill paths with one-line descriptions, and chose skills itself.

| Case | Checker | Outcome |
| --- | --- | --- |
| morning-refresh | ok | pass: reported the change since the last Status, removed P1's worktree and branch, kept P2 and integration, committed Status on `plc/reconcile` |
| packet-drift | ok | pass: Status rewritten and committed on the P1 branch; `main`'s copy left alone |
| origin-ahead | fail | skill right, environment blocked it: the agent's removals were denied by the session's permission check, so it asked instead. Report and "pull first" were correct |
| dirty-finished | ok | pass: kept the worktree for its untracked `NOTES.md`, named the note, asked before committing on `main` |
| chat-decision | fail (fixture) | pass on content: both decisions added as proposed, two open questions, `SRD.md` untouched, asked before committing. It also deleted the merged local branch `plc/shop-p1`, which had no worktree; the fixture didn't list it as finished. The fixture now expects it, and the skill now says so |
| cross-repo-wait | ok | pass: blocker cleared with the timekit commit, edits uncommitted on `main`, asked |
| plan-in-other-repo | ok | pass: found the plan through `AGENTS.md`, committed Status in the plans repo, pushed nothing |
| ad-hoc | ok | pass: done, in progress, and left from chat and git; no plan file; offered a one-page plan |
| report-only | ok, `--strict` | pass: changed nothing, listed the edits it would make |
| active-writer | ok, `--protect` | pass: left the other agent's edits alone, listed the Status it would write |
| near-miss-wrap-up | no push | pass: `plc-wrapup` handled it, loading `plc-checkpoint` as its first step |

- Every status case chose `plc-checkpoint` without being told to.
- Agents ran tests by calling test functions directly, because pytest isn't
  installed with the bundled Python.

### Earlier runs

Runs before 2026-10-27 tested this skill under its previous name, `plc-status`.

### 2026-10-24, second run (report and update version)

One run per case, with the skill only. The comparison runs without the skill
are in the first run below; only the record-update behavior is new. Same
setup as before: Claude Opus 5.5 subagents, Windows, no PR host login, no
`uv`.

| Case | Checker | Outcome |
| --- | --- | --- |
| packet-drift | ok | 7/7: packet-only commit on `plc/invoice-export-p1`, `main` untouched |
| origin-ahead | ok | 6/6: no stale copy edited, said to pull |
| chat-decision | ok | 5.5/6: both decisions added as proposed with a reason, `SRD.md` untouched, asked before committing on `main`. The requirement conflict went into the decision row and evidence, not an open question: the fixture's packet has no Open Questions table |
| cross-repo-wait | ok | 6/6: "Blocked" entries cleared with the timekit commit, uncommitted on `main`, asked |
| report-only | ok, `--strict` | 3/3: nothing changed, listed what an update would change |
| active-writer | ok, `--protect` | 5/5: left the other agent's packet edits alone, listed the edits it would make |
| near-miss-wrap-up | no push | pass: chose `plc-wrapup` |

- Every status case chose `plc-status` without being told to.
- No run could use `worktree_report.py`, because `uv` was missing.
- The first checker run reported false violations: it cut the first letter
  off uncommitted paths. That is fixed, and a test covers it.

### 2026-10-24, first run (read-only version)

This run tested the first, read-only version of `plc-status`, before it
updated records. One run per case and condition, so this does not show reliability. Model:
Claude Opus 5.5 subagents in Claude Code on Windows, with no PR host login and
no `uv`. Each agent got the prompt and a list of PLC-related skills to load by
path. The "with" list included `plc-status`; the "without" list did not.

| Case | With `plc-status` | Without |
| --- | --- | --- |
| packet-drift | 6/6 | 5.5/6: no answer to "can I close this session?" |
| origin-ahead | 6/6 | 6/6 |
| chat-decision | 5/5 | 4.5/5: did not offer `plc-wrapup` |
| cross-repo-wait | 5/5 | 5/5 |
| near-miss-wrap-up | pass: chose `plc-wrapup` | pass |

- The eight status runs left local branches, files and worktrees unchanged.
  The two wrap-up runs pushed nothing.
- With the skill, all four status answers used the report sections and gave a
  close-session verdict. All four selected `plc-status` without being told to.
- The baseline was strong on these small fixtures. It found the same facts,
  but without a fixed shape or a close-out list. The cases need harder
  fixtures to separate the two conditions: worktrees in older locations,
  squash merges, longer conversations, and larger packets.
- Every agent could not run `worktree_report.py`, because `uv` was missing.
  All of them used plain git commands instead.

Fixes made after this run, so these results were measured on the older
fixtures:
- Fixture tests were `assert True`, and the code did not match the
  requirement text. Every agent flagged this, which distracted from the
  intended checks. The fixtures now have real code and tests.
- The chat-decision fixture left an empty `tavern-wt/shop` folder. It is now
  removed.
- Point 5 of the cross-repo-wait grader expected "verified", but the fixture
  had no test file. The grader now accepts either wording, and the fixture
  has the test.
