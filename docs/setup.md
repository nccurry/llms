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
- Use a Task you already have installed. It reads this Taskfile and uses this checkout's tools.

Bootstrap records the folder you called it from in `LLMS_CALLER_CWD`, so `tools:run` works on
that project when you call this checkout's bootstrap from somewhere else.

Add `OUTPUT=json` to get reports in JSON format.

## Setup commands

| Task | What it does |
|---|---|
| `install TARGET=...` | Runs `deps:install`, `tools:install`, `skills:install`, `agents:configure`, and `doctor` in order |
| `install:dry-run TARGET=...` | Shows the tool, skill, and configuration changes without making them |
| `deps:install`, alias `setup` | Installs pinned Task, uv, and Node, and prepares piw's development environment |
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

Required external skills come from the pinned sources in
`agent-dependencies.json`. Tool installers manage their own bundled skills and
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

File validation checks packaging rules. Use [skill behavior checks](../tests/skill-evals.md)
to assess how agents select and follow skills.
Setup scripts are checked by running them. Worktree cleanup uses the agent's
assessment and standard Git commands; it has no custom preflight script.

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

See the [agent tools guide](agent-tools.md#versions-and-dependency-updates) for npm
lockfiles and Serena overrides.
