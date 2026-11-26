"""Build a discovery fixture with a stale TODO."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import current_work, destination, expect, make_repo, packet, snapshot

dest = destination()
files = packet(
    "explicit-reload",
    "Explicit config reload",
    "Read a new file only when the caller explicitly reloads.",
    current_work(
        last_updated="2026-11-26",
        next_action="Run P1 discovery.",
        current_state="P1 is selected. The old process-wide cache was removed.",
        more_keys=["Selected work: P1, CONF-001. Discovery only."],
    ),
    [("P1", "Read on explicit reload", "Planned", "- Requirements: CONF-001")],
    "| ID | Requirement | Check |\n"
    "| --- | --- | --- |\n"
    "| CONF-001 | An explicit reload reads the new file contents. | "
    "Change the file, call reload, and confirm the new value is returned. |",
    log=["2026-11-26 Created."],
)
checkout = make_repo(
    dest,
    "reload",
    {
        **{
            path.replace("docs/plans/", "docs/plans/in-progress/", 1): body
            for path, body in files.items()
        },
        "config.py": '''"""Load the active config."""

# TODO (old cache rollout): restore the process-wide cache and TTL.
def reload(path, current):
    return current
''',
        "docs/config.md": "# Config\n\nThe process-wide cache and TTL were retired. "
        "Callers own the active value. An explicit reload should read the current file.\n",
    },
)
snapshot(dest, [checkout])
expect(dest)
print(dest)
