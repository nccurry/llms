# GitLab issues notes

| Need | Command |
| --- | --- |
| Read an issue | `glab issue view 42` |
| Search before creating | `glab issue list --search "config reload" --all` |
| Create | `glab issue create --title "<title>" --description "<text>"` |
| Comment | `glab issue note 42 --message "<text>"` |
| Close | `glab issue close 42` |
| Set an MR title or description | `glab mr update <number> --title "<title>" --description "<text>"` |

- `Closes #42` in an MR description closes the issue when the MR merges
  into the default branch, unless the project turned that off. Use
  `Related to #42` for partial work.
- A GitLab project can also use an external tracker such as Jira; then the
  key form and status changes follow that tracker.
- Read the issue after the merge: if GitLab already closed it, don't close
  it again.
