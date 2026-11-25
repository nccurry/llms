"""Build a direct wrap-up case with local planning files in the primary checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from digest_fixture import COMPLETED_PLAN, build, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination, snapshot

dest = destination()
tips = build(dest, "complete")
app = dest / "notify"
original = "docs/plans/digest/README.md"
duplicate = "docs/plans/planned/digest/README.md"
keep = {
    "docs/plans/planned/digest/NOTES.md": "Consider a per-recipient quiet hours setting.\n",
    "docs/plans/planned/webhooks/README.md": "# Webhooks proposal\n",
}
for path, content in {duplicate: (app / original).read_text(encoding="utf-8"), **keep}.items():
    file = app / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8", newline="\n")

snapshot(dest, [app])
expect(
    dest,
    merged=[tips["p1"]],
    removed_worktrees=["notify-wt/digest/p1-email"],
    deleted_branches=["plc/digest-p1"],
    deleted_remote_branches=["plc/digest-p1"],
    absent_remote_files=[original, duplicate, *keep],
    removed_local_files=[duplicate],
    kept_local_text=keep,
    remote_text={"AGENTS.md": ["(docs/plans/completed/digest/README.md)"]},
    absent_remote_text={"AGENTS.md": [f"({original})"]},
    plans=[COMPLETED_PLAN],
)
print(dest)
