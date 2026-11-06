# Setup Tooling Fixtures

Stable inputs and expected results for the checks in [SRD.md](SRD.md). All
names, paths and values are invented. Results go under their phase in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Fixture Inventory

| ID | Area | Input and conditions | Expected result | Requirements |
| --- | --- | --- | --- | --- |
| FIX-001 | Claude home | `~/.claude.json` with a user MCP server, a `projects` map and an account-shaped object of fake values; `~/.claude/settings.json` with a user `PostToolUse` hook, a user env key, and `enabledPlugins` | After setup: user server, `projects`, account object, user hook and env key unchanged; managed servers, env `PATH` and hooks match golden files | REQ-014, REQ-015 |
| FIX-002 | Codex home | `~/.codex/config.toml` with comments, a profile table and a user MCP server; `~/.codex/hooks.json` with a shell-form GitNexus hook at mode 0664 | Comments, profile and user server kept; one GitNexus post-commit hook; Serena hooks added; file mode 0644 (POSIX) | REQ-014, REQ-015 |
| FIX-003 | OpenCode home | `~/.config/opencode/opencode.jsonc` with comments and two user MCP servers; no `opencode.json` | Comments and user servers kept; managed servers added; no `opencode.json` left after setup | REQ-014, REQ-015 |
| FIX-004 | Pi home | `~/.pi/agent/AGENTS.md` with user text; `~/.pi/agent/settings.json` with a user `shellCommandPrefix` | User text and prefix kept; cq block and `CQ_ADDR` prefix present | REQ-014, REQ-015 |
| FIX-005 | Fake executables | In a fake `TOOLS` folder: `serena` (handles `setup` and `--version`), `serena-hooks`, `cq` (handles `install`), a GitNexus entry script run by Node (handles `setup` and `--version`), `ast-grep`, and a stand-in for Serena's environment Python that answers version and config-render calls. Installer commands replace MCP server entries, append a shell-form hook, and create a server-only `opencode.json`, as the real installers do | Setup restores only server sections and removes the created file | REQ-014, REQ-015 |
| FIX-006 | Golden output | The files FIX-001 to FIX-004 should become after one `configure("all")`: `~/.claude.json`, `~/.claude/settings.json`, `~/.codex/config.toml`, `~/.codex/hooks.json`, `~/.codex/AGENTS.md`, `~/.config/opencode/opencode.jsonc`, `~/.config/opencode/AGENTS.md`, `~/.pi/agent/AGENTS.md`, `~/.pi/agent/settings.json`, and `~/.serena/serena_config.yml`. Paths are stored as placeholders (`{HOME}`, `{TOOLS}`, `{REPO}`, `{NODE_DIR}`, `{UV_DIR}`, `{TASK_DIR}`, `{CLIENT_DIR}`) | Match after placeholder substitution after the first run; no file's bytes or mode change in the second run | REQ-015, REQ-016 |
| FIX-007 | Windows quoting | Paths `C:/Program Files/Tools/node.exe` and `C:/Users/O’Brien/My 'Repos'/llms` (U+2019 and ASCII quotes) | PowerShell parses each encoded command back to the exact paths; `cmd` command lines quote spaces | REQ-011, REQ-012 |
| FIX-008 | PowerShell 5.1 known failures | Two short `.ps1` samples, added in a scratch worktree: one using the `??` operator, one calling `Get-Content -AsByteStream` | `lint:powershell` exits non-zero naming `PSUseCompatibleSyntax` and `PSUseCompatibleCommands` | REQ-008 |
| FIX-009 | Python lint known failure | An unused `import os` added to an in-scope script in a scratch worktree | `check` and `ci` each exit non-zero naming the file and F401 | REQ-004 |
| FIX-010 | Host scenarios | Seed variants under `tests/fixtures/configure/scenarios/`: `CODEX_HOME` elsewhere; a different Serena home; Claude cq plugin with an old managed cq entry; a foreign cq entry; `opencode --version` 2.x; no `claude` CLI; `serena setup` not functional; a user-owned `opencode.json` | Exit code and message for the two rejections and the conflict (nothing written); golden files for the rest, including the dropped-key report, the `mcp.servers` layout and the limitation texts | REQ-015, REQ-016 |
