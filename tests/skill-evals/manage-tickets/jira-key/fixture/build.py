"""A GitLab-style repository whose CONTRIBUTING.md and CI require
`PROJ-123: Summary` MR titles, and whose Jira moves tickets on its own."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination  # noqa: E402
from host_fixture import build_app, install_host  # noqa: E402

CONTRIBUTING = """# Contributing

## Merge requests

- Every merge request title starts with its Jira key and a colon, such as
  `PROJ-123: Retry failed uploads`. The `mr-title` CI job checks this.
- Commit messages and branch names don't need the key.
- Jira moves the ticket by itself when the merge request opens and when it
  merges. Don't move tickets by hand.

Run the tests with `python run_tests.py` before opening a merge request.
"""

CI = """mr-title:
  stage: test
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - echo "$CI_MERGE_REQUEST_TITLE" | grep -Eq '^[A-Z][A-Z0-9]+-[0-9]+: '

test:
  stage: test
  script:
    - python run_tests.py
"""

dest = destination()
build_app(
    dest,
    {
        "README.md": "# app\n\nA small retry helper.\n",
        "AGENTS.md": "# Agent notes\n\nFollow [CONTRIBUTING.md](CONTRIBUTING.md).\n",
        "CONTRIBUTING.md": CONTRIBUTING,
        ".gitlab-ci.yml": CI,
    },
    history=[
        ("Log each retry", {"README.md": "# app\n\nA small retry helper that logs each retry.\n"}),
    ],
)
install_host(
    dest,
    "gitlab",
    ("glab", "jira"),
    {
        "jira": [
            {
                "key": "PROJ-481",
                "status": "In Progress",
                "summary": "Wait between retries",
                "description": "Retries run back to back and overload the server.",
            }
        ]
    },
)
(dest / "_expect.json").write_text(
    json.dumps(
        {"title_pattern": r"^PROJ-481: \S", "allowed_refs": ["PROJ-481"], "issues": {}},
        indent=2,
    ),
    encoding="utf-8",
)
print(dest)
