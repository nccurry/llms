### Go

- Use the Go version in `go.mod`; keep tool pins in `mise.toml`.
- Return errors with context (`fmt.Errorf("load config: %w", err)`). Never
  hide an error with `_ =`.
- Log with `log/slog`. Never log secrets or credentials.
- Put tests in `_test.go` files next to the code they test. Use table tests
  for contract cases.
- Define small interfaces where they are used. Do not add a shared `utils`
  package.
- Format with gofumpt and goimports through the task runner.
- Every linter suppression names the rule and gives a reason.
