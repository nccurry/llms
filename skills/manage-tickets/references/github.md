# GitHub issues notes

| Need | Command |
| --- | --- |
| Read an issue | `gh issue view 42 --json state,title,body,url` |
| Search before creating | `gh issue list --state all --search "config reload in:title"` |
| Create | `gh issue create --title "<title>" --body-file <file>` |
| Comment | `gh issue comment 42 --body-file <file>` |
| Close | `gh issue close 42 --comment "<why>"` |
| Set a PR title or body | `gh pr edit <number> --title "<title>" --body-file <file>` |

- Closing keywords and partial work: see [the skill](../SKILL.md#4-act-on-the-event).
- Read the issue after the merge: if GitHub already closed it, don't close
  it again.
