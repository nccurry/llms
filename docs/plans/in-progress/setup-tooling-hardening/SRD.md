# Setup Tooling Requirements

## Purpose

The setup scripts that write every agent's configuration are tested but not
linted, formatted or type-checked; their Windows path has never run; and
`scripts/manage_agent_tools.py` spreads each host's and each tool's details
across many functions, so a change to one host or the addition of one tool
needs several edits that must agree. This work adds the missing checks, proves
as much of the Windows path as a Linux host can, and restructures the setup
script without changing what it writes.

## Scope

- In scope:
  - A lint, format and type-check configuration for tracked Python outside
    `piw/`, separate from piw's, with a Task that `check` runs.
  - Checks for `bootstrap.sh`, the PowerShell scripts, and the Windows-only
    branches of the Python setup code, all run on Linux.
  - An end-to-end test of `configure`, then a per-host adapter, a split
    `configure()`, and a tool list driven by `agent-dependencies.json`.
- Out of scope:
  - Any change under `piw/`, including its ruff and pyright settings.
  - Running anything on a real Windows host or adding hosted CI (deferred; see
    [SADD Deferred Work](SADD.md#deferred-work)).
  - Restructuring `scripts/install_skills.py`, and sharing its host list or
    skill checks with `manage_agent_tools.py`.
  - Linting JavaScript (`scripts/*.mjs`, `tests/*.mjs`).
  - Python inside eval fixture projects (`tests/skill-evals/**/fixture/`),
    which are sample repositories the evals operate on.
- Constraints:
  - Setup must keep writing the same files and content for every host;
    restructuring is not a behavior change.
  - New tools are pinned by exact version, with checksums where the source
    provides no lock.

## Current System And Prerequisites

Inspected at `284290e` on 2026-11-06.

- `piw/pyproject.toml` scopes ruff (rules B, D, E, F, I, PERF, PL, RUF, S,
  SIM, TRY, UP; line length 100; Python 3.14) and pyright strict to piw's own
  files. Its lock pins ruff 0.16.2 and pyright 1.1.411. Nothing lints
  `scripts/`, the root `tests/`, or `skills/*/scripts/`.
- Measured with ruff 0.16.2, piw's rules plus C90, no fixes: 166 findings in
  `scripts/` and `tests/test_agent_setup.py`, `tests/test_install_skills.py`,
  `tests/test_fake_host.py` (80 missing function docstrings, 16 over the
  complexity limit, 16 long lines); `ruff format --check` would reformat 6 of
  them. Across every in-scope file (all tracked Python outside `piw/` and
  eval fixture projects) there are 766; with the planned rules (D100 to D107
  off, no C90) 528 remain, mostly long lines (187) and docstring style (D401,
  D205, D209).
- Complexity over 10 (C901) in `scripts/`: 6 functions in
  `manage_agent_tools.py` (`configure` 25, `host_problems` 21, `main` 15,
  `emit` 13, `install` 12, `merge_json` 11) and 10 in `install_skills.py`.
- Pyright 1.1.411 in basic mode, with nothing extra installed: 13 errors on
  the setup scripts and their three tests, 4 of them unresolved imports
  (`tomlkit`; `ruamel.yaml` and `serena.constants` in
  `render_serena_config.py`, which runs inside Serena's own environment;
  `fixture_lib`, which the eval harness adds to `sys.path` at run time); 91
  across every in-scope file, 24 of them unresolved imports. Strict mode on the
  setup scripts gives 148 to 177 errors depending on installed packages,
  mostly unknown types from JSON and TOML data.
- Pyright looks for `pyrightconfig.json` in the folders above where it runs,
  ahead of a `pyproject.toml` lower down: a root `pyrightconfig.json` made
  piw's strict check report 0 errors where it otherwise reports some. Ruff
  uses the configuration nearest each file, so a root `ruff.toml` does not
  affect piw. `uv run --with-requirements` does not enforce `--hash` lines;
  `uv pip install --require-hashes` does.
- `bootstrap.ps1`, `scripts/run_install_skills.ps1` and
  `scripts/set_private_permissions.ps1` are ASCII with LF endings in this
  checkout; `.gitattributes` fixes line endings only for `*.sh`.
  PSScriptAnalyzer 1.25.0 on PowerShell 7.6.7 reports one warning
  (`PSAvoidUsingWriteHost`) and no PowerShell 5.1 syntax incompatibility.
  shellcheck 0.11.0 reports two notes (SC2016) on the deliberately
  single-quoted wrapper text in `bootstrap.sh`. Pester 6.2.0 runs on Linux.
  Wine is not installed.
- `bootstrap.ps1` runs its whole bootstrap at the top level, so no part of it
  can be tested without downloading mise (on Linux it stops early at its
  Windows check). The generated `task.cmd` takes its line endings from the
  checkout's copy of `bootstrap.ps1` (LF here, CRLF on a Windows checkout with
  `core.autocrlf=true`), and the rewrite check compares with `.Trim()` only.
- `task ci` does not call `task check`; it lists `piw:ci`, `skills:check` and
  `test:agent-launchers` itself.
- PowerShell single-quote escaping in `scripts/run_gitnexus_hook.mjs` and
  `gitnexus_hook_launch` doubles only ASCII `'`; PowerShell also treats
  U+2018, U+2019, U+201A and U+201B as single quotes; in `pwsh` 7.6.7,
  `'O’Brien'` fails with "The string is missing the terminator".
- `scripts/manage_agent_tools.py` is 1,675 lines with 59 `host ==`/`!=`/`in`
  branches; `configure()` is 159 lines. Tool names are written out in about
  50 places and in the Taskfile's `tools:run` enum. `agent-dependencies.json`
  has `schema_version` 1, checked by both setup scripts.
- `tests/test_agent_setup.py` covers config writes, restores, hooks and doctor
  reasons, but its `configure` test patches out most of the real work and
  starts from an empty home.
- `tool_command`, `installed_version` and `preview` treat tools differently:
  Serena installs `serena` and `serena-hooks` and reports its version through
  its environment's package metadata; ast-grep is a native binary; GitNexus
  runs under Node, with a fallback entry point used on a fresh machine.
- Prerequisites: shellcheck 0.11.0 and PowerShell 7.6.7 lock for all six
  `mise.lock` platforms (checked 2026-11-06 with a scratch `mise lock`;
  windows-arm64 shellcheck uses the x64 build). Pester 6.2.0 and
  PSScriptAnalyzer 1.25.0 are on the PowerShell Gallery; their `.nupkg`
  checksums are recorded at the start of P2. Network access is needed once
  per pin.

## Requirements

| ID | Priority | Requirement | Check |
| --- | --- | --- | --- |
| REQ-001 | Must | A root ruff configuration governs every tracked Python file outside `piw/` and outside eval fixture projects; files under `piw/` keep using `piw/pyproject.toml`. | `ruff check --show-settings scripts/manage_agent_tools.py` names the root `ruff.toml`; the same for `piw/src/piw/cli.py` names `piw/pyproject.toml`; the Python files in `ruff check --show-files` equal `git ls-files '*.py' ':!piw' ':!tests/skill-evals/**/fixture/**'`. |
| REQ-002 | Must | piw's configuration and checks are unchanged, and piw's type check still reads piw's own configuration. | `git diff 284290e -- piw/` → empty; `./bootstrap.sh piw:check` → passes; `cd piw && uv run --locked pyright --verbose` names `piw/pyproject.toml` as its configuration. |
| REQ-003 | Must | `task lint:python` runs `ruff check`, `ruff format --check` and pyright (basic mode, and strict for the REQ-022 files from P5) on the in-scope files, from an environment installed with `--require-hashes` from a hash-pinned requirements file, and exits 0 on the delivered branch. | `./bootstrap.sh lint:python` → exit 0 and prints the pinned versions; with one hash in the requirements file changed, it fails before linting with a hash-mismatch error. |
| REQ-004 | Must | `task check` and `task ci` run `lint:python`, and fail when an in-scope file has a finding. | With FIX-009 applied in a scratch worktree, `./bootstrap.sh check` and `./bootstrap.sh ci` each exit non-zero naming that file and F401. |
| REQ-005 | Must | The lint configuration lands first; then one commit only reformats, and it is listed in `.git-blame-ignore-revs`. | Running the pinned `ruff format` on that commit's parent (which already holds `ruff.toml`) reproduces its tree exactly; `.git-blame-ignore-revs` lists it. |
| REQ-006 | Must | Each lint or type suppression in an in-scope file names its rule and gives a reason in the form `# noqa: <CODE> - <reason>` or `# pyright: ignore[<rule>] - <reason>`; no `# type: ignore` and no file-wide suppression outside the per-file ignores in the lint configuration. | `git grep -n -E 'noqa\|pyright: ignore\|type: ignore' -- '*.py' ':!piw' ':!tests/skill-evals/**/fixture/**'` → every hit matches one of the two forms; `git grep -n 'ruff: noqa' -- '*.py' ':!piw'` → none. |
| REQ-007 | Must | `task lint:shell` runs a pinned shellcheck on `bootstrap.sh` and passes; each deliberate exception carries a disable comment with its reason. | `./bootstrap.sh lint:shell` → exit 0. |
| REQ-008 | Must | `task lint:powershell` runs a pinned PSScriptAnalyzer on every tracked `.ps1` file with no Warning or Error findings, no PowerShell 5.1 syntax incompatibility (`PSUseCompatibleSyntax`), and no command or parameter missing from Windows PowerShell 5.1 (`PSUseCompatibleCommands` with its bundled Windows PowerShell 5.1 profile). | `./bootstrap.sh lint:powershell` → exit 0; with each FIX-008 sample added to `scripts/` in a scratch worktree, it exits non-zero naming the rule. |
| REQ-009 | Must | `bootstrap.ps1`'s checksum lookup and `task.cmd` text are functions covered by Pester tests: the lookup returns each pinned platform value and throws a message naming the missing key; `task.cmd` calls PowerShell through `%SystemRoot%` with CRLF line endings; an existing `task.cmd` that differs only in line endings is not rewritten. | `./bootstrap.sh test:powershell` → all Pester tests pass. |
| REQ-010 | Must | Tests can load `bootstrap.ps1`'s functions without running the bootstrap. | A Pester test mocks the bootstrap's main function, dot-sources `bootstrap.ps1`, and asserts it raised no error and the main function was called 0 times; running the script directly still calls it. |
| REQ-011 | Must | The Windows-only branches of the Python setup code have tests that run on Linux: the Serena hook command for Codex on Windows, the GitNexus `commandWindows` encoding, and the Windows permission command. | `./bootstrap.sh test:tooling` → the Windows branch tests pass, using FIX-007 paths with spaces and quotes. |
| REQ-012 | Must | PowerShell single-quoted strings built by setup escape every PowerShell single-quote character (`'`, U+2018, U+2019, U+201A, U+201B), in both `run_gitnexus_hook.mjs` and `manage_agent_tools.py`. | Python and Node tests encode a FIX-007 path containing U+2019, and `pwsh` parses the result back to the exact path. |
| REQ-013 | Must | `docs/setup.md` lists the Windows behavior Linux cannot prove and a step-by-step procedure to check it on a Windows host. | The section exists and covers each item in [Risks And Assumptions](#risks-and-assumptions) marked "Windows only". |
| REQ-014 | Must | An end-to-end test runs `configure("all")` twice in a temporary home seeded from FIX-001 to FIX-004, with upstream installers and version probes faked as executables (FIX-005), and passes on the code before P4. It runs on POSIX systems and is skipped elsewhere with a stated reason. | `./bootstrap.sh test:tooling` → the end-to-end test passes at the P3 commit. |
| REQ-015 | Must | After the first run, each compared file (FIX-006) equals its golden copy once machine-specific paths are replaced by placeholders; after the second run every file under the fake home has the same bytes and mode as after the first, apart from backups; unrelated user keys and hooks survive; and `host_problems` is empty for every host. | Same test. |
| REQ-016 | Must | Restructuring keeps setup's output unchanged, and the end-to-end test does not depend on function names the restructure changes. | After P4 and after P5, the end-to-end test passes with no change to it or its fixtures: `git diff <P3 commit> -- tests/fixtures/configure/ <end-to-end test file>` → empty. |
| REQ-017 | Must | Each host is described by one adapter: config file paths, how to read and write its servers, its environment key, its server command shape, its Serena context and its hooks file. `configure`, `preview`, `host_problems`, `require_standard_profiles` and `existing_server` take host details only from it. | A test registers a fake host adapter, and `configure`, `preview` and `host_problems` handle it with no other code change; `git grep -n -E '"(claude\|codex\|opencode\|pi)"'` over the setup code → hits only in the adapter definitions and the host list. |
| REQ-018 | Must | `configure()` is a short sequence of named steps, and no function in `manage_agent_tools.py` (or a package split out of it) exceeds complexity 10. | C901 at `max-complexity = 10` applies to those files in the lint configuration; `./bootstrap.sh lint:python` → exit 0. |
| REQ-019 | Must | Each tool's install method, commands and version probe come from its `agent-dependencies.json` entry, as defined in [Public Contracts](#public-contracts); install, command lookup, version checks, the npm package, latest-version lookups, the fresh-machine preview and the `--tool` choices all derive from it, and `tools:run` lets the script validate the name. | A test adds a fifth `npm` tool to a temporary manifest: the npm package lists it, its command resolves from its fields, and `--tool` accepts it; an entry with an unknown `installer` fails with a message naming the tool and the field. |
| REQ-020 | Must | Users see no change from P4 and P5: the setup preview on this machine matches the run saved before P4, and `doctor` stays healthy. | Before P4, from the main checkout and before any reconfigure, save `manage_agent_tools.py --command preview --target all --output json` outside the repo; after P4 and after P5, the same command from the same checkout path gives the same output; `./bootstrap.sh doctor` → healthy. |
| REQ-021 | Must | Dropped — won't do: the owner removed the commit-scan requirement on 2026-11-06. | None |
| REQ-022 | Must | Pyright strict mode passes on `manage_agent_tools.py` and any package split out of it, using the typed host and tool records from P4 and P5; the rest of the in-scope Python stays on basic mode. | `lint/pyrightconfig.json`'s `strict` list names `../scripts/manage_agent_tools.py` (and any split package); `./bootstrap.sh lint:python` → exit 0; with an unannotated parameter added to `manage_agent_tools.py` in a scratch worktree, it fails with `reportMissingParameterType`. |

## User Experience And Public Surface

| Surface | Action or input | Expected result | Compatibility |
| --- | --- | --- | --- |
| Task | `lint:python`, `lint:shell`, `lint:powershell`, `test:powershell` | Run the checks above; exit non-zero with the file and rule on a finding | New |
| Task | `deps:dev-tools` | Installs the development-only tools: the lint environment, shellcheck, PowerShell 7, Pester and PSScriptAnalyzer | New; `deps:tools` and `install` download nothing new |
| Task | `check`, `ci` | Also run the three lint tasks and `test:powershell` | Changed: can fail on lint findings |
| Task | `tools:run TOOL=<name>` | Accepts any tool in `agent-dependencies.json`; an unknown name fails with the list of valid names | Changed: validation moves from Task to the script |
| Configuration | `agent-dependencies.json` tool entries | Each entry has `installer` and `bin` | Changed: additive; same commit updates the file |
| Configuration | `ruff.toml` and `.git-blame-ignore-revs` at the repo root; the pyright configuration, lint requirements and development-only tool pins in a `lint/` folder | Configure checks for Python outside `piw/` | New |
| Generated file | `.tools/bin/task.cmd` on Windows | CRLF line endings; rewritten only when its content changes | Changed |

## Expected Experience

### CLI

```text
$ ./bootstrap.sh lint:python
ruff 0.16.2
All checks passed!
<n> files already formatted
0 errors, 0 warnings, 0 informations

$ ./bootstrap.sh tools:run TOOL=nope -- --version
tools:run: unknown tool 'nope'; choose one of serena, ast-grep, gitnexus, cq
```

### Configuration

```text
"gitnexus": {
  "package": "gitnexus",
  "version": "1.6.12",
  "installer": "npm",
  "bin": "gitnexus",
  "runs_with": "node",
  "entry": "dist/cli/index.js",
  ...
}
```

An entry without `installer`, or with a value other than `uv`, `npm` or
`github-release`, stops `tools:install` before any download:

```text
tools:install: agent-dependencies.json tools.gitnexus.installer must be one of uv, npm, github-release
```

## Public Contracts

- `agent-dependencies.json`: `schema_version` stays 1. Each `tools.<name>`
  entry gains:
  - `installer` (required): `uv`, `npm` or `github-release`. A `uv` tool
    reports its version from its environment's package metadata; the others
    run `<bin> --version`.
  - `bin` (required): the main executable the tool installs.
  - `extra_bins` (optional): other executables it installs, such as
    `serena-hooks`.
  - `runs_with` (npm only, required): `native` or `node`.
  - `entry` (npm only, required when `runs_with` is `node`): the script path
    inside the package, used when the package is not installed yet.

  Invalid or missing values stop install, configure, doctor and run with the
  message above; no partial install happens.
- New Task names: `lint:python`, `lint:shell`, `lint:powershell`,
  `test:powershell`. Each exits 0 on success and non-zero with the failing
  file and rule otherwise.
- Development-only tool versions live in the `lint/` folder: ruff, pyright
  and `tomlkit` in a hash-pinned requirements file; shellcheck and PowerShell
  in a separate mise environment with its own lock; Pester and
  PSScriptAnalyzer as exact versions with SHA-256 checksums of their
  `.nupkg` files. `mise.toml` and `mise.lock` do not change.

## Quality Attributes

| Attribute | Scenario | Pass/fail measure |
| --- | --- | --- |
| Maintainability | Add a fifth tool installed from npm | Only `agent-dependencies.json` and the npm lock change |
| Maintainability | Change one host's server layout | Only that host's adapter changes |
| Reliability | Run `configure` twice | Second run reports every file unchanged (REQ-015) |
| Isolation | Run `piw:check` and `lint:python` | Each uses only its own configuration (REQ-001, REQ-002) |

## Traceability

Phase state lives in the README `## Phases` table; phase details and evidence
live in `IMPLEMENTATION_PLAN.md`.

| Requirement | Design section | Phase |
| --- | --- | --- |
| REQ-001 to REQ-006 | [Lint and type checks](SADD.md#lint-and-type-checks) | P1 |
| REQ-007 to REQ-013 | [Windows checks from Linux](SADD.md#windows-checks-from-linux) | P2 |
| REQ-014, REQ-015 | [End-to-end test](SADD.md#end-to-end-test) | P3 |
| REQ-016, REQ-017, REQ-018, REQ-020 | [Host adapters](SADD.md#host-adapters) | P4 |
| REQ-016, REQ-018, REQ-019, REQ-020 | [Tools from the manifest](SADD.md#tools-from-the-manifest) | P5 |
| REQ-022 | [Lint and type checks](SADD.md#lint-and-type-checks) | P5 |

## Risks And Assumptions

Open questions go in the README's `## Open questions` section, one
`Open question:` line each. Record adopted decisions in `SADD.md`.

| Item | Type | Affected requirements or phases | Blocks work? | Owner | Resolution or permitted assumption |
| --- | --- | --- | --- | --- | --- |
| Restructuring changes what setup writes to a user's agent config | Risk | P4, P5 | Yes: P4 starts only after REQ-014 passes | @nccurry | Golden-file test (REQ-015, REQ-016), dry-run comparison (REQ-020), and the existing config backups |
| Fixing 528 findings (after the planned rule set) across all in-scope Python is larger than the setup scripts alone | Risk | P1 | No | @nccurry | Per-file ignores for the eval harness and fixture tests are allowed when each names its rule and reason (REQ-006); report the final count in P1 evidence |
| The end-to-end test's golden files depend on machine paths and installed tools | Risk | REQ-014, REQ-015 | No | @nccurry | Placeholders for paths, a fixed `PATH`, `LLMS_ORIGINAL_PATH`, `SERENA_HOME` and temp root, and fake executables for version probes (FIX-005, FIX-006) |
| Windows only: `cmd.exe` parsing of `task.cmd`, Windows PowerShell 5.1 at runtime, ACLs set by `set_private_permissions.ps1`, Task's `[ -L ]` test on junctions, Codex running hook commands through `cmd` | Risk | REQ-013 | No | @nccurry | Linux checks cover syntax and logic only; REQ-013 records the manual procedure; hosted CI deferred by the owner on 2026-11-06 |
| A separate mise environment can install and lock shellcheck and PowerShell without touching `mise.toml` | Assumption | P2 | Yes: REQ-007 to REQ-010 | @nccurry | Confirm at the start of P2; the tools themselves lock for all six platforms (checked 2026-11-06) |
| Pyright strict on the setup script needs typed JSON and TOML handling | Risk | REQ-022 | No | @nccurry | P4 and P5 introduce typed host and tool records; untyped third-party data is narrowed at the boundary where it is read |
| A formatting commit makes `git blame` noisy | Risk | REQ-005 | No | @nccurry | `.git-blame-ignore-revs` |
