"""MR !7 from `retry-backoff` has failing CI, a review bot's thread about
the bug that fails it, and a human's open question. There is no plan."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination, git  # noqa: E402
from host_fixture import BRANCH, build_app, install_host  # noqa: E402

dest = destination()
app = build_app(
    dest,
    {
        "README.md": "# app\n\nA small retry helper.\n",
        "AGENTS.md": (
            "# Agent notes\n\n"
            "- Run the tests with `python run_tests.py`. CI runs the same tests on\n"
            "  every merge request.\n"
            "- Merge requests target `main`.\n"
        ),
    },
    capped=False,
)
install_host(
    dest,
    "gitlab",
    ("glab",),
    {
        "mrs": [
            {
                "number": 7,
                "title": "Add a backoff delay between retries",
                "body": "Waits longer before each retry, doubling the delay up to `max_delay`.",
                "source": BRANCH,
                "target": "main",
                "state": "opened",
                "auto_merge": False,
                "discussions": [
                    {
                        "id": "d-bot",
                        "resolvable": True,
                        "resolved": False,
                        "notes": [
                            {
                                "id": 101,
                                "author": "review-bot",
                                "bot": True,
                                "body": (
                                    "`backoff_delay` never applies `max_delay`, so the delay "
                                    "grows without bound and `test_delay_is_capped` fails. "
                                    "Cap it with `min(..., max_delay)`."
                                ),
                                "position": {"new_path": "retry.py", "new_line": 17},
                            }
                        ],
                    },
                    {
                        "id": "d-human",
                        "resolvable": True,
                        "resolved": False,
                        "notes": [
                            {
                                "id": 102,
                                "author": "sam",
                                "bot": False,
                                "body": (
                                    "Should `max_delay` come from the settings file, or is "
                                    "two seconds fine for now?"
                                ),
                            }
                        ],
                    },
                ],
            }
        ],
        "next_mr": 8,
        "next_note": 500,
    },
)
(dest / "_expect.json").write_text(
    json.dumps(
        {
            "mr": 7,
            "main": git(app, "rev-parse", "origin/main"),
            "branch_start": git(app, "rev-parse", f"origin/{BRANCH}"),
            "ai_threads": ["d-bot"],
            "human_threads": ["d-human"],
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(dest)
