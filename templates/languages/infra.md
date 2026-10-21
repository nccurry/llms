### Infrastructure (shell, containers, CI, Helm)

- Shell scripts use strict mode (`set -euo pipefail`).
- Never ignore a failed checksum or signature check.
- Pin tool and image versions. Change them in one place and sync the rest.
- Keep Helm values, templates, example YAML, and CLI flags in agreement.
- Run containers that write into the repository as the invoking user, through
  the repository's wrapper when it has one.
- Ask before editing CI pipelines or the Taskfile when the change affects
  other contributors.
