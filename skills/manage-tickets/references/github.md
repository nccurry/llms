# GitHub issues notes

| Need | Command |
| --- | --- |
| Read an issue | `gh issue view 42 --json state,title,body,url` |
| Search before creating | `gh issue list --state all --search "config reload in:title"` |
| Create | `gh issue create --title "<title>" --body-file <file>` |
| Comment | `gh issue comment 42 --body-file <file>` |
| Close | `gh issue close 42 --comment "<why>"` |
| Set a PR title or body | `gh pr edit <number> --title "<title>" --body-file <file>` |

- `Closes #42`, `Fixes #42` or `Resolves #42` in a PR body closes the issue
  when the PR merges into the default branch only. A PR into another
  branch does not close it.
- For a PR that delivers only part of an issue, write `Refs #42` or
  `Part of #42`, which link without closing.
- Read the issue after the merge: if GitHub already closed it, don't close
  it again.
