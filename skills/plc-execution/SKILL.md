---
name: plc-execution
description: "Run selected Plan-Led Change (PLC) work with optional child agents and worktrees, regular audits during implementation, direct merges or merge requests, and questions for open decisions. Use only when the user calls $plc-execution."
---

# PLC Execution

## Use only when called

Use this skill only when the user explicitly calls `$plc-execution`.

Use it for the PLC work that the user names. That work can be:

- One entire PLC.
- One or more phases or sub-phases in one PLC.
- Related phases or sub-phases in several PLCs.

The user must name the PLC files and the phases to run. If the selection is not
clear, stop and ask. Use `plc-planning` to create or repair a PLC. This skill
can run discovery work inside an existing PLC.

## Choose the work and merge route

Before you create a worktree, make a work list. For every selected phase or
sub-phase, record:

- The PLC file and exact phase or sub-phase.
- Its prerequisites, including phases in other PLC files.
- Its design goals, files, behavior, tests, and audits.
- Whether it is ready, blocked, or a discovery task.

Run an item only after its prerequisites pass. A discovery task can run before
a prerequisite only when it does not change that prerequisite.

Choose one merge route before the children start. Use direct integration when
the user wants the parent to merge child branches into its chosen worktree.
Use merge-request integration when the user wants a review and CI for each
child branch. If the user does not name a route and the repository has no
clear convention, stop and ask.

Use the user-specified integration branch and worktree. If no target is named,
choose a clean target. Prefer a non-default integration branch and linked
worktree when the work needs isolation or child agents. Use `main`, another
default branch, or the primary worktree only when the user named it as the
clean merge target. Record the target branch and worktree before children
start. For merge-request integration, record each MR target branch. Ask the
user if the target branch is not clear.

## Set up the work

1. Read the root and scoped `AGENTS.md` files. Read every selected PLC, the
   source code, and the product and design documents for this work. Follow
   repository rules, such as CQ. Use named design goals as acceptance criteria.
   If the user names Roci design goals, find the documents that state them.
   Do not guess them.
2. Use the work list to order the selected phases. Use child agents only when
   a phase has independent implementation blocks. Keep small or tightly coupled
   work with one agent. Work in parallel only when tasks own different files and
   do not change the same API, schema, data format, or design choice.
3. Use the chosen clean target. Create an integration branch and linked
   worktree when the work needs isolation or child agents. Do not change a
   dirty worktree. Do not stash user work. Do not work in the source checkout
   unless the user chose it as a clean merge target.

If child agents use separate worktrees, do not assume that the agent tool made
them. Some tools reuse the caller's folder. The parent creates and checks each
child worktree before it starts the child.

```text
git worktree add -b <child-branch> <absolute-child-path> <integration-commit>
git -C <absolute-child-path> status --short --branch
```

When children use separate worktrees, give each one a different branch and
sibling folder. For example, use `ncurry/<plc>-p<phase>-<slice>`. Record the
base commit. Do not put a child worktree inside another worktree.

## Audit during implementation

Run `$audit-codebase` regularly during implementation, whether one agent or
several agents do the work. Run it after a meaningful block, often at a phase
boundary. A meaningful block changes code, configuration, tests, or user
behavior.

- Audit a child's meaningful block before it hands work to the parent.
- Audit the combined diff after a meaningful merge or at the phase boundary.
- If one agent does the work, audit after each meaningful block or phase.
- A discovery-only task or a tiny no-code edit can wait for the next meaningful
  block.

At every handoff or merge, read `git status --short` in the exact worktree.
Do not use another worktree's status. If several tiny related blocks do not
justify separate audits, audit them as one small group and record why.

## Allow discovery work

A discovery task can read source code, trace behavior, run tests, and make a
small reversible experiment in its own worktree. Its report must state the
facts found, tests run, options, and questions.

Do not merge an experiment that chooses an unanswered technical, architectural,
product, API, data, security, or design option. Stop and ask the user first.

## Give each child clear instructions

Every child assignment must state:

- The absolute worktree path, branch, and base commit.
- The PLC file, exact phase or sub-phase, acceptance criteria, and design
  goals.
- The prerequisites that must pass before the child starts.
- The chosen merge route. For an MR, state its target branch and who opens it.
- The files, APIs, and behavior the child owns. State what it must not change.
- Whether it can make a small fix outside its work to keep old code working.
  The default is no.
- The tests and audits to run. State what the final report must contain.

Tell the child to edit only its assigned worktree. It must not edit the
integration worktree, another child worktree, or `main`. It can commit its
branch. It cannot merge, rebase a shared branch, or delete a worktree. It can
push or open an MR only when its assignment uses merge-request integration.

Each child must:

1. Read the source, PLC, design goals, prerequisites, and local instructions
   before editing.
2. Change only its assigned files and behavior. Update the PLC or product
   documents if the change alters documented behavior or the record of results
   for that phase.
3. Run focused tests while working. Then run the project tests and checks that
   cover the change.
4. After a meaningful implementation block, run `$audit-codebase` against its
   branch diff from the supplied base commit. This is what "all audit skills"
   means. It runs every specialist audit named by that skill. A discovery-only
   task or a tiny no-code edit can wait for the next meaningful block.
5. Run extra audits that match the change. For UI work, run
   `frontend-design-review`. For a dependency change, run
   `dependency-auditor`.
6. Fix every finding that needs a change. Stop and ask if a finding needs a
   technical, architectural, product, API, schema, stored-data, security, or
   design choice.
7. After fixes, run the affected audits and tests again. Get the final audit
   result. Merge only when the result is `PASS`. `PASS WITH FOLLOW-UPS` is not
   enough when the user says to fix every finding.
8. Commit a clean branch. Report the commit hash, files changed, tests run,
   audit result, fixes made, and decisions that stopped work.

## Direct integration

For direct integration, only the parent merges child branches. Before each
merge, make sure that the child branch is clean and committed. Read its diff,
test results, and `PASS` audit result. Merge one child at a time. Run tests
after each merge. Run the required combined audit after a meaningful merge or
at the phase boundary. Audit a small group only when no single child changed
enough to warrant its own audit. Record that choice.

## Merge-request integration

For merge-request integration, follow the assignment to decide whether the
child or parent opens the MR. By default, the child opens an MR from its branch
to the recorded target branch. Its MR description names the PLC phase,
behavior, tests, audits, and known dependencies.

For each MR:

1. Use `$check-pr` to wait for review comments and CI results.
2. Fix actionable comments that fit the assigned work. Run affected tests and
   audits after each fix.
3. Ignore a comment only when it is informational, already fixed, outside the
   assigned work, or approved by the user. Give a short reason before you
   resolve it.
4. Do not resolve an actionable comment only to make the MR look clean.
5. Stop and ask when a comment needs a technical, architectural, product, API,
   data, security, or design decision.
6. Wait for all required CI checks to pass after the final update. The parent
   merges the MR only after the audit result is `PASS`, the CI is green, and
   no actionable review comment remains.

## Close a phase or group

After all child changes for one phase or dependency group are merged:

1. Run all tests and checks for the phase or group in the integration worktree.
2. Run `$audit-codebase` on the combined diff. For UI work, inspect the
   rendered UI against the stated design goals.
3. If the combined work shows a defect or audit finding, start a repair child.
   Base its worktree on the latest integration commit. Use the selected merge
   route. It must get a `PASS` result before its merge.
4. Update the PLC phase status and results only after the phase checks pass.
   Do not call the selected work done if later phases or a user decision remain.

Run the phase-close audit even if earlier handoff audits passed. After repairs,
run one final audit. If a blocking finding remains, stop and ask for direction.
Do not repeat a full audit without new work or new evidence.

Leave completed child branches and worktrees until the user asks to clean
them. This lets the user examine or recover the work. Some processes keep a
worktree folder open.

## Stop and ask

Stop and ask the user immediately if:

- You cannot tell what to do next.
- The PLC, source code, or design documents disagree.
- The PLC, source code, or design documents do not define important behavior.
- A dependency between selected PLC phases is missing or unclear.
- The next step changes a public API, stored data, or schema beyond the PLC.
- The next step changes a data format, migration, security model, or design
  goal beyond the PLC.
- An audit fix goes outside assigned work or creates a real tradeoff.
- A review comment needs a technical, architectural, product, API, data,
  security, or design decision.
- A required test or check cannot run, and the parent cannot safely fix the
  problem.

Do not ask about a small local coding choice that the PLC and source already
answer. Report the facts, options, and question. Write the user's answer in
the PLC if it changes the plan or the tests that must pass.

## Write plainly

Write every assignment, phase note, question, and report in plain English. Use
the product's existing names and concrete facts. Prefer short sentences. State
what changed, why, and which tests passed. Do not make up broad labels. Do not
use vague words such as "holistic," "seamless," or "robust." Name the exact
file, behavior, test, or design goal instead. `$audit-codebase` includes
`plain-language-audit`.

## Finish

List the selected PLC files, phase order, dependencies, and parallel groups.
State the merge route, every child branch and commit, every MR, each audit and
test result, whether each design goal passed, and every open question. Merge
the final target branch only when the user authorized it and all required
tests, audits, reviews, and CI checks passed.
