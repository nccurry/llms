"""A GitLab-style repository with no sign of tickets: no rules, templates,
plans or history that name one, and no issues on the host."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination  # noqa: E402
from host_fixture import build_app, install_host  # noqa: E402

dest = destination()
build_app(
    dest,
    {
        "README.md": "# app\n\nA small retry helper.\n",
        "AGENTS.md": (
            "# Agent notes\n\n"
            "- Run the tests with `python run_tests.py`.\n"
            "- Open merge requests against `main`.\n"
        ),
    },
    history=[("Tidy the retry docstring", {"README.md": "# app\n\nA small retry helper for flaky calls.\n"})],
)
install_host(dest, "gitlab", ("glab",))
(dest / "_expect.json").write_text(
    json.dumps({"allowed_refs": [], "issues": {}}, indent=2), encoding="utf-8"
)
print(dest)
