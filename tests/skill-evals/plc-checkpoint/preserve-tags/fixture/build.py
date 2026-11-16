"""Reuse the existing lifecycle fixture, adding invented tag declarations."""

import json
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import commit, snapshot

base = Path(__file__).resolve().parents[2] / "morning-refresh" / "fixture/build.py"
values = runpy.run_path(str(base))
dest = Path(sys.argv[1]).resolve()
checkout = values["integration"]
path = checkout / "docs/plans/reconcile/README.md"
text = path.read_text(encoding="utf-8").replace(
    "- Blocker:", "- Tags: release: 1.0.0; component: storage\n- Blocker:"
)
text = text.replace("| Phase | Name | Owner | State |", "| Phase | Name | Owner | State | Tags |")
text = text.replace("| --- | --- | --- | --- |\n| P1", "| --- | --- | --- | --- | --- |\n| P1")
lines = text.splitlines()
for index, line in enumerate(lines):
    if line.startswith("| P1 |") or line.startswith("| P2 |"):
        lines[index] = line + (" release: 1.1.0 |" if line.startswith("| P2 |") else " |")
commit(
    checkout, "Record invented tags", {"docs/plans/reconcile/README.md": "\n".join(lines) + "\n"}
)
expected_path = dest / "_expect.json"
expected = json.loads(expected_path.read_text(encoding="utf-8"))
expected["packet_content"] = {
    "path": "ledger-wt/reconcile/integration/docs/plans/reconcile",
    "tags": {
        "plc": {"release": "1.0.0", "component": "storage"},
        "P1": {},
        "P2": {"release": "1.1.0"},
    },
}
expected_path.write_text(json.dumps(expected), encoding="utf-8")
snapshot(dest, [values["app"]])
