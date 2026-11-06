# Setup reference

[Back to the README](../README.md#set-up-a-computer).

For first-time installation, follow [Set up a computer](../README.md#set-up-a-computer).
This guide covers setup commands, skill maintenance, and recovery.

- [How setup works](#how-setup-works)
- [Setup commands](#setup-commands)
- [Maintain installed skills](#maintain-installed-skills)
- [Recover from a failed install](#recover-from-a-failed-install)
- [Update tool versions](#update-tool-versions)

## How setup works

| Part | What it does |
|---|---|
| `bootstrap.sh` / `bootstrap.ps1` | Downloads a checksum-verified, pinned mise and Task into `.tools/`, then passes its arguments to Task |
| `mise.toml` / `mise.lock` | Pin Task, uv, and Node, with their download checksums |
| `Taskfile.yml` | Defines the install, check, development, and update commands |
| `scripts/` | Install skills and tools, and merge agent configuration |

Downloaded tools and setup files stay in the ignored `.tools/` folder. Bootstrap
leaves your shell profile, PATH, and global mise setup unchanged. uv manages Python; the version comes from
[`piw/.python-version`](../piw/.python-version).

With no arguments, bootstrap runs `deps:install`. That prepares the pinned tools and the piw
development environment only. It does not install skills or configure agents.

After the first bootstrap, you can call Task in three ways:

- Keep using bootstrap with Task arguments, for example `./bootstrap.sh doctor`.
- Add `.tools/bin` to your PATH and run `task doctor`.
- Use a Task you already have installed, as long as it is not run through a global mise older
  than this checkout's: that mise refuses this checkout's shims.

Bootstrap records the folder you called it from in `LLMS_CALLER_CWD`, so `tools:run` works on
that project when you call this checkout's bootstrap from somewhere else.

Add `OUTPUT=json` to get reports in JSON format.

## Setup commands

| Task | What it does |
|---|---|
| `install TARGET=...` | Runs `deps:install`, `tools:install`, `skills:install`, `agents:configure`, and `doctor` in order |
| `install:dry-run TARGET=...` | Shows the tool, skill, and configuration changes without making them |
| `deps:install`, alias `setup` | Installs pinned Task, uv, and Node, and prepares piw's development environment |
| `deps:dev-tools` | Not part of `deps:install`. Installs the development-only tools: the hash-pinned Ruff and Pyright from `lint/requirements.txt` into `.tools/lint/`, shellcheck and PowerShell 7 pinned in `lint/mise.toml` (locked in `lint/mise.lock`), and the PowerShell modules Pester and PSScriptAnalyzer into `.tools/powershell-modules/`. Each module download is checked against the SHA-256 in `lint/powershell-modules.json` before it is unpacked. `lint:python`, `lint:shell`, `lint:powershell` and `test:powershell` need it |
| `lint:python` | Runs Ruff lint, Ruff format check, and Pyright on the Python outside `piw/` |
| `lint:shell` | Runs shellcheck on `bootstrap.sh` |
| `lint:powershell` | Runs PSScriptAnalyzer on every tracked `.ps1` file, including its Windows PowerShell 5.1 syntax and command checks |
| `test:powershell` | Runs the Pester tests for `bootstrap.ps1` in `tests/powershell/` |
| `tools:install` | Installs the pinned Serena, ast-grep, GitNexus, and local cq |
| `tools:run TOOL=... -- ...` | Runs a local tool with its arguments in the caller's project or worktree |
| `skills:install TARGET=...` | Installs the managed skills and the external skills they need |
| `agents:configure TARGET=...` | Adds the tools to each agent's configuration and keeps existing settings |
| `doctor TARGET=...` | Reports tool versions and agent configuration (not live connections) |
| `deps:versions` | Reports the selected tool versions |
| `deps:check` | Reports available updates without changing pins |

## Maintain installed skills

The installer checks skill files before changing an installation. It prepares a
copy, compares file hashes, and backs up changed skills outside the folders agents
search for skills. If replacement fails, it restores the previous copy. Old
`*.backup-*` folders are moved out of those search folders to prevent duplicate skills.

Each install records the skills it installed in `.<skills folder>-installed.json`
beside the skills folder, for example `~/.claude/.skills-installed.json`. A
recorded skill that is no longer in this repo, such as one that was renamed, is
moved to the backup folder on the next install. Skills from other installers are
never moved. `RETIRED_SKILLS` in `scripts/install_skills.py` lists skills
removed before installs were recorded.

Normal skill installs check the upstream GitHub default branch for external
skills, validate the downloaded files, and record the installed commits and
checksums in `agent-dependencies.json`. All six Ponytail skills are managed this
way. An upstream lookup failure stops installation; it does not silently use an
old version. Tool installers manage their own bundled skills and
integrations; keep one copy of each. Skill validation checks source dependencies.
`doctor` checks installed packages and configuration. Try the skills in an agent app
to check that they work.

```bash
task skills:list
task skills:fetch
task skills:validate
task skills:test
task skills:dry-run TARGET=codex
task skills:install TARGET=codex
```

You can also use target-specific commands such as `skills:install:codex` and
`skills:dry-run:codex`. Matching commands exist for Claude, Pi, and OpenCode.

`skills:fetch` downloads and verifies external skill sources without changing installed
skills. `skills:validate` works offline and reports missing or invalid sources.
`skills:check` fetches dependencies, validates skills, and runs their script tests.
Installation prepares external dependencies before changing installed skills.
`skills:install` and the dry runs use the commits recorded in `agent-dependencies.json`.
`skills:update` moves external skills to upstream's latest commit and records it, which
changes that tracked file. Fetch and validation commands also use the recorded commits,
so checks do not advance dependency versions.

File validation checks packaging rules, not agent behavior. Maintain skill
instructions from actual use and observed failures. Setup scripts are checked
by `task test:tooling`. Worktree cleanup uses the agent's assessment, standard Git
commands, and the read-only `worktree_report.py` fact report in that skill.

The direct installer remains available through `scripts/install_skills.py`; run it with the
uv-managed Python version. `scripts/run_install_skills.ps1` is a compatibility wrapper for an
already available Python runtime. Use root bootstrap for first-time setup.

## Recover from a failed install

Keep installer and configuration reports with `OUTPUT=json`. They list backup paths
and failed checks. Fix the reported prerequisite before retrying. A moved
checkout needs `agents:configure` again so host launchers point to the current location. To
restore an earlier managed skill revision, check out that reviewed revision here and rerun
`skills:install`; retain the external backups until the restored skills are verified.

## Update tool versions

For native tool updates, edit `mise.toml`, then refresh `mise.lock` with this
checkout's mise binary. `vars.mise_version` selects the bootstrap release. Keep exact
version pins and review lockfile changes. `deps:check` reports updates without applying them.

The lint tools are pinned in `lint/requirements.in` and are not reported by `deps:check`. To
update them, edit that file, then regenerate the hashed list:

```sh
MISE_DATA_DIR=.tools/mise/data .tools/bin/mise exec -- uv pip compile --generate-hashes --python-version 3.14 lint/requirements.in -o lint/requirements.txt
```

Review the diff, then rerun `task deps:dev-tools` and `task lint:python`.

shellcheck and PowerShell are pinned in `lint/mise.toml`, apart from `mise.toml`, so the
installed tools (`install`, `deps:install`) never download them. Task runs mise with `lint/` as the
working directory, and mise then reads `lint/mise.toml` along with the root `mise.toml`. To
change a version, edit `lint/mise.toml` and refresh the lock with this checkout's mise binary:

```sh
cd lint && MISE_DATA_DIR=../.tools/mise/data ../.tools/bin/mise lock -p linux-x64,linux-arm64,macos-x64,macos-arm64,windows-x64,windows-arm64
```

Pester and PSScriptAnalyzer are pinned in `lint/powershell-modules.json`. To change one, set the
new version and the SHA-256 of its `.nupkg` file from
`https://www.powershellgallery.com/api/v2/package/<name>/<version>`, then rerun
`task deps:dev-tools`.

## Windows setup: what Linux checks cannot prove

On Linux, `lint:shell`, `lint:powershell`, `test:powershell`, `test:tooling` and
`test:agent-launchers` check the Windows path as far as a Linux host can: shell and PowerShell
syntax (including Windows PowerShell 5.1 compatibility), the logic of the functions in
`bootstrap.ps1`, and the exact commands the Python and Node code build for Windows. Nothing runs
Windows itself. These behaviors need a Windows host:

- `cmd.exe` parsing of `.tools/bin/task.cmd` (its quoting, `%~dp0`, `%SystemRoot%` and `%*`).
- Windows PowerShell 5.1 at runtime. The Linux checks run PowerShell 7 and only read the 5.1
  command list; they cannot catch a difference in behavior.
- The ACLs that `scripts/set_private_permissions.ps1` writes.
- Task's `[ -L ... ]` test on `.tools/mise/data` in `deps:tools`, when that folder is a junction
  or symbolic link on Windows.
- Codex running the Windows hook commands through `cmd`: the Serena hook command line and the
  GitNexus `commandWindows` value that starts Windows PowerShell with `-EncodedCommand`.

### Check these on a Windows host

Use a Windows 10 or 11 machine with Windows PowerShell 5.1 and a user account that is not an
administrator. Use a checkout path with a space and an apostrophe, such as
`C:\Users\Test User\My 'Repos'\llms`. To check the typographic apostrophe case too, use
`O’Brien` (with U+2019) in the user folder name.

1. In a normal (non-elevated) Windows PowerShell 5.1 window, run
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 deps:install`. It should end
   without an error and create `.tools\bin\mise.exe`, `.tools\bin\mise-shim.exe` and
   `.tools\bin\task.cmd`.
2. Check the line endings of `task.cmd`:
   `$b = [IO.File]::ReadAllBytes('.tools\bin\task.cmd'); ($b | Where-Object { $_ -eq 10 }).Count -eq ($b | Where-Object { $_ -eq 13 }).Count`
   should print `True`. Run step 1 again and check that the file's last write time did not change.
3. From a `cmd.exe` window in a different folder, put `.tools\bin` on `PATH` and run
   `task --version`, then `task` with no arguments. Both should run through the bootstrap and
   print Task output, not a parse error from `cmd`.
4. Run `.\bootstrap.ps1 deps:tools` twice. The second run should finish without an error, which
   covers Task's `[ -L ]` test.
5. Run `.\bootstrap.ps1 tools:install`, `.\bootstrap.ps1 agents:configure TARGET=codex` and
   `.\bootstrap.ps1 doctor TARGET=codex`. `doctor` should report no problems.
6. Open `%USERPROFILE%\.codex\hooks.json`. Copy a Serena hook `command` and the GitNexus
   `commandWindows` value into a `cmd.exe` window one at a time. Each should start without a
   quoting error (the Serena command prints a usage or JSON message and exits).
7. Check the ACLs on a file the setup protects, for example
   `icacls $env:USERPROFILE\.codex\config.toml`. Only your account and `SYSTEM` should appear,
   and inheritance should be off.
8. Start Codex, open a project, and confirm that the session-start hook runs without an error in
   its log.

Record anything that differs in the PR or issue that asked for the check.

See the [agent tools guide](agent-tools.md#versions-and-dependency-updates) for npm
lockfiles and Serena overrides.
