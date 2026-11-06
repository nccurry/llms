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
| `deps:dev-tools:lock` | Regenerates `lint/requirements.txt` and `lint/mise.lock` after you edit `lint/requirements.in` or `lint/mise.toml` |
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

The Python lint tools are pinned in `lint/requirements.in`, and shellcheck and PowerShell in
`lint/mise.toml`, apart from `mise.toml`, so the install tasks never download them. None of them is
reported by `deps:check`. To change one, edit that file, then run:

```sh
task deps:dev-tools:lock
```

It regenerates the hashed `lint/requirements.txt` and `lint/mise.lock` (for the six platforms in
`mise.lock`) with the same environment the other tasks use. Review the diff, then rerun
`task deps:dev-tools` and `task lint:python`.

The lint-only mise tools use their own data directory, `.tools/lint-mise/data`, and read only
`lint/mise.toml` (Task runs mise with `lint/` as the working directory and stops it at the checkout
root). mise rebuilds every shim in a data directory it installs into, and points each one at the
`mise` it runs from, even when the install then fails. Keeping these tools out of
`.tools/mise/data` means `deps:dev-tools` never changes those shims.

A worktree can share another checkout's `.tools/mise/data` through a link (at `.tools`,
`.tools/mise` or `.tools/mise/data`). That checkout owns the shims, and a worktree's `mise`
disappears when the worktree is removed. So `bootstrap.sh` and `deps:tools` run
`scripts/ensure_mise_tools.sh`: when the data directory resolves to a place outside the checkout,
it never installs. It checks with the read-only `mise ls --missing`, passes when the pinned tools
are there, and otherwise stops and names the owning checkout, where you run
`./bootstrap.sh deps:tools`. A checkout that owns its data directory installs as usual. (This does
not cover `deps:dev-tools` when `.tools` itself is a link; that rebuilds only the lint tools' own
shims in the owner's `.tools/lint-mise`.)

Pester and PSScriptAnalyzer are pinned in `lint/powershell-modules.json`. To change one, set the
new version and the SHA-256 of its `.nupkg` file from
`https://www.powershellgallery.com/api/v2/package/<name>/<version>`, then rerun
`task deps:dev-tools`. `lint:powershell` and `test:powershell` import the pinned copy by its exact
path and fail if PowerShell loads a module from anywhere else.

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
- `deps:tools` when `.tools/mise/data` is a junction to another checkout's data. On Linux, a
  script refuses to install into a shared directory; on Windows that step is skipped, and nothing has run it.
- Codex running the Windows hook commands through `cmd`: the Serena hook command line and the
  GitNexus `commandWindows` value that starts Windows PowerShell with `-EncodedCommand`.

### Check these on a Windows host

Use a Windows 10 or 11 machine with Windows PowerShell 5.1 and a user account that is not an
administrator. Use a checkout path with a space and an apostrophe, such as
`C:\Users\Test User\My 'Repos'\llms`. To check the typographic apostrophe case too, use
`O’Brien` (with U+2019) in the user folder name. Run the PowerShell commands in a Windows
PowerShell 5.1 window in the checkout, and the `cmd` commands in a `cmd.exe` window.

1. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 deps:install`. It
   should end without an error and create `.tools\bin\mise.exe`, `.tools\bin\mise-shim.exe` and
   `.tools\bin\task.cmd`.
2. Check the line endings of a new `task.cmd` (delete `.tools\bin\task.cmd` and run step 1 once
   more to get one). This should print `True`:
   `$b = [IO.File]::ReadAllBytes('.tools\bin\task.cmd'); ($b | Where-Object { $_ -eq 10 }).Count -eq ($b | Where-Object { $_ -eq 13 }).Count`
   Run step 1 again and check that the file's last write time did not change. A `task.cmd` that
   differs only in line endings (for example one with LF endings) is deliberately left as it is: it
   runs the same, and rewriting a batch file while `cmd` runs it breaks the run. To check that,
   convert the file to LF
   (`(Get-Content .tools\bin\task.cmd -Raw).Replace([string][char]13, '') | Set-Content -NoNewline .tools\bin\task.cmd`),
   run step 1, and confirm the file is still LF and `task --version` (step 3) still works.
3. In a `cmd.exe` window in a different folder, run
   `set "PATH=<checkout>\.tools\bin;%PATH%"`, then `task --version`, then `task` with no
   arguments. Both should run through the bootstrap and print Task output, not a parse error from
   `cmd`. Use `task` for the next steps in this window.
4. Run `task deps:tools` twice. The second run should finish without an error. Then check a
   junction: make a second checkout (for example `git worktree add ..\llms-second`), and in it
   run `cmd /c mklink /J .tools\mise\data <first checkout>\.tools\mise\data` (create `.tools\mise`
   first), then `powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 deps:tools`.
   It should end without an error. Back in the first checkout, run
   `.tools\mise\data\shims\node.exe --version`; it should still print Node's version. Remove the
   junction (`rmdir .tools\mise\data` removes only the link) and the second checkout afterwards.
5. Run `task tools:install`, `task agents:configure TARGET=codex` and `task doctor TARGET=codex`.
   `doctor` should report no problems.
6. Read the Codex hook commands with PowerShell and run each one by hand in a `cmd.exe` window.
   List them with:
   `(Get-Content "$env:USERPROFILE\.codex\hooks.json" -Raw | ConvertFrom-Json).hooks.PSObject.Properties | ForEach-Object { $n = $_.Name; $_.Value.hooks | ForEach-Object { "[$n]"; $_.command; $_.commandWindows } }`
   It prints each event's name, then each hook's `command` and (when it has one) `commandWindows`.
   Paste each `commandWindows` value, or the `command` value for a hook without one, into `cmd`
   with `echo {} |` in front, for example `echo {} | "C:\...\serena-hooks.exe" remind --client=codex`.
   Each should start without a quoting or parsing error. (A hook may print a message or an error
   about the empty event it received; that is fine.)
7. Check the ACLs on something setup always restricts. When setup updates a config file that
   already exists, it keeps that file's own ACL, so `config.toml` is not a good check on a profile
   that already had one. Backups are always restricted: run
   `icacls .tools\agent-tools\config-backups` and then `icacls` on the newest folder inside it.
   Only your account and `SYSTEM` should appear, and inheritance should be off. If there is no
   `config-backups` folder, setup updated no existing file (a fresh profile): then
   `icacls "%USERPROFILE%\.codex\config.toml"` shows the ACL of a file setup created, with the same
   expected result.
8. Start Codex, open a project, and confirm that the session-start hook runs without an error in
   its log.

Record anything that differs in the PR or issue that asked for the check.

See the [agent tools guide](agent-tools.md#versions-and-dependency-updates) for npm
lockfiles and Serena overrides.
