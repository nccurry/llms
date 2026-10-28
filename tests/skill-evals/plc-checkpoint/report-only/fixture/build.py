"""The cross-repo-wait fixture, used for a report-only request."""

import runpy
from pathlib import Path

runpy.run_path(
    str(
        Path(__file__).resolve().parents[2] / "cross-repo-wait" / "fixture" / "build.py"
    ),
    run_name="__main__",
)
