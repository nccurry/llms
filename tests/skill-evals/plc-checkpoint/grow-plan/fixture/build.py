"""An in-progress one-file plan whose P1 is merged and verified. The user then
approves a new public CLI flag in the conversation.

The plan's one requirement is internal, so it started as one file. The new
flag is a public contract, so the planning skill's Adding files rule calls
for SRD.md, and its Growing a packet rule turns the plan into a folder.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import (  # noqa: E402
    OWNER,
    add_worktree,
    commit,
    current_work,
    destination,
    expect,
    git,
    make_repo,
    snapshot,
)

PLANS = "docs/plans/in-progress"
ONE_FILE_PLAN = f"{PLANS}/plc-tide-cache.md"
PACKET = f"{PLANS}/tide-cache"
DONE_WHEN_LINE = "The requirements and their checks are in [SRD.md](SRD.md)."
TEST_RESULT = "`python -m unittest` → 2 tests OK"

TIDES = '''"""tides: print today's tide times for the harbor."""

import argparse
import sys

from cache import cached
from feed import fetch_tides


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tides")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show", help="print today's tide times")
    parser.parse_args(argv)
    for line in cached(fetch_tides):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

FEED = '''"""The tide feed. The real one is a web request; this one is fixed."""


def fetch_tides():
    return ["High 06:12 4.1 m", "Low 12:30 0.8 m", "High 18:41 4.3 m"]
'''

NO_CACHE = '''"""No cache yet: every call fetches the feed."""


def cached(fetch):
    return fetch()
'''

CACHE = '''"""Keep the tide feed for a minute, so repeated `tides show` calls don't fetch it again."""

import json
import time
from pathlib import Path

CACHE_FILE = Path.home() / ".cache" / "tides.json"
MAX_AGE = 60


def cached(fetch, path=CACHE_FILE, max_age=MAX_AGE, now=time.time):
    """The feed saved in `path` when it is younger than `max_age` seconds;
    otherwise a fresh fetch, saved there."""
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if now() - saved["at"] < max_age:
            return saved["lines"]
    except (OSError, ValueError, KeyError):
        pass
    lines = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": now(), "lines": lines}), encoding="utf-8")
    return lines
'''

CACHE_TESTS = '''import tempfile
import unittest
from pathlib import Path

from cache import cached


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "tides.json"
        self.calls = 0

    def fetch(self):
        self.calls += 1
        return ["High 06:12 4.1 m"]

    def test_second_call_within_a_minute_reads_the_feed_once(self):
        cached(self.fetch, self.path, now=lambda: 100.0)
        cached(self.fetch, self.path, now=lambda: 159.0)
        self.assertEqual(self.calls, 1)

    def test_call_after_a_minute_reads_the_feed_again(self):
        cached(self.fetch, self.path, now=lambda: 100.0)
        cached(self.fetch, self.path, now=lambda: 160.0)
        self.assertEqual(self.calls, 2)


if __name__ == "__main__":
    unittest.main()
'''

README = """# tides

Print today's tide times for the harbor: `python tides.py show`.

Tests: `python -m unittest`.
"""

PLANS_README = """# Plans

Plans for changes to tides live here, in lifecycle folders: `planned/`,
`in-progress/`, `completed/` and `archived/`.
"""

REQUIREMENT = (
    "- TIDE-001: A second `tides show` within a minute reads the feed once."
    " Check: `python -m unittest tests.test_cache` → passes"
)


def plan(current_work_block: str, p1_state: str, log: list[str]) -> str:
    """The one-file plan, in the shared template."""
    return "\n".join(
        [
            "# Tide cache\n",
            "Cache the tide feed for a minute, so repeated `tides show` calls"
            " don't fetch it each time.\n",
            current_work_block,
            "## Phases\n",
            "| Phase | Name | Owner | State |",
            "| --- | --- | --- | --- |",
            f"| P1 | Cache the feed | | {p1_state} |\n",
            "## Done when\n",
            f"{REQUIREMENT}\n",
            "## Log\n",
            "".join(f"- {line}\n" for line in log),
        ]
    )


dest = destination()
app = make_repo(
    dest,
    "tides",
    {
        "README.md": README,
        "tides.py": TIDES,
        "feed.py": FEED,
        "cache.py": NO_CACHE,
        "tests/__init__.py": "",
        "docs/plans/README.md": PLANS_README,
    },
    message="feat: print tide times",
)
start = git(app, "rev-parse", "--short", "HEAD")
commit(
    app,
    "docs(plan): add tide cache plan",
    {
        ONE_FILE_PLAN: plan(
            current_work(
                last_updated=f"2026-11-02, `main` at `{start}`",
                next_action="Write the failing cache test in `tests/test_cache.py`.",
                current_state="P1 started in `tides-wt/tide-cache/p1-cache`.",
                checkouts=[("tides-wt/tide-cache/p1-cache", "plc/tide-cache-p1", OWNER, "in progress")],
            ),
            "In progress",
            ["2026-11-02 Created."],
        )
    },
)
p1 = add_worktree(app, "tide-cache", "p1-cache", "plc/tide-cache-p1")
commit(
    p1,
    "feat(cache): read the tide feed at most once a minute (TIDE-001)",
    {"cache.py": CACHE, "tests/test_cache.py": CACHE_TESTS},
)
git(app, "merge", "-q", "--no-ff", "plc/tide-cache-p1", "-m", "Merge P1 tide cache")
merge = git(app, "rev-parse", "--short", "HEAD")
git(app, "worktree", "remove", str(p1))
p1.parent.rmdir()
p1.parent.parent.rmdir()
git(app, "branch", "-q", "-d", "plc/tide-cache-p1")
commit(
    app,
    "docs(plan): record P1 verified",
    {
        ONE_FILE_PLAN: plan(
            current_work(
                last_updated=f"2026-11-03, `main` at `{merge}`",
                next_action="Finish the plan with `wrap-this-up`.",
                current_state=f"P1 merged into `main` at `{merge}` and verified: {TEST_RESULT}.",
                resume_check=TEST_RESULT,
            ),
            f"Verified — {TEST_RESULT} @ `{merge}`",
            [
                "2026-11-02 Created.",
                f"2026-11-03 P1 merged @ `{merge}`.",
                f"2026-11-03 P1 verified: {TEST_RESULT} @ `{merge}`.",
            ],
        )
    },
)
git(app, "push", "-q", "origin", "main")
snapshot(dest, [app])
# Nothing to tidy. The approved --max-age flag is a public contract, so the
# plan must become a folder whose SRD.md holds the new requirement, with
# only the pointer line left in ## Done when, a dated Log line naming
# SRD.md, and no findings from the shipped format check.
expect(
    dest,
    packet_content={
        "path": f"tides/{PACKET}",
        "one_file_plan": f"tides/{ONE_FILE_PLAN}",
        "srd_rows": ["TIDE-001", "--max-age"],
        "done_when": DONE_WHEN_LINE,
        "log_line": "SRD.md",
        "format_check": True,
    },
)
print(dest)
