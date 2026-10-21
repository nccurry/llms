### C# and .NET

- Pin the SDK in `global.json`. Keep package versions in
  `Directory.Packages.props` and shared settings in `Directory.Build.props`.
- Keep nullable reference types on. Fix warnings instead of suppressing them.
- Follow `.editorconfig` for naming and style. Avoid placeholder names such as
  `Manager`, `Service`, `Data`, or `Info`.
- Document public members with XML docs; let analyzers enforce it.
- Pass `CancellationToken` through async calls. Use `ConfigureAwait(false)` in
  library code.
- Prefer a plain loop over a long multi-line LINQ chain.
- Mark tests that need live services with a category, such as
  `[Trait("Category", "Live")]`, so normal runs skip them.
