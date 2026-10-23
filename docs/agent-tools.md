# Agent tools

[Back to the README](../README.md#agent-tools).

For installation commands, see [Set up a computer](../README.md#set-up-a-computer).

- [Versions and dependency updates](#versions-and-dependency-updates)
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
these with `--overrides` because Serena 1.7.0 pins older urllib3 and Werkzeug versions.
`uv pip check` still reports those two version conflicts. Check the reviewed versions
and language-server behavior; record the conflicts when reporting the result.

## Agent configuration

Agent launchers point to this checkout. If it moves, rerun `agents:configure`.
Managed Codex tools use `~/.codex`. Setup rejects a custom `CODEX_HOME` before making
changes; skills-only installation still supports custom destinations.

Setup uses local connections for managed MCP servers, backs up their previous
settings, and keeps unrelated servers and preferences.

GitNexus's installer manages its bundled skills and hooks. Local launchers use the
pinned Node version and separate storage for each project or worktree. Stale-index
reminders run the pinned CLI. `doctor` checks launchers; test hooks and client trust
in the agent app.

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
configure anything.

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
