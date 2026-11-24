Grade the plan against the user's request and the fixture's repository
context.

- It is a one-file plan under docs/plans/planned/plc-<slug>.md, with @alex
  as owner.
- It covers the limit behavior in both harbor's CLI and the admin console,
  with checks for both.
- Its top-level Code repositories section is outside Current Work and before
  Log. It contains exactly the two repository-root URLs from
  docs/code-repositories.md, one bare URL per unordered-list bullet.
- It does not use board aliases or change code.

The fixture checker enforces packet shape, strict lint and the exact URL list.
Judge whether the plan explains the user's requested behavior and checks
clearly.
