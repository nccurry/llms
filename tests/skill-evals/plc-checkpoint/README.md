# plc-checkpoint eval cases

Eleven runnable cases for [`plc-checkpoint`](../../../skills/plc-checkpoint/SKILL.md),
modeled on the case shape in trailofbits/skills: each case folder has a
`case.yaml`, a `fixture/build.py` that creates its git repositories, and
Markdown graders. They live here, not in the skill folder, because the
installer copies the whole skill folder into each agent.

| Case | What it checks |
| --- | --- |
| [morning-refresh](morning-refresh/case.yaml) | Yesterday's Status is stale; P1 merged into integration since. Report the change, tidy P1, rewrite Status |
| [packet-drift](packet-drift/case.yaml) | `main`'s packet says pending; the worktree's copy and commits show P1 implemented |
| [origin-ahead](origin-ahead/case.yaml) | P1 merged on `origin/main`; local `main` is behind. Tidy the merged worktree and branches |
| [dirty-finished](dirty-finished/case.yaml) | P1 merged, but its worktree has untracked notes: keep it |
| [chat-decision](chat-decision/case.yaml) | Two scope calls made in the conversation are missing from the packet |
| [cross-repo-wait](cross-repo-wait/case.yaml) | The plan waits on another repo whose `origin/main` already has the work |
| [plan-in-other-repo](plan-in-other-repo/case.yaml) | The plan lives in a separate plans repo: commit Status there, push nothing |
| [ad-hoc](ad-hoc/case.yaml) | No plan: report from the conversation and git, create nothing |
| [report-only](report-only/case.yaml) | "Just tell me, don't change anything" must change nothing |
| [active-writer](active-writer/case.yaml) | Another agent's uncommitted packet edits must be left alone |
| [near-miss-wrap-up](near-miss-wrap-up/case.yaml) | "Wrap this up" must go to `wrap-this-up` |

`check_state.py` compares a fixture with the `_snapshot.json` and
`_expect.json` its build script wrote:
- **Required:** removing each finished worktree, local branch, and remote
  branch listed in `_expect.json`.
- **Allowed:** plan record edits under `docs/plans/`, and commits that touch
  only those files.
- **Violations:** removing anything else, pushes, merges, new branches or
  worktrees, code edits, and any change to `SRD.md`.

It prints JSON and exits 1 on a violation. The outcome graders then judge the
report and the plan edits. `fixture_lib.py` is shared with the
[wrap-this-up cases](../wrap-this-up/README.md).

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
   none. Then grade the answer with the case's `graders/*.md`. Record which
   skills were loaded, the final answer, turns, and tokens.

Run each case at least three times; one run does not show reliability.
Follow the general rules in [skill-evals.md](../../skill-evals.md).

`tests/test_plc_checkpoint_fixtures.py` builds every fixture, checks the git
facts each case depends on, and tests the checker. It does not run an agent.

## Results

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
| near-miss-wrap-up | no push | pass: `wrap-this-up` handled it, loading `plc-checkpoint` as its first step |

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
| near-miss-wrap-up | no push | pass: chose `wrap-this-up` |

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
| chat-decision | 5/5 | 4.5/5: did not offer `wrap-this-up` |
| cross-repo-wait | 5/5 | 5/5 |
| near-miss-wrap-up | pass: chose `wrap-this-up` | pass |

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
