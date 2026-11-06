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
  1. Write `ruff.toml`: line length 100, target Python 3.11 (3.10 for the two
     skill scripts that declare it), piw's rule
     families minus D100 to D107, `extend-exclude` for `piw/` and
     `tests/skill-evals/**/fixture/`, test per-file ignores as in piw.
  2. Write `lint/pyrightconfig.json` (paths resolve from `lint/`): basic
     mode, Python 3.11 (3.10 for those two skill scripts), include `../scripts`, `../tests`, `../skills`; exclude `piw`, eval fixtures and
     `scripts/render_serena_config.py`; an execution environment for
     `tests/skill-evals` with its harness folder in `extraPaths`.
  3. Pin ruff 0.16.2, pyright 1.1.411 with its `nodejs` extra (piw's current
     versions; Node then comes from a hash-pinned wheel) and `tomlkit`
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
- Evidence (code commit 1ea0b4bb947d86489cd3a14f610e61592a6c0df9 unless another commit is named):
  - Targets: ruff `target-version = "py311"` and pyright `pythonVersion = "3.11"`, with
    py310 overrides in both tools for the two skill scripts that declare it. `git grep -n -E
    '^\s*except [A-Za-z_.]+, ' -- '*.py' ':!piw'` finds nothing.
  - Baseline on the configuration commit 373f17a: ruff check 200 findings (a first draft of the
    config gave 528), `ruff format --check` says 25 of 27 files would change, pyright basic 67
    errors (78 with a draft config that could not see tomlkit). Final: ruff check,
    ruff format --check and pyright (`--warnings`) all report 0.
  - REQ-001: `ruff check --show-settings` names `ruff.toml` for `scripts/manage_agent_tools.py`
    and `piw/pyproject.toml` for `piw/src/piw/cli.py`; `ruff check --show-files` equals
    `git ls-files '*.py' ':!piw' ':!tests/skill-evals/**/fixture/**'` (27 files).
  - REQ-002: `git diff 6968fd2 -- piw/` is empty; `./bootstrap.sh piw:check` exits 0 (185 passed);
    `cd piw && uv run --locked pyright --verbose` prints "Loading pyproject.toml file at
    …/piw/pyproject.toml".
  - REQ-003: `./bootstrap.sh deps:dev-tools` then `./bootstrap.sh lint:python` exit 0 and print
    ruff 0.16.2 and pyright 1.1.411. With every hash of `typing-extensions` changed (uv accepts
    any listed hash, so one changed hash of several is not enough), `deps:dev-tools` fails with
    "Hash mismatch for `typing-extensions==4.16.0`" and `lint:python` then refuses to run.
  - Node and pyright come from the hash pins: `pyright[nodejs]` adds `nodejs-wheel-binaries`,
    and `lint:python` clears the wrapper variables that would download another pyright or Node.
    With `PATH=/usr/bin:/bin`, a temporary `HOME`, `PYRIGHT_PYTHON_FORCE_VERSION=latest` and
    `PYRIGHT_PYTHON_USE_BUNDLED_PYRIGHT=0`, `./bootstrap.sh lint:python` exits 0 and the temporary
    HOME stays empty (checked at 1ea0b4b; debug output showed "Using nodejs_wheel package").
  - REQ-004: in a detached scratch worktree at 1ea0b4b with `import colorsys` added to
    `scripts/install_skills.py`, after its own `deps:dev-tools`, `./bootstrap.sh check` and
    `./bootstrap.sh ci` each exit 201 and print "F401 [*] `colorsys` imported but unused" at
    `scripts/install_skills.py:13:8`. The worktree was removed afterwards.
  - REQ-005: formatting commit 090d7e29ca40591faf55f171a8d71790ecbb83c8, listed in
    `.git-blame-ignore-revs`. The pinned ruff 0.16.2 `format` run on its parent 373f17a gives
    tree 05b70841291f132044521c670306101e4f14dd83, equal to the commit's tree.
  - REQ-006: every `noqa` in scope matches `# noqa: <CODE> - <reason>`; there is no
    `pyright: ignore`, `type: ignore` or `ruff: noqa` (checked at 1ea0b4b).
  - At 1ea0b4b: `./bootstrap.sh test` exits 0 (piw 185 passed, setup-script tests 26 OK, launcher
    tests 3 pass); `./bootstrap.sh check` exits 0.

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
- Evidence (code commits 9ceb757 and d0c60a9, base 1164802):
  - Test: `tests/test_configure_end_to_end.py`; fixtures in `tests/fixtures/configure/`: `seed/`
    (FIX-001 to FIX-004), `golden/` (FIX-006, ten files), `scenarios/<name>/{seed,golden}`,
    `fake_upstream_tools.py` and `fake_gitnexus_cli.js` (FIX-005). It copies `scripts/` and
    `agent-dependencies.json` into a temporary repository (path of only `[A-Za-z0-9_./-]`) and runs
    `manage_agent_tools.py --command configure --target all` (twice for the main run) and
    `--command doctor --output json` as subprocesses. No function of the script is imported or
    patched. The fake GitNexus edits an existing `opencode.json`, `opencode.jsonc` or `config.json`
    in place with jsonc-parser; only the fake cq creates a server-only `opencode.json`.
  - Real dependency: the pinned Node and `jsonc-parser` from `.tools/agent-tools`. Missing → the
    tests skip; with `LLMS_REQUIRE_PINNED_TOOLS` set they fail. `check` and `ci` now pass
    `REQUIRE_PINNED_TOOLS=1` as a Task variable down to `skills:test` and `test:agent-launchers`
    (a task's `env` does not reach called tasks on Task 3.54.0); `test` and `test:tooling` still skip.
  - REQ-014, REQ-015: `./bootstrap.sh test:tooling` → 48 tests OK, no skips (26 before, 22 new).
    The main run checks the ten golden files, exact modes (0600 for setup's own private files,
    0644 for `hooks.json` and seeded 0644 files and the fake-made AGENTS.md), same bytes and mode
    after the second run, user content kept, the removed server-only `opencode.json` (a backup of
    it proves the fake made it), doctor problems for every host before configure and none after,
    and that every fixture is tracked by git.
  - Scenarios (REQ-016 cover): `CODEX_HOME` elsewhere and a different Serena home (exit 1, message,
    nothing written); Claude cq plugin with an old manual cq entry (golden, dropped key reported,
    doctor clean) and with a foreign entry (conflict error); OpenCode 2.x (`mcp.servers` golden);
    no Claude CLI; failing `serena setup` ("not found or not functional"; golden); a user-owned
    `opencode.json` kept.
  - Fresh clone: `git clone -b plc/sth-p3-e2e` into the campaign `_output/p3-clone`, linking only
    the toolchain into `.tools`: `./bootstrap.sh test:tooling REQUIRE_PINNED_TOOLS=1` → 48 tests
    OK with the golden Serena file present (it had been hidden by `.gitignore` line `.serena/`;
    now `!tests/fixtures/configure/golden/.serena/`).
  - Pinned tools hidden (same clone, no `.tools/agent-tools`): `./bootstrap.sh test:tooling` and
    `./bootstrap.sh test` → OK (skipped=9) and launcher "skipped 1"; `./bootstrap.sh check` exits
    201 with "AssertionError: Node and the pinned jsonc-parser are missing"; `test:agent-launchers
    REQUIRE_PINNED_TOOLS=1` → fail 1, without the variable → skipped 1.
  - Known-fault controls, each in `scripts/manage_agent_tools.py`, each restored with `git checkout`
    (suite fails, then passes): `merge_json` drops `userID` → golden `.claude.json`, user-content
    and three scenario goldens fail; `restore_servers` writes JSONC with `json.dumps` → golden
    `.jsonc`, comment-keeping and OpenCode 2 tests fail; `private_permissions` makes files 0644 →
    `.serena/serena_config.yml` mode test fails; `configure_pi` always appends the prefix →
    `test_second_run_keeps_every_file_unchanged` fails on `.pi/agent/settings.json`.
  - `./bootstrap.sh test`, `./bootstrap.sh lint:python` exit 0; `git diff 1164802 -- scripts/ piw/`
    is empty; the owner's real `~/.claude.json`, `~/.claude/settings.json`, `~/.codex/config.toml`
    and `~/.codex/hooks.json` kept their mtimes.
  - Seen, not changed: an OpenCode 2 migration drops comments inside the legacy `mcp` block, so
    the main seed's comment inside `mcp` is kept only because OpenCode 1.x is faked there; the
    `opencode_2` golden shows the loss.

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
- Evidence (code commit 12421df, base ae975e8):
  - Design: `HostAdapter` and `StandardProfile` (typed named tuples; frozen dataclasses fail when a
    test loads the script without registering it in `sys.modules`) in
    `scripts/manage_agent_tools.py`. One adapter each for codex, claude, pi and opencode, listed in
    `ADAPTERS` (the host list; `--target` choices and `selected_hosts` derive from it).
    `configure`, `preview`, `host_problems`, `require_standard_profiles`, `existing_server`,
    `host_servers`, the hook helpers and `skill_health` read host details from the adapter.
  - `configure()` is 14 lines (was 159): `require_standard_profiles`, `require_pinned_tools`,
    `serena_configuration`, then `configure_host` per host, which runs `back_up_host_files`,
    the adapter's environment step, `register_serena`, `back_up_server_files`, `set_up_gitnexus`,
    `run_cq_install` (both through `run_with_server_restore`), `configure_serena_hooks` and
    `write_managed_config`. Order of writes and upstream calls is unchanged. File length 1619 → 1859.
  - REQ-016: `git diff ae975e8 -- tests/test_configure_end_to_end.py tests/fixtures/configure/` →
    empty; `./bootstrap.sh test:tooling REQUIRE_PINNED_TOOLS=1` → 54 tests OK (48 + 6 new).
  - REQ-017: `tests/test_host_adapters.py` registers a fake adapter (own file, own section and
    env key) in `ADAPTERS` and runs `preview`, `configure`, `host_problems`, `existing_server` and
    `require_standard_profiles` on it with no other code change. It imports the script, because the
    black-box test cannot add a host. `git grep -n -E '"(claude|codex|opencode|pi)"' -- scripts/`
    → hits only in the four adapter definitions in `manage_agent_tools.py` and in
    `scripts/install_skills.py` (out of scope for P4).
  - REQ-020: preview and doctor output (text and JSON) from this checkout are byte-identical
    between the old script (`ae975e8`) and the new one. Against the saved baseline the only
    difference is `serena_hooks` for codex and claude, because the hook command holds the
    checkout's own `.tools` path and the user's hook files name the main checkout's.

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
