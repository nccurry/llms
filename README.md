# LLM Tools and Skills

Reusable agent skills, tools, and personal setup. Keep project-specific facts,
design notes, build commands, and rules in the project they describe.

- [`skills`](skills/) contains managed Agent Skills; [`scripts`](scripts/) holds their installer and the setup scripts.
- [`templates`](templates/README.md) has starting `AGENTS.md`, `CLAUDE.md`, and `llms.txt` files for new repositories.
- [`piw`](piw/README.md) runs persistent or disposable Pi sessions in Docker Sandboxes.
- [`agent-dependencies.json`](agent-dependencies.json) pins external skills and agent tools.
- [`agent-runtime.txt`](agent-runtime.txt) pins the Python libraries used by setup commands.

## Use the skills

Describe what you want done. Call a skill with `$skill-name`
in Codex or `/skill-name` in Claude Code. Agents can also choose skills from their
descriptions. Ask explicitly to use a monitored implementation workflow.

![Skill workflow: investigate, plan, review the plan, build, audit and repair, then deliver and clean up. Plain English, clear design, and verified claims apply throughout.](docs/images/skill-workflow.svg)

### Pick the next step

| When you want to… | Use | Example request |
|---|---|---|
| Understand existing code | [repo-navigation](skills/repo-navigation/SKILL.md) | “Trace how configuration reaches the cache.” |
| Reproduce a bug | [debug-and-reproduce](skills/debug-and-reproduce/SKILL.md) | “Reproduce this reload failure and fix its cause.” |
| Plan a larger change | [plc-planning](skills/plc-planning/SKILL.md) | “Plan config reloads. Include requirements, steps, and checks.” |
| Improve a written plan | [review-and-fix-plc](skills/review-and-fix-plc/SKILL.md) | “Have a subagent review this plan, then fix supported findings.” |
| Start one feature by hand | [plc-feature-start](skills/plc-feature-start/SKILL.md) | “Start this up in a new branch and worktree from main.” |
| Implement selected plan work | [monitored-sol-plc-execution](skills/monitored-sol-plc-execution/SKILL.md) | “Finish phase 1, including tests and docs. Open an MR; leave it unmerged.” |
| Review a change thoroughly | [audit-codebase](skills/audit-codebase/SKILL.md) | “Audit this branch against main. Report findings without editing.” |
| Handle review feedback | [resolve-review-comments](skills/resolve-review-comments/SKILL.md) | “Check the PR feedback against the source and fix valid issues.” |
| Get open MRs ready for review | [plc-mr-review](skills/plc-mr-review/SKILL.md) | “Get these MRs ready: CI green and comments resolved. Don’t merge.” |
| Keep tickets in step with the work | [manage-tickets](skills/manage-tickets/SKILL.md) | “Link this plan to PROJ-123 and put the key in the MR title the way this repo does.” |
| Write or refresh a review description | [create-mr-description](skills/create-mr-description/SKILL.md) | “Update the MR description with examples, change counts, and actual test results.” |
| Catch up and save progress | [plc-checkpoint](skills/plc-checkpoint/SKILL.md) | “Where are we? Update the plan and tidy what’s merged.” |
| Finish delivery | [plc-wrapup](skills/plc-wrapup/SKILL.md) | “Merge the approved MR, update the plan, and clean up this task’s worktrees.” |
| Remove stale local work | [clean-stale-worktrees](skills/clean-stale-worktrees/SKILL.md) | “Remove finished worktrees. Keep unmerged work.” |

A **PLC** (Plan-Led Change) records requirements, design, delivery phases, and
checks. Small fixes can go straight from investigation to repair and testing.

See [skill workflows](docs/skill-workflows.md) for plan examples, model choices,
and the steps from implementation through delivery.

## Set up a computer

### 1. Install the prerequisites

| Platform | Install |
|---|---|
| All | [Git](https://git-scm.com/downloads) |
| Windows | PowerShell 7: `winget install --id Microsoft.PowerShell -e` |
| Linux/macOS | `curl` or `wget`, and `sha256sum` or `shasum` (most systems already have these) |

You don't need mise, Task, Python, Node, or uv. Bootstrap downloads pinned copies into this
checkout.

On Windows, setup uses the built-in Windows PowerShell 5.1. Agent apps use
PowerShell 7 (`pwsh`); install it with winget. See troubleshooting below if a global
mise installation has taken over `pwsh`.

### 2. Clone this repository

```bash
git clone https://github.com/nccurry/llms.git
cd llms
```

Keep the checkout in a stable place. Agent configuration points to it, so if you move it,
run `agents:configure` again.

### 3. Install everything

Linux/macOS:

```bash
./bootstrap.sh install TARGET=all
```

Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 install TARGET=all
```

This installs pinned tools and skills, configures the agents, and runs `doctor`.
`TARGET=all` covers Codex, Claude, Pi, and OpenCode. Use `TARGET=codex`, `claude`, `pi`, or `opencode` for one agent only.

To preview changes, first run bootstrap with no arguments to download the setup
tools, then run `install:dry-run TARGET=all` through the same script.

### 4. Check it works

`install` ends by running `doctor`. Read its report for anything missing. `doctor` checks
installed files and configuration only. Restart your agent apps and try a real query in a
project before relying on a tool.

### Update later

```bash
git pull
./bootstrap.sh install TARGET=all
```

On Windows, run `git pull`, then the same `bootstrap.ps1 install TARGET=all` command as step 3.

Use `skills:install TARGET=all` instead of `install` to update only the skills. Installs are
safe to repeat: unchanged skills are skipped, and changed ones are backed up first.
Installs use the external skill commits recorded in `agent-dependencies.json`. Run
`skills:update TARGET=all` to move them to upstream's latest commit; it rewrites that
tracked file, so commit or discard the change before your next `git pull`.

### Troubleshooting

| Problem | Fix |
|---|---|
| `mise ERROR No version is set for shim: pwsh` | A global mise owns `pwsh` without a version. Run `mise uninstall powershell --all`, then install PowerShell 7 with winget. |
| Agent tools point to an old folder | Run `agents:configure TARGET=all` through bootstrap from the current checkout. |
| `mise ERROR mise version ... is required` | A global mise is running this checkout's shims. Run commands through `./bootstrap.sh` or `.tools/bin/task` instead of a global `task`. |
| A skill install failed | Rerun with `OUTPUT=json`. The report lists backup paths and the failed check. |

## How setup works

Bootstrap downloads the pinned setup tools into `.tools/` and runs commands from
`Taskfile.yml`. It leaves your shell profile, PATH, and global mise setup unchanged.
Run commands through bootstrap, such as `./bootstrap.sh doctor`, or through
`.tools/bin/task`, which bootstrap writes. A `task` from a global mise may not match
this checkout's pins.

With no arguments, bootstrap prepares the tools and piw development environment.
Use `install TARGET=all` to install skills and configure agents.

See the [setup reference](docs/setup.md) for all commands, version updates,
skill maintenance, and recovery steps.

## Agent tools

| Tool | Main use |
|---|---|
| Serena | Find symbols and references through standard language servers |
| ast-grep | Search structural code patterns through the CLI |
| GitNexus | Query code maps, execution flows, and change impact |
| cq | Store and find lessons from previous debugging locally |
| Ponytail skills | Review code and look for bugs or unnecessary complexity |

The setup above installs and configures these tools.

Run a tool directly with `task tools:run TOOL=ast-grep -- --version`.
GitNexus is enabled for a personal noncommercial trial; resolve licensing before commercial use.

See the [agent tools guide](docs/agent-tools.md) for configuration, Serena sessions and
dashboards, GitNexus indexing and licensing, and dependency updates.

## Development

| Command | Checks |
|---|---|
| `task test` | piw application tests, setup-script tests, and agent launchers; no network or live Docker Sandboxes |
| `task lint:python` | Ruff lint, Ruff format check, and Pyright (basic mode, Python 3.11) on the Python outside `piw/`: `scripts/`, `skills/` and `tests/`, except the eval fixture projects under `tests/skill-evals/**/fixture/`. Pyright also skips `scripts/render_serena_config.py`, which runs in Serena's own environment. Only `task deps:dev-tools` installs the lint tools (`task install` does not); run it first. It installs the hash-pinned tools from `lint/requirements.txt` into `.tools/lint/`. |
| `task lint:shell`, `task lint:powershell`, `task test:powershell` | shellcheck on `bootstrap.sh`; PSScriptAnalyzer (with Windows PowerShell 5.1 syntax and command checks) on every tracked `.ps1` file; Pester tests for `bootstrap.ps1`. `task deps:dev-tools` installs their pinned tools. See [Windows setup](docs/setup.md#windows-setup-what-linux-checks-cannot-prove) for what they cannot prove. |
| `task check` | piw formatting, lint, types, and coverage; `lint:python`, `lint:shell`, `lint:powershell` and `test:powershell` (run `task deps:dev-tools` once first); skill validation and tests; launcher checks. Fetches external skills. |
| `task ci` | `check`, plus a piw build and a smoke test of the installed package; needs `task deps:dev-tools` once first |

`piw/` keeps its own Ruff and strict Pyright settings in `piw/pyproject.toml`. The settings for the
rest are `ruff.toml` and `lint/pyrightconfig.json`. `.git-blame-ignore-revs` lists the
formatting-only commit; run `git config blame.ignoreRevsFile .git-blame-ignore-revs` to skip it in
`git blame`.

Run `task test:agent-launchers` to check only the launchers. If the pinned GitNexus
is installed, these checks also run its real hook. Project commands are available
under `piw:` and `skills:`.

See [skill maintenance](docs/setup.md#maintain-installed-skills)
for installer and validation commands.

## piw

Install the current piw checkout as a uv tool:

```bash
task piw:install
```

Or install directly from Git using an available uv:

```bash
uv tool install 'git+https://github.com/nccurry/llms#subdirectory=piw'
```

See the [piw README](piw/README.md) for requirements, configuration, commands, and development.
