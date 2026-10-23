---
name: create-mr-description
description: "Creates and updates merge request and pull request descriptions from the current diff and validation evidence. Use when opening an MR/PR or refreshing its description after implementation, review, validation, rebase, or target changes."
---

# Create MR Description

Explain the current change to a reviewer who has not read the conversation.
Support GitLab MRs, GitHub PRs, and equivalent reviews. Drafting a description
does not authorize creating a review, pushing code, or merging it. An authorized
create/update workflow includes maintaining its description; respect draft-only
and read-only requests.

## Gather the current facts

Read repository instructions, its description template, the existing description,
the task or plan, and relevant validation results. Use the current diff and enough
surrounding source to establish behavior; commit messages and bot summaries are
hints, not proof. Fetch all pages and check for truncated or omitted diffs.

Identify the host, source revision, target, and comparison base. For a stack,
distinguish the full target diff from this MR's own changes. State the prerequisite
and review range; use that range consistently for the summary and counts, and
label counts that differ from the host's full diff. Do not silently change the
MR target or count unrelated working-tree edits. A draft for unpublished changes
must say which local revision or working tree it describes.

## Write for the reviewer

Use plain English, short sentences, and concrete names. Follow the repository
template; otherwise use the compact example below as a starting point. Usually
150–300 words of prose is enough, excluding snippets and tables. Scale to the
change, omit empty sections, and keep necessary migration guidance visible.

- **What and why:** Start with the problem and resulting behavior. Summarize
  important changes by purpose. Explain compatibility breaks, changed defaults,
  and required migration early. Distinguish usable features from preparatory work
  that remains disabled or needs another MR.
- **Show the change:** Choose one or two small examples that explain the effect.
  Use actual configuration, CLI input/output, code, documentation, API shapes,
  or an inspected screenshot. A metric change may need an old/new name-and-unit
  table; deployment changes may need a path/precedence table; a refactor may need
  a small old/new module layout. Show the consequence, not a dump of the diff.
  Verify names and syntax. Label illustrative or expected output when unobserved.
- **Change breakdown:** Count added and deleted lines for the stated range using
  Git numstat with rename detection or complete host diff statistics. Make the
  kind of change explicit in every row: production code, test code/fixtures,
  comments/docstrings only, user documentation, planning/evidence, developer
  tooling, build/CI, deployment/config, or generated files/lockfiles. Feature or
  module grouping is fine; use a separate `Kind` column or labels such as
  `Production code — config reload` and `Test code — config reload`. A feature
  name or path alone does not explain what kind of change the count represents.
  Use only populated groups and enough detail to identify the affected code or
  documents without turning the table into a per-file inventory.
  Inspect the changed content, not just file extensions or directories: a source
  file can contain only comment edits, and a test plan is documentation rather
  than test code. Separate comment-only edits from production/test code when
  practical; comments accompanying a code change can stay with that code.
  Split mixed groups such as runtime code and docs, or Helm logic and value
  comments, when the diff supports it. For inseparable mixed files or hunks,
  state the kinds included (for example, `Mixed: production code + inline tests`)
  and that counts cover both; do not guess a precise split or count lines twice.
  Include file counts when useful. Note substantial moves, and list binary files
  separately. Reconcile category totals with the diff; disclose incomplete counts.
  Counts describe review scope, not complexity or quality.
- **Validation:** Give commands actually run, results, and the behavior they
  establish. Separate regression/feature tests from lint and build checks.
  Identify the tested source and relevant environment: hardware, architecture,
  driver/library versions, mocks, injection, or deployment method. Keep failures,
  skips, retries, pending checks, and material untested paths visible. A passing
  test on a modified copy or earlier revision is evidence for that source only;
  explain any supported reuse. Never infer executed tests from test source alone.
  For performance claims, include baseline, workload, method, and measured result.
- **Related work:** Link issues, relevant plan requirements, prerequisites, and
  follow-ups with their relationship. Explain what this MR delivers and what
  remains elsewhere. Avoid unexplained phase IDs and internal process language.

Keep the description about the final implementation. Link exact evidence records
and CI results for detailed logs, hashes, audit history, and delivery receipts.
Do not replace useful explanation with links or append a development diary.
Description work uses existing evidence; missing evidence is reported, not an
instruction to launch hardware tests, audits, or a new qualification campaign.

## Keep it current and publish

Refresh when creating the review, after publishing changes that affect its
description, after a rebase or target change, when validation changes materially,
and before final merge readiness. Reconcile the whole description so old claims,
examples, counts, dependencies, and test results do not contradict new ones.
Skip writes when nothing needs changing. These are workflow checkpoints, not a
background monitor.

Before writing, fetch the existing description again. Preserve human notes,
required checklists, issue references, and bot-owned sections. Revise outdated
summary text while retaining meaningful rationale. If a bot section contradicts
the diff, flag the disagreement without rewriting its owned block. Incorporate
concurrent edits; do not overwrite a description fetched before someone changed it.

Use the host's available tools with structured arguments or a body file. Pass
Markdown as data, never shell-evaluated text. Read back the saved description and
verify the intended content and preserved sections. If a write's outcome is
unknown, inspect before retrying. If publication is unavailable or outside scope,
provide the finished draft and state that it has not been published.

Before finishing, check that the description matches the selected diff, examples
and counts are accurate, validation claims have evidence, and material limitations
remain visible. Report the review link and update result, or provide the draft.

## Compact example

Illustrative only; the commands, results, and counts below are not real evidence.

````markdown
Invalid configuration could leave a reload partly applied. Reload now validates
the replacement first and keeps the active configuration when validation fails.

### Example

```console
$ app reload --config invalid.yaml
Error: timeout must be greater than zero; active configuration unchanged.
```

### Change breakdown

| Area | Kind | Added | Deleted |
| --- | --- | ---: | ---: |
| Config reload validation | Production code | 64 | 21 |
| Invalid reload and active-config preservation | Test code | 98 | 8 |
| Reload API docstrings | Comments/docstrings only | 4 | 2 |
| Reload usage guide | User documentation | 18 | 3 |
| **Total** | | **184** | **34** |

### Validation

- `pytest tests/test_reload.py` — 12 passed on source `abc1234`, Linux CPU;
  covers valid reloads, invalid input, and preservation of the active config.
- CI: pending. Live deployment: not tested.

### Related work

Builds on !120's parser. File watching remains in !124.
````
