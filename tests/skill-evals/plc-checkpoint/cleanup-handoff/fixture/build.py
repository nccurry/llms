"""Released donors, a rejected bypass, a shared cache and unique ignored source."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import (
    add_worktree,
    commit,
    current_work,
    destination,
    expect,
    git,
    make_repo,
    packet,
    snapshot,
    write,
)

dest = destination()
app = make_repo(
    dest,
    "exporter",
    {
        ".gitignore": "__pycache__/\n*.py[cod]\ntarget/\n",
        "README.md": (
            "# Exporter\n\nThe current render PLC is in "
            "../exporter-wt/render/integration/docs/plans/render.\n"
        ),
        "src/check.py": "def supported(kind):\n    return kind == 'file'\n",
    },
)
integration = add_worktree(app, "render", "integration", "plc/render")
donor = add_worktree(app, "render", "donor", "plc/render-donor")
donor_head = commit(
    donor,
    "feat: render selected values",
    {"src/render.py": "def render(values):\n    return ','.join(values)\n"},
)
git(integration, "cherry-pick", "-x", donor_head)
accepted_head = git(integration, "rev-parse", "--short", "HEAD")
experiment = add_worktree(app, "render", "socket-trial", "plc/socket-trial")
write(experiment, {"src/check.py": "def supported(kind):\n    return True\n"})
pending = add_worktree(app, "render", "pending-patch", "plc/pending-patch")
write(
    pending,
    {
        "target/config.patch": (
            "--- a/src/check.py\n+++ b/src/check.py\n@@ -1,2 +1,2 @@\n"
            " def supported(kind):\n-    return kind == 'file'\n"
            "+    return kind in ('file', 'pipe')\n"
        )
    },
)
write(integration, {"target/cache/input.bin": "shared input for the next render check\n"})
for path, reason in [
    (donor, "ended-donor-session; keep until parent accepts render contribution"),
    (experiment, "ended-trial-session; keep until parent chooses the supported adapter"),
    (pending, "patch-review-session; keep until the user reviews target/config.patch"),
    (integration, "render-parent-session; shared cache needed by the next render check"),
]:
    git(app, "worktree", "lock", "--reason", reason, str(path))

commit(
    integration,
    "docs(plan): record child acceptance and remaining checks",
    packet(
        "render",
        "Render values",
        "Render selected file values and check the output.",
        current_work(
            last_updated="2026-11-17",
            next_action="run the remaining integration check using target/cache/input.bin",
            current_state=(
                "P1 accepted by cherry-pick into plc/render; donor released, owner ended. "
                "The socket trial was rejected and released; owner ended. Its only edit "
                "bypasses every supported-kind check and must not enter product source. "
                "The file adapter remains selected. P2 is still in progress; main delivery "
                "is pending. Keep all branch refs, the shared cache and the pending patch."
            ),
            checkouts=[
                (
                    "exporter-wt/render/integration",
                    "plc/render",
                    "render-parent-session",
                    "in progress",
                ),
                (
                    "exporter-wt/render/donor",
                    "plc/render-donor",
                    "ended-donor-session",
                    "accepted; released",
                ),
                (
                    "exporter-wt/render/socket-trial",
                    "plc/socket-trial",
                    "ended-trial-session",
                    "rejected; released",
                ),
                (
                    "exporter-wt/render/pending-patch",
                    "plc/pending-patch",
                    "patch-review-session",
                    "awaiting review",
                ),
            ],
        ),
        [
            (
                "P1",
                "Render values",
                f"Merged — accepted into plc/render @ `{accepted_head}`",
                "- Requirements: REN-001\n- Check: selected values are joined.",
            ),
            (
                "P2",
                "Check integrated output",
                "In progress",
                "- Requirements: REN-002\n- Check: integration test pending.",
            ),
        ],
        "| ID | Requirement | Acceptance |\n| --- | --- | --- |\n"
        "| REN-001 | Join selected file values. | `test_render` passes. |\n"
        "| REN-002 | Check the integrated output. | `test_output` passes. |\n",
        log=[
            "2026-11-17 Accepted the donor contribution into plc/render by cherry-pick; "
            "child released.",
            "2026-11-17 Rejected the socket trial and its private bypass; "
            "child released. Keep the file adapter.",
        ],
    ),
)
snapshot(dest, [app])
expect(
    dest,
    removed_worktrees=["exporter-wt/render/donor", "exporter-wt/render/socket-trial"],
    protected_files=[
        "exporter-wt/render/integration/target/cache/input.bin",
        "exporter-wt/render/pending-patch/target/config.patch",
    ],
)
print(dest)
