# Setup Tooling Implementation Plan

Phase state lives in the README's [Phases](README.md#phases) table. This file
holds what each phase changes, how it is checked, and its evidence. It has no
state table of its own.

## Selected Delivery

All of REQ-001 to REQ-020 and REQ-022, delivered to `main` as one direct
commit series per phase. The order puts the cheap, independent checks first (P1, P2),
then the safety net (P3), then the restructure (P4, P5), so the restructure's
diff is not mixed with formatting and is guarded by the golden test.

P1 goes first: its formatting commit touches the files P2 and P3 change.
P2 and P3 each need P1 merged and are independent of each other. P4 needs P3
merged. P5 needs P4.

Hosted Windows CI is not selected (the owner chose not now).

## Phase Details

### P1: Separate lint and type checks for Python outside piw

- Requirements: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006
- Change: Add `ruff.toml` and `.git-blame-ignore-revs` at the root and a
  `lint/` folder with the pyright configuration and hash-pinned requirements;
  add `deps:dev-tools` and `lint:python`, and run `lint:python` from `check`
  and `ci`; reformat; fix or narrowly suppress the remaining findings; update
  the README's development table.
- Out of scope: C901 and pyright strict (both enabled in P5); any `piw/` file.
- Prerequisite: None.
- Steps:
  1. Write `ruff.toml`: line length 100, target Python 3.14, piw's rule
     families minus D100 to D107, `extend-exclude` for `piw/` and
     `tests/skill-evals/**/fixture/`, test per-file ignores as in piw.
  2. Write `lint/pyrightconfig.json` (paths resolve from `lint/`): basic
     mode, Python 3.14, include `../scripts`, `../tests`, `../skills`; exclude `piw`, eval fixtures and
     `scripts/render_serena_config.py`; an execution environment for
     `tests/skill-evals` with its harness folder in `extraPaths`.
  3. Pin ruff 0.16.2, pyright 1.1.411 (piw's current versions) and `tomlkit`
     (as in `agent-runtime.txt`) with hashes in `lint/requirements.txt` via
     `uv pip compile --generate-hashes`.
  4. Add `deps:dev-tools` (installs `.tools/lint/` with
     `uv pip install --require-hashes`) and `lint:python`; call `lint:python`
     from `check` and `ci`.
  5. Commit the configuration and record the baseline counts. Then commit
     the result of `ruff format` alone, and add that commit to
     `.git-blame-ignore-revs`.
  6. Apply safe auto-fixes, then fix the rest by hand. Use a per-file ignore
     or a suppression in the REQ-006 form only where the code is right as is.
- Validation: `./bootstrap.sh lint:python` → exit 0, and fails with one
  hash changed; `ruff check --show-settings` and `--show-files` as in
  REQ-001; `git diff 284290e -- piw/` → empty; `./bootstrap.sh piw:check` →
  pass; `cd piw && uv run --locked pyright --verbose` names
  `piw/pyproject.toml`; FIX-009 known failure through `check` and `ci`;
  REQ-005 reformat reproduction; `./bootstrap.sh test` → unchanged pass
  counts.
- Exit criterion: every P1 requirement's check passes on `main`.
- Rollback or fallback: revert the phase's commits; the formatting commit
  reverts cleanly on its own.
- Evidence:
  - Targets: ruff `target-version = "py311"` and pyright `pythonVersion = "3.11"`, with
    py310 overrides for the two skill scripts that declare it. `git grep -n -E
    '^\s*except [A-Za-z_.]+, ' -- '*.py' ':!piw'` finds nothing.
  - Baseline on the configuration commit 373f17a: ruff check 200 findings (the first draft of the
    config, before per-file ignores, gave 528), ruff format would change 25 of 164 files,
    pyright basic 78 errors in the first run at Python 3.14. Final: ruff check,
    ruff format --check and pyright all report 0.
  - Formatting commit 090d7e29ca40591faf55f171a8d71790ecbb83c8; `.git-blame-ignore-revs` lists it.
    Running the pinned ruff 0.16.2 `format` on its parent gives tree 05b70841, equal to the
    commit's tree.
  - `./bootstrap.sh lint:python`, `./bootstrap.sh piw:check`, `./bootstrap.sh test` and
    `./bootstrap.sh check` exit 0; piw 185 passed, setup-script tests 26 OK, launcher tests 3 pass.
  - With an unused import added to `scripts/install_skills.py`, `./bootstrap.sh check` and
    `./bootstrap.sh ci` each exit 201 and print F401 for that file (run on the earlier history;
    the task wiring is unchanged).
  - Changing every hash of one package in `lint/requirements.txt` makes `deps:dev-tools`
    fail with a hash mismatch. `deps:dev-tools` is not part of `deps:install`.

### P2: Windows checks from Linux

- Requirements: REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-012,
  REQ-013
- Change: Pin shellcheck and PowerShell in a separate mise environment under
  `lint/`, installed by `deps:dev-tools`; add a pinned, checksum-verified
  download of Pester and PSScriptAnalyzer into `.tools/powershell-modules/`;
  add `lint:shell`, `lint:powershell` and `test:powershell`, all run by
  `check` and `ci`; turn `bootstrap.ps1`'s checksum
  lookup and `task.cmd` text into functions behind a dot-source guard; write
  `task.cmd` with CRLF and compare ignoring line endings; escape every
  PowerShell single-quote character in both quoting sites; add Python
  Windows-branch tests; document the Windows-only checks.
- Out of scope: running on Windows; hosted CI; PowerShell 7-only syntax in
  `bootstrap.ps1`.
- Prerequisite: P1 merged. A separate mise environment can install and lock
  shellcheck and PowerShell (both lock for all six platforms, checked
  2026-11-06), and the two module packages download by exact version with
  stable SHA-256 checksums. Confirm at the start of the phase.
- Steps:
  1. Prove each checker detects a known failure before relying on it:
     FIX-008 for PSScriptAnalyzer's 5.1 syntax and command rules; an
     unquoted variable for shellcheck; a failing Pester assertion.
  2. Pin the tools and modules; add the three tasks.
  3. Refactor `bootstrap.ps1` into functions with a dot-source guard
     (`if ($MyInvocation.InvocationName -ne '.') { <main> }`); add Pester
     tests that mock the main function.
  4. Fix the `task.cmd` line endings and comparison.
  5. Fix single-quote escaping in `run_gitnexus_hook.mjs` and
     `gitnexus_hook_launch`; add Python and Node tests with FIX-007.
  6. Add Python tests for the Codex hook command, `commandWindows` and the
     Windows permission command on `os.name == "nt"`.
  7. Add the Windows section to `docs/setup.md`.
- Validation: `./bootstrap.sh lint:shell`, `lint:powershell`,
  `test:powershell`, `test:tooling`, `test:agent-launchers` → all pass;
  known-failure runs from step 1 recorded; `pwsh -NoProfile -File bootstrap.ps1`
  is not run (it downloads).
- Exit criterion: every P2 requirement's check passes on `main`.
- Rollback or fallback: revert; generated `task.cmd` files are rewritten on
  the next bootstrap.
- Evidence:

### P3: End-to-end configure test

- Requirements: REQ-014, REQ-015
- Change: Add the fixtures FIX-001 to FIX-006 under `tests/fixtures/configure/`
  and a test class that runs `configure("all")` twice against them with faked
  upstream installers and compares every file with its golden copy.
- Out of scope: any change to `scripts/` other than test seams that do not
  change behavior.
- Prerequisite: P1 merged.
- Steps:
  1. Write the seeded home (FIX-001 to FIX-004) with invented names and paths.
  2. Write the fake executables (FIX-005) from the behavior observed in the
     real installers and version probes.
  3. Point the code at the fake home and `TOOLS` folder, and fix `PATH`,
     `LLMS_ORIGINAL_PATH`, `SERENA_HOME` and the temp root through the
     environment, so backups never reach the real checkout and no internal
     function is patched.
  4. Generate golden files from the current code with machine paths replaced
     by placeholders, read them line by line against what the real setup
     writes on this machine, and commit them.
- Validation: `./bootstrap.sh test:tooling` → pass; deliberately break one
  merge (for example drop a user key in `merge_json`) and confirm the test
  fails, then restore.
- Exit criterion: REQ-014 and REQ-015 pass on `main` with no change to
  setup behavior.
- Rollback or fallback: revert; tests only.
- Evidence:

### P4: Host adapters and a split configure

- Requirements: REQ-016, REQ-017, REQ-018 (for `configure`), REQ-020
- Change: Introduce one adapter per host and route `configure`, `preview`,
  `host_problems`, `require_standard_profiles` and `existing_server` through
  it; split `configure()` into named steps with one shared
  snapshot-and-restore helper for upstream installers.
- Out of scope: tool installation (P5); `install_skills.py`.
- Prerequisite: P3 merged and passing; the pre-change dry-run JSON saved
  outside the repo (REQ-020).
- Steps:
  1. From the main checkout, before any reconfigure, save the REQ-020 preview
     JSON outside the repo.
  2. Add the adapter type and the four adapters.
  3. Move each host branch into its adapter one function at a time, running
     the golden test after each move.
  4. Split `configure()`; keep the order of writes.
  5. Add the fake-host test.
- Validation: golden test unchanged; `git grep` check from REQ-017; fake-host
  test; dry-run comparison; `./bootstrap.sh doctor` → healthy;
  `./bootstrap.sh check` → pass.
- Exit criterion: P4's requirements pass on `main`.
- Rollback or fallback: revert the phase; the golden test proves the old code
  is still correct.
- Evidence:

### P5: Tools described by the manifest

- Requirements: REQ-016, REQ-018, REQ-019, REQ-020, REQ-022
- Change: Add `installer` and `bin` to each tool entry; add the three
  installer handlers; derive install, commands, versions, latest versions,
  the npm package and `--tool` choices from the manifest; remove the
  Taskfile's `TOOL` enum and let the script report unknown names; enable
  C901 at 10 and pyright strict for `manage_agent_tools.py` (and any split
  package) and bring it under both.
- Out of scope: new tools.
- Prerequisite: P4 merged.
- Steps:
  1. Add the fields to `agent-dependencies.json` and validate them on load.
  2. Add the handlers and replace each hard-coded tool name.
  3. Add the fifth-tool and bad-installer tests.
  4. Enable C901 for `manage_agent_tools.py` (and any package split out of
     it) and bring its functions under the limit.
  5. Switch those files to pyright strict and fix what it reports (REQ-022).
  6. Rerun `tools:install`, `agents:configure` and `doctor` on this machine.
- Validation: golden test unchanged; REQ-019 tests; `./bootstrap.sh
  lint:python` with C901 → exit 0; preview comparison against the output
  saved before P4, run before step 6's reconfigure; `./bootstrap.sh check` →
  pass; strict pyright on the setup script as in REQ-022.
- Exit criterion: P5's requirements pass on `main`, and every requirement in
  SRD.md has current evidence.
- Rollback or fallback: revert the phase; the manifest fields are ignored by
  the P4 code.
- Evidence:

## Review And Recheck Rules

- Required review domains for each phase: correctness and reliability, code
  quality, test quality, and file hygiene; security for P2 (downloads and
  quoting) and P5 (manifest-driven commands); docs-sync for P1, P2 and P5.
  Fix every supported in-scope finding, including P3-severity ones.
- A change to setup code invalidates the golden test, dry-run comparison and
  `doctor` evidence; a change only to lint configuration invalidates only
  `lint:python` evidence.
- A new commit hash alone does not invalidate unchanged evidence.

## Readiness And Completion

Before starting:

- [ ] Every selected Must requirement has a phase, proving check, and exit criterion.
- [ ] P2's prerequisite is checked at its start; P4 waits on P3.
- [ ] Documentation changes are listed in P1, P2 and P5.

Before closing selected work:

- [ ] Every requirement has current acceptance evidence.
- [ ] Required reviews have no supported actionable in-scope findings remaining.
- [ ] Delivery to `main` is verified and no checkout is left behind.
- [ ] Current Work and the Log agree with the code.
