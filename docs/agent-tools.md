# Agent tools

[Back to the README](../README.md#agent-tools).

For installation commands, see [Set up a computer](../README.md#set-up-a-computer).

- [Versions and dependency updates](#versions-and-dependency-updates)
- [Tool entries in agent-dependencies.json](#tool-entries-in-agent-dependenciesjson)
- [Agent configuration](#agent-configuration)
- [Check tools in a project](#check-tools-in-a-project)
- [Serena sessions and dashboards](#serena-sessions-and-dashboards)
- [Run a tool from any project](#run-a-tool-from-any-project)
- [GitNexus indexing and licensing](#gitnexus-indexing-and-licensing)
- [Project boundaries](#project-boundaries)

## Versions and dependency updates

Keep native tool versions in mise and agent package and external skill versions in
`agent-dependencies.json`. Host configurations should use those versions.
`agent-tools/package-lock.json` records the full npm dependency tree. After changing
npm tool versions, run `task tools:lock` and review the lockfile before installing.

Reviewed Serena security overrides also live in `agent-dependencies.json`. uv applies
these with `--overrides` because Serena 2.1.0 pins older filelock and Werkzeug versions.
`uv pip check` still reports those two version conflicts. Check the reviewed versions
and language-server behavior; record the conflicts when reporting the result.

## Tool entries in agent-dependencies.json

Each `tools.<name>` entry says how its tool is installed, so install, the command that
runs the tool, version checks, `task deps:check`, `tools:lock`, `doctor` and `tools:run`
all read the entry; the install, command, version and lock code in
`scripts/manage_agent_tools.py` names no tool. Every entry has `version`, `installer` and
`bin`, plus these fields for its installer:

| Field | Meaning |
| --- | --- |
| `installer` | `uv` (a Python package in its own environment), `npm` (a package in the shared npm folder, installed from `agent-tools/package-lock.json`) or `github-release` (an archive checked against `checksums`) |
| `bin` | The main program the tool installs |
| `extra_bins` | Optional list of other programs it installs, such as `serena-hooks`. Informational: nothing reads it, and host hooks name the programs they call |
| `package` | `uv` and `npm`: the package name (`@scope/name` is allowed for npm) |
| `python`, `dependency_overrides` | `uv`: the Python version of its environment, and optional reviewed `package: version` overrides |
| `runs_with` | `npm` only, required. `native` runs the file directly; `node` runs it with the pinned Node |
| `entry` | Required when `runs_with` is `node`; not allowed for other installers. The script path inside the package, used when the package is not installed yet |
| `source`, `release`, `checksums` | `github-release`: the GitHub repository URL; the download folder of the pinned tag (`.../download/<tag>`, the tag ending in `version`); SHA-256 per asset named `<bin>_<system>_<machine>.<ext>` |

Setup checks every entry when it reads the file and stops with a message such as
`tools:install: agent-dependencies.json tools.gitnexus.installer must be one of uv, npm, github-release`
before it downloads or writes anything. It also refuses names and paths that could leave
`.tools`: the tool name, `bin` and `extra_bins` must be plain names (letters, digits, `.`,
`_`, `-`, starting with a letter or digit); `package` must be a package name; `entry`
must stay inside the package; and `version`, `python` and override versions must look like
versions.

To add another tool that installs one of these ways, add its entry and, for `uv` or `npm`,
run `task tools:lock`. Install, `tools:run`, `doctor` and `deps:check` then work with no
code change, and `configure` requires every pinned tool to install cleanly. Connecting a
tool to each agent host is separate code in `scripts/manage_agent_tools.py`: `servers()`
for the MCP server entries, the per-host native setup steps (`register_serena`,
`set_up_gitnexus`, the cq install) and the hook helpers. A new way of installing needs a
new installer record in `INSTALLERS` in the same file.

## Agent configuration

Agent launchers point to this checkout. If it moves, rerun `agents:configure`.
Managed Codex tools use `~/.codex`. Setup rejects a custom `CODEX_HOME` before making
changes; skills-only installation still supports custom destinations.

Setup uses local connections for managed MCP servers, backs up their previous
settings, and keeps unrelated servers and preferences.

GitNexus's installer manages its bundled skills and hooks. Setup keeps its post-commit
stale-index reminder and removes its search hook, which reopened the graph database on
every Grep, Glob, and Bash call (about 0.9 s each); query the GitNexus MCP server instead.
Local launchers use the pinned Node version and separate storage for each project or
worktree, and give `analyze` a 4 GiB database buffer. Exclude large generated folders
from an index with the repository's `.git/info/exclude`.

Setup also adds Serena's hooks (`serena-hooks activate`, `remind`, and `cleanup`) to
Claude and Codex, so agents load Serena's tools and are reminded to use them during long
grep or file-read runs. Codex asks you to approve new hooks once with `/hooks`.

`doctor` checks launchers and hook entries; test hooks and client trust in the agent app.

OpenCode setup keeps existing `opencode.jsonc` or legacy `config.json` files and
preserves JSONC comments with the locked upstream parser. Before tool installation,
a dry run reports that source validation is pending. Check project and runtime
configuration overrides in OpenCode itself.

## Check tools in a project

Activate the project or worktree in Serena. Run GitNexus with `--index-only` to avoid
adding instructions to project repositories. cq stores its data locally.

Use the app's documented integrations where available, or run the CLI. Pi does not
need an extra MCP bridge. After installation, run `doctor` and try real queries in
the selected project to check language servers, indexes, and agent connections.

## Serena sessions and dashboards

Each agent session gets its own Serena stdio connection. `--project-from-cwd` selects
the current checkout. Setup leaves repository names and fixed project paths out of
agent configuration. In a chat with no project, activate the exact repo or worktree.

`task agents:configure` adds these user preferences while keeping other settings,
registered projects, and comments:

```yaml
gui_log_window: false
web_dashboard: true
web_dashboard_open_on_launch: false
web_dashboard_interface: browser
```

Preferences live in `~/.serena/serena_config.yml`, or under `SERENA_HOME` when set.
Setup records that home in the Serena launcher so desktop and CLI sessions use the
same settings. If an agent's existing override points elsewhere, setup stops before
making changes. Select that home explicitly to keep using it.

Setup backs up the configuration and replaces it atomically. Dry runs show changes
without writing files. `doctor` checks preferences and launcher arguments.

New sessions keep a local dashboard available without opening windows, tray icons,
or browser tabs. Open it with Serena's `open_dashboard` tool or its logged localhost
URL. Restart existing sessions to use changed startup settings.

Separate repos and worktrees need their own project state. A shared HTTP server can
switch the active project for every connected agent; use it only when all agents
are working in the same checkout. The browser interface works across platforms;
the pinned release marks its shared tray manager as experimental.
See Serena's [multiple-project guidance](https://oraios.github.io/serena/02-usage/040_workflow.html)
and [dashboard settings](https://oraios.github.io/serena/02-usage/060_dashboard.html).

## Run a tool from any project

Use Task to run installed CLIs without adding package caches to your global PATH:

```bash
task tools:run TOOL=ast-grep -- --version
```

From another project, call this checkout's bootstrap by its absolute path with the
same arguments. Bootstrap records your current folder in `LLMS_CALLER_CWD`.
`tools:run` runs there and returns the tool's exit code. It does not install or
configure anything. `TOOL` is any tool name in `agent-dependencies.json`; an unknown
name fails with the list of valid names.

## GitNexus indexing and licensing

GitNexus is enabled for a personal noncommercial trial. Its PolyForm Noncommercial
license restricts commercial use, including work on private source code. Resolve
commercial licensing with its maintainers before using it for commercial work.

Index with `--index-only`. Setup stores separate indexes under
`.tools/agent-tools/gitnexus-indexes`, outside the project being inspected.

## Project boundaries

Keep agent tool installation and configuration here. Project builds, tests, CI,
and contributor setup should work without these tools. Keep optional checks of
project agent guidance here too.
