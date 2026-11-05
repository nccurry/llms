# Jira notes

Commands differ between Jira CLIs; check `jira --help` for the one
installed. These match the common open-source `jira` CLI.

| Need | Command |
| --- | --- |
| Read a ticket | `jira issue view PROJ-123 --plain` |
| Search before creating | `jira issue list -q 'summary ~ "config reload"' --plain` |
| Create | `jira issue create -t Task -s "<summary>" -b "<body>" --no-input` |
| Move | `jira issue move PROJ-123 "In Progress"` |
| Comment | `jira issue comment add PROJ-123 "<text>"` |

- The key's form is `<PROJECT>-<number>`; take the project prefix from the
  rules or from existing keys, never from a guess.
- A Jira project linked to the code host may move tickets itself when an
  MR that names the key opens or merges, or on smart-commit words such as
  `PROJ-123 #done`. Read the ticket's state first, and write only what
  that automation did not do.
- Without a CLI, an MCP server for Jira may offer the same reads and
  writes.
