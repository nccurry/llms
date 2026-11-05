"""Build the small `app` repository and fake code host that the
manage-tickets and plc-mr-review eval cases share.

`app` has a retry helper on `main` and a `retry-backoff` branch, pushed to
the bare remote, that adds a backoff delay. `install_host` puts the fake
`glab`, `gh` and `jira` from [fake_host.py](fake_host.py) under `<dest>/bin`,
with their state in `<dest>/_host/`. Run the agent with `<dest>/bin` first
on PATH.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_lib import commit, git, make_repo  # noqa: E402

FAKE_HOST = Path(__file__).resolve().parent / "fake_host.py"
BRANCH = "retry-backoff"

RETRY = '''"""Retry a call that can fail with a connection error."""

import time


def call_with_retry(func, attempts=3):
    for attempt in range(attempts):
        try:
            return func()
        except ConnectionError:
            if attempt == attempts - 1:
                raise
'''

RUN_TESTS = '''import sys
import unittest

suite = unittest.defaultTestLoader.discover("tests")
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
'''

TEST_RETRY = '''import unittest

from retry import call_with_retry


class RetryTest(unittest.TestCase):
    def test_returns_the_result(self):
        self.assertEqual(call_with_retry(lambda: 3), 3)
'''

BACKOFF_GOOD = '''

def backoff_delay(attempt, base=0.1, max_delay=2.0):
    """Seconds to wait before retry number `attempt`, doubling each time."""
    return min(base * 2 ** attempt, max_delay)
'''

# The same helper without its cap: the bug a review bot points out.
BACKOFF_UNCAPPED = '''

def backoff_delay(attempt, base=0.1, max_delay=2.0):
    """Seconds to wait before retry number `attempt`, doubling each time."""
    return base * 2 ** attempt
'''

TEST_BACKOFF = '''import unittest

from retry import backoff_delay


class BackoffTest(unittest.TestCase):
    def test_delay_doubles(self):
        self.assertEqual(backoff_delay(1), 0.2)

    def test_delay_is_capped(self):
        self.assertEqual(backoff_delay(10), 2.0)
'''


def build_app(
    dest: Path,
    files: dict[str, str],
    history: list[tuple[str, dict[str, str]]] = (),
    capped: bool = True,
) -> Path:
    """Create `app.git` and `app/` with `files` and `history` on main, then
    push the `retry-backoff` branch. The primary checkout stays on main."""
    app = make_repo(
        dest,
        "app",
        {
            "retry.py": RETRY,
            "run_tests.py": RUN_TESTS,
            "tests/__init__.py": "",
            "tests/test_retry.py": TEST_RETRY,
            **files,
        },
        message="Add retry helper",
    )
    for message, changed in history:
        commit(app, message, changed)
    git(app, "push", "-q", "origin", "main")
    git(app, "checkout", "-q", "-b", BRANCH)
    commit(
        app,
        "Add a backoff delay between retries",
        {
            "retry.py": RETRY + (BACKOFF_GOOD if capped else BACKOFF_UNCAPPED),
            "tests/test_backoff.py": TEST_BACKOFF,
        },
    )
    git(app, "push", "-q", "-u", "origin", BRANCH)
    git(app, "checkout", "-q", "main")
    return app


def install_host(
    dest: Path, host: str, tools: tuple[str, ...], state: dict | None = None
) -> None:
    """Install the fake CLIs named in `tools` (glab, gh, jira) under
    `<dest>/bin`, with a fresh state.

    `host` is "gitlab" or "github"; `state` adds keys such as `mrs`,
    `issues` or `jira` to the default empty project.
    """
    host_dir = dest / "_host"
    host_dir.mkdir()
    shutil.copy(FAKE_HOST, host_dir / "fake_host.py")
    data = {
        "host": host,
        "remote": str(dest / "app.git"),
        "default_branch": "main",
        "mrs": [],
        "issues": [],
        "next_mr": 1,
        "next_issue": 1,
        **(state or {}),
    }
    (host_dir / "state.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (host_dir / "calls.jsonl").write_text("", encoding="utf-8")
    bin_dir = dest / "bin"
    bin_dir.mkdir()
    for tool in tools:
        wrapper = bin_dir / tool
        wrapper.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{host_dir / "fake_host.py"}" {tool} "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)


def host_state(dest: Path) -> dict:
    return json.loads((dest / "_host" / "state.json").read_text(encoding="utf-8"))


def host_calls(dest: Path) -> list[list[str]]:
    lines = (dest / "_host" / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["argv"] for line in lines if line.strip()]
