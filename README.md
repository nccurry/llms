# LLM Tools and Skills

This repository contains two related, provider-neutral tools:

- `piw`, a Linux CLI for persistent [Pi](https://pi.dev/) coding sessions in isolated
  Docker Sandboxes.
- A curated collection of Agent Skills with an installer for Codex, Claude, and Pi.

## piw

`piw` gives each task a persistent Docker Sandbox, private writable clone, dedicated branch,
Pi session, and configurable read-only reference directories. The host checkout remains
untouched. A task can push through the forwarded host SSH agent and use MCP servers that were
registered with Docker Sandboxes.

### Requirements

- Linux
- [uv](https://docs.astral.sh/uv/)
- Python 3.14, which uv can install automatically
- Git
- Docker Sandboxes (`sbx`) with clone-mode support
- An SSH key loaded in the host SSH agent if the task will push

### Install and run

From a checkout:

```bash
uv sync --locked
uv run piw --help
```

The repository also contains an executable uv-script launcher:

```bash
./piw --help
```

Install the command directly from Git:

```bash
uv tool install git+https://github.com/nccurry/llms
piw --help
```

### Typical workflow

```bash
piw init
piw config edit
piw doctor --live

cd /path/to/repository
piw start fix-exporter-metrics

# Later:
piw list
piw status fix-exporter-metrics
piw resume fix-exporter-metrics

# Preserve the sandbox but release resources:
piw stop fix-exporter-metrics --yes

# After the branch is pushed or unchanged:
piw clean fix-exporter-metrics --dry-run
piw clean fix-exporter-metrics --yes
```

Inside Pi, ask the agent to commit, push, create the merge/pull request with its configured MCP
or CLI, monitor CI and review feedback, and address findings. `piw` deliberately does not encode
GitLab, GitHub, or another hosting provider's API.

### Commands

| Command | Purpose |
|---|---|
| `piw init` | Create a neutral user configuration. |
| `piw doctor` | Check host, sandbox, model, skill, SSH, template, and MCP readiness. |
| `piw start TASK` | Create a private task clone and attach Pi. |
| `piw resume TASK` | Continue the task's latest Pi session. |
| `piw list` | Reconcile saved tasks with live sandboxes. |
| `piw status TASK` | Show task, branch, recovery, and cleanup state. |
| `piw shell TASK` | Open a shell in the task clone. |
| `piw exec TASK -- COMMAND...` | Run a captured non-interactive command. |
| `piw stop TASK` | Stop the sandbox without deleting it. |
| `piw clean TASK` | Safely remove a task sandbox and local record. |
| `piw config path\|show\|validate\|edit` | Manage user configuration. |
| `piw template status\|ensure\|rebuild\|prune` | Manage reusable Pi templates. |

Data-producing commands accept `--output json`. In JSON, `ok` matches the process result; failed
doctor checks and nonzero `piw exec` commands set it to `false` while retaining diagnostics in
`data`. Put wrapper options before the forwarded command delimiter:

```bash
piw --output json exec TASK -- git status --short
```

Mutating commands support `--dry-run`, `--yes`, or `--batch` as appropriate. Long help includes an
`AI_CONTEXT` section and stable exit codes.

### Configuration

`piw init` creates `~/.config/piw/config.toml`. CLI flags override this file. Repository-local
configuration is intentionally not loaded because an untrusted checkout could otherwise inject
host mounts, extensions, profiles, or MCP servers.

```toml
config_version = 1

[sandbox]
# profile = "your-governance-profile"
read_only_refs = ["~/projects/reference-code"]
mcp_servers = []
mcp_gateway_url = "http://mcp-gateway.docker.internal/mcp"
cpus = 0
# memory = "8g"
timeout_seconds = 600

[pi]
package = "@earendil-works/pi-coding-agent@0.84.0"
# model = "provider/model"
thinking = "high"
extensions = []
# models_file = "~/.pi/agent/models.json"
# settings_file = "~/.pi/agent/settings.json"
skill_paths = ["~/.pi/agent/skills"]

[template]
prefix = "piw-pi"
node_version = "v22.19.0"
```

Reference and skill paths are mounted read-only at the same absolute path inside the sandbox.
The primary repository is cloned privately and remains writable. Configure a broad reference
root when all content below that root is safe for agents to read. When that root contains the
active repository, `piw` expands it into disjoint sibling mounts so the broad reference cannot
make the nested private clone read-only. Files directly beside the active path are copied into the
sandbox as snapshots; editing those copies cannot affect the host files.

Pi does not include MCP support in its core harness. Add a reviewed, pinned MCP extension to
`pi.extensions`, register servers with `sbx mcp add`, authorize them with `sbx mcp auth`, then put
their aliases in `sandbox.mcp_servers`. Docker retains OAuth and secrets; `piw` only selects the
registered aliases and configures the sandbox gateway.

`piw` never reads or copies Pi `auth.json`, API keys, SSH private keys, or MCP secrets. Models and
settings files are accepted only as JSON metadata. Credential fields may contain a single
environment-variable reference such as `"apiKey": "$EXAMPLE_API_KEY"`; literal credential values
are rejected.

For a custom provider, store the real value in Docker Sandboxes and reference only its injected
placeholder from `models.json`:

```bash
sbx secret set-custom \
  --host api.example.com \
  --env EXAMPLE_API_KEY \
  --value "$EXAMPLE_API_KEY"
```

Docker injects a generated placeholder into each sandbox and replaces it only on requests to the
configured host. `piw start` also asks the template's installed Pi version to validate copied model
and settings metadata before it saves task state.

### Development

```bash
task piw:sync
task piw:check
task piw:build
```

The implementation uses Python 3.14, the standard library, strict Pyright, Ruff, pytest, and the
native uv build backend. Runtime code has no Python package dependencies.

## Managed Agent Skills

The `skills/` directory is the source for the managed Codex, Claude, and Pi skills.

## Commands

List the managed skills and install targets:

```powershell
task skills:list
```

Run the installer tests and skill validation:

```powershell
task skills:test
task skills:validate
```

Preview a Codex installation before you change live skills:

```powershell
task skills:dry-run:codex
```

Install the managed skills for Codex:

```powershell
task skills:install:codex
```

Preview or install the managed skills for Pi:

```powershell
task skills:dry-run:pi
task skills:install:pi
```

Use `task skills:dry-run` or `task skills:install` only when you want every target.

## Installation Behavior

The installer validates the complete managed source before it changes a target. It stages each skill and compares its source digest with the staged digest.

When a live skill changes, the installer moves the old copy to an external backup directory. Codex backups use `~/.codex/skill-backups/<timestamp>/codex/`. Claude backups use `~/.claude/skill-backups/<timestamp>/claude/`. Pi backups use `~/.pi/agent/skill-backups/<timestamp>/pi/`.

The installer also moves managed legacy `*.backup-*` directories out of each skill discovery directory. This migration prevents an agent from discovering duplicate skill names.

If promotion fails, the installer restores the prior live skill. Use `--output json` to record actions, backup paths, digests, and verification results.

## Direct Usage

The PowerShell wrapper selects an available Python runtime:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_install_skills.ps1 --command install --target pi --dry-run --output json
```

Pi installs to `~/.pi/agent/skills` by default. Set `CODEX_SKILLS_DIR`, `CLAUDE_SKILLS_DIR`, or `PI_SKILLS_DIR` to override a default target. You can also use `--codex-dir`, `--claude-dir`, or `--pi-dir`.
