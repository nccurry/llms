"""A GitHub-style repository whose PR template and history close issues
with `Closes #N`, and whose open issue #42 the branch fixes."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination  # noqa: E402
from host_fixture import build_app, install_host  # noqa: E402

TEMPLATE = """## What and why

## How it was checked

Closes #
"""

dest = destination()
build_app(
    dest,
    {
        "README.md": "# app\n\nA small retry helper.\n",
        "AGENTS.md": "# Agent notes\n\nRun the tests with `python run_tests.py`.\n",
        ".github/pull_request_template.md": TEMPLATE,
    },
    history=[
        (
            "Log each retry (#12)\n\nCloses #11",
            {"README.md": "# app\n\nA small retry helper that logs each retry.\n"},
        ),
    ],
)
install_host(
    dest,
    "github",
    ("gh",),
    {
        "issues": [
            {
                "number": 11,
                "title": "Retries are silent",
                "body": "Nothing says a call was retried.",
                "state": "closed",
                "comments": [],
            },
            {
                "number": 42,
                "title": "Add a backoff delay helper for retries",
                "body": "Add a function that says how long to wait before retry N: start at 0.1 seconds, double each time, and stop at 2 seconds. Using it in the retry loop is a separate change.",
                "state": "open",
                "comments": [],
            },
        ],
        "next_mr": 43,
        "next_issue": 44,
    },
)
(dest / "_expect.json").write_text(
    json.dumps(
        {
            "body_pattern": r"(?i)\bcloses #42\b",
            "allowed_refs": ["#42"],
            "issues": {"11": "closed", "42": "open"},
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(dest)
