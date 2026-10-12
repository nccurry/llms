# LLM Tools and Skills

This repository owns reusable agent processes and personal agent setup. Project facts,
architecture, build commands, and local constraints stay in their project repositories.

- [`skills`](skills/) contains managed Agent Skills and their installer.
- [`piw`](piw/README.md) runs persistent or disposable Pi sessions in Docker Sandboxes.
- [`agent-dependencies.json`](agent-dependencies.json) pins external skills and agent tools.
- [`agent-runtime.txt`](agent-runtime.txt) pins the Python libraries used by setup commands.

## Bootstrap and Task

The setup follows the same layering as the Pinlight repositories:

| Layer | Responsibility |
|---|---|
| `bootstrap.sh` / `bootstrap.ps1` | Download checksum-verified, pinned local mise; prepare pinned Task; forward Task arguments |
| `mise.toml` / `mise.lock` | Pin native prerequisites and their platform downloads |
| `Taskfile.yml` | Provide installation, verification, development, and update commands |
| `scripts/` | Install skills and tools; merge host configuration; validate and recover changes |

Python is owned by uv. The Python version comes from [`piw/.python-version`](piw/.python-version),
not a second mise Python pin. Bootstrap needs no installed mise, Task, Python, or shell activation.
On Linux/macOS it needs curl or wget and sha256sum or shasum. On Windows it uses the built-in
PowerShell host. Tool installation also requires Git.

Prepare the development environment on Linux/macOS:

```bash
./bootstrap.sh
```

On Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

With no arguments, bootstrap runs `deps:install`: prepare the pinned native tools and synchronize
the piw development environment. It does not configure agents or require running Docker Sandboxes.
Arguments are forwarded to Task, including task variables and options:

```bash
./bootstrap.sh tools:install
./bootstrap.sh skills:install TARGET=codex
./bootstrap.sh install:dry-run TARGET=all
./bootstrap.sh install TARGET=all
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 tools:install
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 install TARGET=all
```

All mise state, native tools, and agent tool caches are kept under the ignored `.tools/` directory.
Bootstrap records the caller's directory in `LLMS_CALLER_CWD` before entering this checkout.
Host launchers must retain their calling project and worktree.

Use Task after setup. An existing Task executable can read this Taskfile; its commands select
this checkout's mise environment. Alternatively, add `.tools/bin` to your PATH for the generated
Task forwarding command, or continue using bootstrap with Task arguments. Bootstrap does not
change your shell profile or persistent PATH.

```bash
task tools:install
task skills:install TARGET=all
task agents:configure TARGET=all
task doctor
task --list
```

The default target is `all`: Codex, Claude, Pi, and OpenCode. Set `TARGET=codex`, `claude`, `pi`, or
`opencode` to select a host. `OUTPUT=json` requests machine-readable script reports.

| Task | Behavior |
|---|---|
| `deps:install`, alias `setup` | Prepare native prerequisites and piw's development environment |
| `tools:install` | Install pinned Serena, ast-grep, GitNexus, and local cq |
| `tools:run TOOL=... -- ...` | Run a local tool with its arguments in the caller's project or worktree |
| `skills:install TARGET=...` | Install managed skills and required external dependencies |
| `agents:configure TARGET=...` | Merge supported host integrations while preserving existing settings |
| `install TARGET=...` | Run preparation, tools, skills, configuration, and verification in order |
| `install:dry-run TARGET=...` | Preview actual tool, skill, and configuration changes |
| `doctor TARGET=...` | Report native/package versions and host configuration; distinguish configuration from live connections |
| `deps:versions` | Report selected native and agent tool versions |
| `deps:check` | Report available updates without changing pins |

`install:dry-run`, skill listing, and validation do not run dependency installation. Prepare the
runtime once with bootstrap before using them. Bootstrap itself may download mise and Task when
missing; it is not a preview command.

## Agent tools

| Tool | Main use |
|---|---|
| Serena | Find symbols and references through standard language servers |
| ast-grep | Search structural code patterns through the CLI |
| GitNexus | Query code maps, execution flows, and change impact |
| cq | Trial a local store of knowledge from previous debugging |
| Ponytail skills | Review changes and audit code using focused processes |

Native prerequisite versions belong to mise. Agent packages and external skill sources belong
to `agent-dependencies.json`; do not duplicate their pins in individual host configurations.
The npm lock at `agent-tools/package-lock.json` records their complete resolved dependencies.
After changing npm tool pins, run `task tools:lock` and review the lockfile before installation.
Reviewed Serena security overrides also live in `agent-dependencies.json`; uv installs them
with `--overrides` because Serena 1.7.0 otherwise pins older urllib3 and Werkzeug versions.
Serena's upstream metadata still reports those two exact-pin conflicts in `uv pip check`;
verify the reviewed versions and language-server behavior rather than treating that output as clean.
Use this canonical checkout for host launcher paths, then rerun `agents:configure` if it moves.
Managed Codex integrations use the standard `~/.codex` profile, matching the upstream installers.
A custom `CODEX_HOME` is rejected before setup; skills-only installation still supports custom destinations.

Configuration selects local transports for managed MCP entries and backs up their previous settings.
Unrelated servers and preferences are preserved. GitNexus's native installer owns bundled skills and
hook bodies; local launchers select pinned Node and separate storage for each project or worktree.
Doctor checks those launchers separately from live hook execution and client trust.
OpenCode setup preserves existing `opencode.jsonc` or legacy `config.json` files. JSONC
comments are retained by the locked upstream parser; before tool installation, its dry run
reports that source validation is pending. Project and runtime overrides still need a live
OpenCode check.

Serena must activate the project or worktree being inspected. When enabled, use GitNexus in
indexing-only mode so it does not inject instructions into project repositories. cq storage stays local.
Use documented integrations where the host supports them, and the CLIs otherwise; Pi does not
need an added MCP bridge. A successful package installation does not establish that a language
server, index, or host integration works. Check `doctor` and perform real queries in the selected
project before relying on them.

### Multiple repos, workspaces, and agents

The managed Serena setup uses a separate stdio connection for each agent session and
`--project-from-cwd` to select its current checkout. No repo names, repo list, fixed
project directory, or shared HTTP endpoint are written into host configuration. An agent
working from a projectless chat must activate the exact repo or worktree explicitly.

`task agents:configure` also merges these generic preferences into Serena's user-level
configuration, preserving other settings, registered projects, and comments:

```yaml
gui_log_window: false
web_dashboard: true
web_dashboard_open_on_launch: false
web_dashboard_interface: browser
```

The configuration lives in `~/.serena/serena_config.yml`, or under `SERENA_HOME` when
set. Setup records that selected home in the managed Serena launch environment so desktop
and CLI sessions read the same preferences. A conflicting existing host override is
rejected before changes; select its existing home explicitly rather than silently
switching data directories. Changes use the existing private backup and atomic update
process. Dry runs preview them without writes, and `doctor` checks both preferences and
host launch arguments.
New sessions keep a local dashboard available without launching native windows, tray
icons, or browser tabs. Open a dashboard on demand through Serena's `open_dashboard`
tool or its logged localhost URL. Existing sessions retain their startup settings.

This follows [Serena's multiple-project guidance](https://oraios.github.io/serena/02-usage/040_workflow.html).
Separate repos and worktrees need independent project state. HTTP sharing is useful when
every connected agent deliberately uses the same checkout; a single global endpoint can
switch the active project underneath other agents. The browser interface is supported
across platforms; the pinned release labels its shared tray manager experimental.
See [dashboard settings](https://oraios.github.io/serena/02-usage/060_dashboard.html).

Run installed CLIs through Task without adding their package caches to global PATH:

```bash
task tools:run TOOL=ast-grep -- --version
```

From another project, call this checkout's bootstrap by its absolute path with the same Task
arguments. `tools:run` uses `LLMS_CALLER_CWD` for that project or worktree and forwards the tool's
exit code. It does not install or configure anything.

GitNexus is enabled for the current personal noncommercial trial. Its PolyForm Noncommercial
license limits anticipated commercial application; source privacy does not change those terms.
Commercial licensing is available from its maintainers. Before adopting it for commercial work,
resolve that license. Index with `--index-only`; the managed environment stores isolated indexes
under `.tools/agent-tools/gitnexus-indexes`, outside the inspected project.

Repo builds, tests, CI, and contributor setup do not depend on these LLM tools. Keep their
installation and configuration here. Optional project guidance checks also belong here.

## Development

```bash
task test
task check
task ci
```

`task test` runs piw's application tests without live Docker Sandboxes.
`task check` adds formatting, lint, typing, coverage, and actual skill validation.
`task ci` also builds piw and smoke-tests the installed wheel. Project-specific commands remain
available under `piw:` and `skills:`.

For native tool pin changes, edit `mise.toml`, then refresh `mise.lock` with the project-local mise
binary. `vars.mise_version` selects the bootstrap release. Keep exact pins and reviewed lockfile
changes; `deps:check` reports updates without applying them.

## Managed skills

The installer validates managed source before changing a target. It stages each skill, compares
source and staged digests, backs up changed live copies outside skill discovery, and restores
previous copies if promotion fails. It also moves managed legacy `*.backup-*` folders out of
skill discovery to prevent duplicate names.

External required skills are fetched from the pinned upstream sources declared in the dependency
manifest. Upstream tool installers own their bundled skills and integrations; avoid maintaining
competing copies. Skill validation reports required source dependencies. Doctor reports package
and host configuration state; live client connections and skill use require separate checks.

```bash
task skills:list
task skills:fetch
task skills:validate
task skills:test
task skills:dry-run TARGET=codex
task skills:install TARGET=codex
```

Existing `skills:install:codex`, `skills:install:claude`, `skills:install:pi`, and their dry-run
commands remain available. OpenCode has matching target-specific commands.

`skills:fetch` prepares verified external source caches without changing live skills.
`skills:validate` is offline and reports required source caches that are missing or invalid.
`skills:check` fetches dependencies before validation. Live installation prepares
external dependencies before changing a skill target.

Use [skill behavior checks](tests/skill-evals.md) to evaluate selection and workflow changes.
Structural validation proves packaging constraints; it does not establish agent performance.
Setup scripts are checked by running them. `skills:test` retains the existing optional
Git cleanup safety checks for changes to that script; it is outside the normal setup gate.

The direct installer remains available through `scripts/install_skills.py`; run it with the
uv-managed Python version. `scripts/run_install_skills.ps1` is a compatibility wrapper for an
already available Python runtime. Use root bootstrap for first-time setup.

For recovery, keep installer and configuration reports with `OUTPUT=json`; they identify
backup paths and failed verification. Fix the reported prerequisite before retrying. A moved
checkout needs `agents:configure` again so host launchers point to the current location. To
restore an earlier managed skill revision, check out that reviewed revision here and rerun
`skills:install`; retain the external backups until the restored skills are verified.

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
