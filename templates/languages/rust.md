### Rust

- Pin the toolchain in `rust-toolchain.toml` and commit `Cargo.lock`.
- Set dependency versions only in `[workspace.dependencies]`.
- Deny `unsafe_code`. If FFI needs `unsafe`, keep it in one crate.
- Do not use `unwrap`, `expect`, or `panic!` in production code. Return typed
  errors.
- Prefer `#[expect(lint, reason = "...")]` over `#[allow(lint)]`.
- Do not add a crate or a manager-style abstraction without a real boundary
  that needs it.
- Baseline checks: `cargo fmt --check`, `cargo clippy -- -D warnings`, and
  `cargo test`, run through the task runner.
