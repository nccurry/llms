# Repository templates

Starting points for the agent instruction files in a new repository. Copy what
you need, fill in the `<...>` placeholders, and delete what does not apply.
These files are not skills and are not installed.
The `.template` names stop agents working in this repository from loading them
as real instructions; drop `.template` when you copy them.

| File | Copy to | Purpose |
| --- | --- | --- |
| [AGENTS.template.md](AGENTS.template.md) | `AGENTS.md` | Rules and commands every agent reads |
| [CLAUDE.template.md](CLAUDE.template.md) | `CLAUDE.md` | Makes Claude Code load `AGENTS.md` |
| [llms.template.txt](llms.template.txt) | `llms.txt` | Short map of the repository ([format](https://llmstxt.org/)) |
| [scoped-AGENTS.template.md](scoped-AGENTS.template.md) | `<folder>/AGENTS.md` | Extra rules for one folder |
| [languages/](languages/) | Paste into `AGENTS.md` | Rules for Go, Rust, .NET, or infrastructure |

## How the files fit together

- `AGENTS.md` is the only rulebook. Every other file points to it.
- `CLAUDE.md` contains only `@AGENTS.md`. Claude Code can read `AGENTS.md` on
  its own when no `CLAUDE.md` exists, but the import also works in sessions and
  versions that cannot. Prefer it to a symlink, which needs extra setup on
  Windows.
- `llms.txt` lists where things are. It does not repeat rules or track status.
- A folder's `AGENTS.md` adds rules for that folder. The closest one wins.

## Writing good instructions

- Keep each `AGENTS.md` under 200 lines. Longer files are followed less
  reliably.
- Be specific: "Run `task test` before committing" beats "test your changes".
- Add a rule only after a repeated mistake or for a fact an agent cannot
  easily find. Prefer a linter rule, test, or task when one can enforce it.
- Leave out status, dates, versions, and plan or ticket IDs. They go stale.
- Put multi-step procedures in skills or docs and link to them.
- Remove rules that no longer apply whenever you edit the file.
