"""Reuse the existing lifecycle fixture, adding invented tag declarations."""

import json
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import commit, git, snapshot

base = Path(__file__).resolve().parents[2] / "complete-moves-plan" / "fixture/build.py"
values = runpy.run_path(str(base))
dest = Path(sys.argv[1]).resolve()
checkout = dest / "notify"
path = checkout / "docs/plans/digest/README.md"
text = path.read_text(encoding="utf-8").replace(
    "- Blocker:", "- Tags: release: 1.0.0; component: storage\n- Blocker:"
)
text = text.replace("| Phase | Name | Owner | State |", "| Phase | Name | Owner | State | Tags |")
text = text.replace("| --- | --- | --- | --- |\n| P1", "| --- | --- | --- | --- | --- |\n| P1")
text = (
    "\n".join(
        line + " release: 1.1.0 |" if line.startswith("| P1 |") else line
        for line in text.splitlines()
    )
    + "\n"
)
commit(checkout, "Record invented tags", {"docs/plans/digest/README.md": text})
git(checkout, "push", "-q", "origin", "main")
expected_path = dest / "_expect.json"
expected = json.loads(expected_path.read_text(encoding="utf-8"))
expected["plans"][0]["tags"] = {
    "plc": {"release": "1.0.0", "component": "storage"},
    "P1": {"release": "1.1.0"},
}
expected_path.write_text(json.dumps(expected), encoding="utf-8")
snapshot(dest, [checkout])
