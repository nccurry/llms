"""Reuse the existing lifecycle fixture, adding invented tag declarations."""

import json
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

base = Path(__file__).resolve().parents[2] / "small-change" / "fixture/build.py"
values = runpy.run_path(str(base))
dest = Path(sys.argv[1]).resolve()
expected = {"plc": {"release": "1.0.0", "component": "storage"}, "P1": {}}
(dest / "_tag_expect.json").write_text(json.dumps(expected), encoding="utf-8")
