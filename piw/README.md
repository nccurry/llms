# piw

`piw` runs Pi in isolated Docker Sandboxes. A branch session has a persistent private clone,
dedicated Git branch, and resumable Pi conversations. A chat session has a persistent empty
workspace and resumable conversations without a repository. Add `--temporary` when a chat should
be discarded as soon as Pi exits. Both workflows support configurable read-only references,
skills, models, secrets, extensions, and MCP servers.

### Requirements

- Windows 11 (x86-64) or Linux
- [uv](https://docs.astral.sh/uv/)
- Python 3.14, which uv can install automatically
- Git for branch sessions
- Docker Sandboxes (`sbx`) with clone-mode support
- An SSH key loaded in the host SSH agent if a branch session will push

### Install and run

From a checkout:

```bash
cd piw
uv sync --locked
uv run piw --help
```

On POSIX hosts, the repository also contains an executable uv-script launcher:

```bash
./piw --help
```

Install the current checkout from the repository root. `--no-cache` ensures local source changes are
included when reinstalling the same package version:

```bash
uv tool install --force --no-cache ./piw
piw --help
```

Use the installed `piw` command on Windows; the extensionless `./piw` launcher is POSIX-only.

Install the command directly from Git:

```bash
uv tool install 'git+https://github.com/nccurry/llms#subdirectory=piw'
piw --help
```

### Typical workflow

```bash
piw init
piw config edit
piw secrets status
piw secrets sync --dry-run
piw secrets sync
piw doctor --live

cd /path/to/repository
piw branch fix-exporter-metrics

# If the host checkout is dirty, choose one explicit policy:
piw branch clean-commit-only --ignore-host-changes
piw branch include-local-work --carry-host-changes

# Continue an existing local branch or review a fetched remote-tracking branch:
piw branch continue-metrics --existing feature/metrics
git fetch origin
piw branch review-metrics --existing origin/feature/metrics

# Later:
piw list
piw status fix-exporter-metrics
piw attach fix-exporter-metrics

# Start a separate Pi conversation in the same sandbox and working tree:
piw attach fix-exporter-metrics \
  --new reviewer \
  --model provider/reviewer-model \
  --prompt "Review the current changes. Do not modify files."

# Preserve the sandbox but release resources:
piw stop fix-exporter-metrics --yes

# After the branch is pushed or unchanged:
piw clean fix-exporter-metrics --dry-run
piw clean fix-exporter-metrics --yes

# For persistent repository-free research:
piw chat architecture-research
piw attach architecture-research

# For a repository-free conversation that disappears on exit:
piw chat --temporary
```

Inside Pi, ask the agent to commit, push, create the merge/pull request with its configured MCP
or CLI, monitor CI and review feedback, and address findings. `piw` deliberately does not encode
GitLab, GitHub, or another hosting provider's API.

`piw chat NAME` does not inspect or clone the current directory. It creates an empty writable
workspace under `~/.local/state/piw/chats/NAME`, exposes the configured references and skills
read-only, and retains the workspace, sandbox, and Pi conversation. It works with the same
`attach`, `status`, `shell`, `exec`, `stop`, and `clean` commands as a branch session. Use
`--temporary` to discard all chat resources on exit; the name is optional in that mode. One-off
overrides use the same flags as branch sessions:

```bash
piw chat research --ref ~/notes --model provider/model --thinking high
piw chat research --batch
piw chat --temporary
piw chat scratch --temporary
piw chat research --dry-run --output yaml
```

`--batch` creates a persistent chat without attaching Pi. It cannot be combined with
`--temporary`, because an unattached temporary sandbox would be unreachable.

`piw attach NAME` launches Pi in the existing workspace for either session type. It continues the
latest conversation by default. `--new CONVERSATION` starts a separate saved conversation in that
same sandbox and working tree; combine it with `--model`, `--thinking`, or `--prompt` for an
independent reviewer or specialist. These overrides apply only to that attachment. `--select`
opens Pi's saved-conversation picker. Attachments share writable files, so avoid concurrent edits
unless the agents are deliberately coordinating.

### Commands

| Command | Purpose |
|---|---|
| `piw init` | Create a neutral user configuration. |
| `piw doctor` | Check host, sandbox, model, skill, SSH, template, and runtime-config readiness. |
| `piw branch NAME [--existing BRANCH]` | Create a new branch or adopt an existing branch in a persistent private clone. |
| `piw chat NAME` | Create a persistent repository-free workspace, then attach Pi. |
| `piw chat [NAME] --temporary` | Run a disposable repository-free chat and remove it on exit. |
| `piw attach NAME` | Continue the latest Pi conversation in a branch or chat session. |
| `piw attach NAME --new CONVERSATION` | Start a separate conversation in the same sandbox and working tree. |
| `piw attach NAME --select` | Open Pi's saved-conversation selector for the session. |
| `piw list` | Reconcile saved branch and chat sessions with live sandboxes. |
| `piw status NAME` | Show session, sandbox, and branch-specific Git state. |
| `piw shell NAME` | Open a shell in the session workspace. |
| `piw exec NAME -- COMMAND...` | Run a captured non-interactive command. |
| `piw stop NAME` | Stop the sandbox without deleting it. |
| `piw clean NAME` | Remove a persistent session; branch work is protected by Git safety checks. |
| `piw secrets status\|sync` | Reconcile declared environment variables with Docker's scoped secret store. |
| `piw config path\|show\|validate\|edit` | Manage user configuration. |
| `piw template status\|ensure\|rebuild\|prune` | Manage reusable Pi templates. |

Text output uses compact tables for record lists and indented sections for nested details.
Data-producing commands also accept `--output json` or `--output yaml`; both structured formats use
the same versioned envelope. In that envelope, `ok` matches the process result. Failed doctor checks
and nonzero `piw exec` commands set it to `false` while retaining diagnostics in `data`. Put wrapper
options before the forwarded command delimiter:

```bash
piw --output json exec NAME -- git status --short
piw list --output yaml
```

Mutating commands support `--dry-run`, `--yes`, or `--batch` as appropriate. Long help includes an
`AI_CONTEXT` section and stable exit codes.

`piw branch` fails closed when the host repository has staged, unstaged, or untracked changes. Use
`--ignore-host-changes` to create the branch session strictly from the selected commit, or
`--carry-host-changes` to recreate the final working-tree contents in the private clone. The two
flags are mutually exclusive, ignored files are never carried, and unresolved merge conflicts are
always rejected. Carrying changes flattens staged and unstaged state into ordinary unstaged branch
changes. `--dry-run --output json` reports the selected policy and affected paths.

Use `piw branch NAME --existing BRANCH` to start a session at the exact commit of an existing
branch instead of creating `piw/NAME`. A local branch uses its existing name and upstream. An
explicit remote-tracking ref such as `origin/feature/metrics` becomes a local
`feature/metrics` branch that tracks the remote ref. `piw` does not fetch or change host Git refs;
run `git fetch REMOTE` first when a remote-tracking branch is missing or stale. Local branch names
take precedence over same-named remote shorthand; use a full `refs/remotes/REMOTE/BRANCH` ref to
force the remote selection. `--existing` cannot be combined with `--base` or `--branch`.

Existing-branch dry runs expose `mode`, `source_ref`, `base_commit`, `branch`, and `upstream` in
JSON or YAML. Host change policies work the same way as new branches: the default fails closed,
`--ignore-host-changes` uses only committed state, and `--carry-host-changes` applies the current
working-tree patch to the adopted commit inside the sandbox.

### Configuration

`piw init` creates `~/.config/piw/config.toml`. CLI flags override this file. Repository-local
configuration is intentionally not loaded because an untrusted checkout could otherwise inject
host mounts, extensions, profiles, or runtime configuration.

```toml
config_version = 1

[sandbox]
# profile = "your-governance-profile"
read_only_refs = ["~/projects/reference-code"]
cpus = 0
# memory = "8g"
timeout_seconds = 600

[[sandbox.secrets]]
source_env = "EXAMPLE_PROVIDER_TOKEN"
sandbox_env = "EXAMPLE_API_KEY"
hosts = ["api.example.com"]
placeholder = "example-{rand}"
required = true

[pi]
package = "@earendil-works/pi-coding-agent@0.84.0"
# model = "provider/model"
thinking = "high"
extensions = []
# models_file = "~/.pi/agent/models.json"
# settings_file = "~/.pi/agent/settings.json"
# mcp_file = "~/.pi/agent/mcp.json"
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

Pi does not include MCP support in its core harness. Install a reviewed, pinned MCP client extension
with `pi.extensions`, then point `pi.mcp_file` at that extension's ordinary non-secret JSON config.
`piw` validates and copies the file to `~/.pi/agent/mcp.json` when it creates a session; it does not
register servers with Docker or reinterpret the extension's schema. The same file can therefore use
public HTTP, OAuth, or stdio servers supported by the selected extension:

```json
{
  "settings": {
    "maxRetries": 10
  },
  "mcpServers": {
    "remote-tools": {
      "transport": "streamable-http",
      "url": "https://mcp.example.com/mcp",
      "auth": { "type": "oauth" },
      "lifecycle": "lazy"
    },
    "local-tools": {
      "transport": "stdio",
      "command": "example-mcp-server",
      "args": ["serve"],
      "lifecycle": "lazy"
    }
  }
}
```

With `pi-mcp-extension`, keep OAuth servers lazy and run `/mcp:auth remote-tools` after Pi
starts. The command opens one browser tab, waits up to five minutes for the callback, and starts the
server after authentication. An unauthenticated eager server instead treats the OAuth redirect as a
failed connection and opens another tab on every retry. `maxRetries` extends recovery from ordinary
connection failures; it does not extend the OAuth callback window.

Remote endpoints must be allowed by the active sandbox network policy. A stdio command runs inside
the sandbox, so install it in the reusable template or make it available in the workspace; host-only
commands are intentionally unavailable. Use the MCP extension's own status and authentication
commands inside Pi. OAuth state is sandbox-local and persists until a persistent branch or chat
session is cleaned. A temporary chat discards OAuth state with the rest of its sandbox on exit.
Do not put bearer tokens, client secrets, or other literal credentials in `mcp.json`.

`piw` never copies Pi `auth.json`, SSH private keys, MCP auth state, or literal credentials from
runtime metadata. Models, settings, and MCP files are accepted only as JSON metadata. Credential
fields may contain a single environment-variable reference such as
`"apiKey": "$EXAMPLE_API_KEY"`; literal credential values are rejected.

For a custom provider, export its credential on the host and declare the source variable, sandbox
variable, and exact outbound hosts under `[[sandbox.secrets]]`. The source and sandbox names may
differ, which is useful when a workstation already uses a provider-specific variable:

```bash
export EXAMPLE_PROVIDER_TOKEN="..."
piw secrets status
piw secrets sync --dry-run
piw secrets sync
```

`piw` feeds the real value to `sbx secret set-custom` over standard input, never a process argument.
Docker injects a generated placeholder into each sandbox and replaces it only on requests to the
declared hosts. `piw` stores only the concrete placeholder and a SHA-256 fingerprint under
`~/.local/state/piw/secrets.json`; it never persists the credential value. A matching fingerprint
is skipped, rotation reuses the placeholder so running sandboxes continue working, and external
secret-store drift is repaired on the next sync. Missing required variables fail closed; optional
declarations use `required = false`.

`piw branch`, `piw chat`, and `piw attach` automatically perform the same synchronization before
launching Pi. Branch and chat creation also ask the template's installed Pi version to validate
copied model and settings metadata before starting the session.

### Development

From the repository root, use the namespaced tasks:

```bash
task piw:test
task piw:check
task piw:test:package
```

From `piw/`, the same tasks are available without the `piw:` prefix. Normal tests use deterministic
subprocess fakes and require neither Docker nor network access. The live lifecycle test is separate
because it creates and removes a real sandbox and may download or build the reusable Pi template:

```bash
task piw:test:live
```

The live test uses the sandbox profile from the user configuration. Set `PIW_LIVE_PROFILE` to
override it in CI. It deliberately ignores configured providers, secrets, MCPs, references, and
skills.

`task piw:ci` runs the complete piw gate: lockfile validation, formatting, lint, strict typing,
tests, branch coverage, package build, and an isolated installed-command smoke test. The
implementation uses Python 3.14, strict Pyright, Ruff, pytest, PyYAML, and uv's native build
backend.
