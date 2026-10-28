# Dependency check (one other repository)

Use this as the prompt for a subagent, or follow it yourself, for each
repository the PLC waits on. Fill in the placeholders.

---

Check whether a dependency is already delivered. Only read: you may run
`git fetch`, but do not edit files, commit, check out, pull, merge, or push.

- Repository: `<path or remote URL>`
- Target branch: `<usually main>`
- What the plan waits for: `<feature, function, API, or ticket ID>`
- How the plan describes it: `<quote from the packet>`

Steps:

1. Run `git -C <path> fetch --quiet origin`. If the path is not available
   locally, use `git ls-remote <url>` and the host's PR/MR tools instead.
2. Look on `origin/<target>`, not the local branch, for the dependency:
   - `git -C <path> log origin/<target> --oneline --grep "<ticket or name>"`
   - `git -C <path> grep -n "<symbol>" origin/<target>`
   - Its PR/MR state through `gh` or `glab`, when a host login works.
3. If it is not on the target branch, look for an open branch or PR/MR that
   adds it.

Reply in this form:

```text
Dependency: <name>
State: delivered | in review | in progress | not started | unknown
Evidence: <commit, PR/MR, or file and line on origin/<target>, with the commit checked>
Local checkout behind origin: <yes, N commits | no | not checked>
Unknown: <anything you could not check, and why>
```

Report what you found, not what the plan expects. Say "unknown" rather than
guessing.
