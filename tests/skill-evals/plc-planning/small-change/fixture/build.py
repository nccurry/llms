"""A small CLI repo with a bounded bug, and a plans folder with lifecycle folders.

`harbor list --limit 0` prints nothing, and a negative limit quietly drops
berths from the end of the list. The fix is one argument check and a test.
The repo says where plans go and that small work gets a one-file plan; no
trigger in the planning skill's Adding files rule holds.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination, make_repo, snapshot  # noqa: E402

HARBOR = '''"""harbor: list free berths at the marina."""

import argparse
import sys

BERTHS = ["A1", "A2", "B1", "B2", "C1"]


def list_berths(limit):
    return BERTHS[:limit]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="harbor")
    commands = parser.add_subparsers(dest="command", required=True)
    list_command = commands.add_parser("list", help="list free berths")
    list_command.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    for berth in list_berths(args.limit):
        print(berth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

TESTS = '''import unittest

from harbor import list_berths


class ListBerthsTest(unittest.TestCase):
    def test_limit(self):
        self.assertEqual(list_berths(2), ["A1", "A2"])


if __name__ == "__main__":
    unittest.main()
'''

README = """# harbor

List free berths at the marina: `python harbor.py list`.

Tests: `python -m unittest`.
"""

PLANS_README = """# Plans

Plans for changes to harbor live here, in lifecycle folders: `planned/`,
`in-progress/`, `completed/` and `archived/`. A new plan starts in
`planned/`.

A plan for small work is one file, `plc-<slug>.md`. Work that needs a
requirements, design or implementation file beside the plan gets a folder,
`<slug>/`, with the plan as its `README.md`.
"""

dest = destination()
app = make_repo(
    dest,
    "harbor",
    {
        "README.md": README,
        "harbor.py": HARBOR,
        "tests/__init__.py": "",
        "tests/test_harbor.py": TESTS,
        "docs/plans/README.md": PLANS_README,
    },
    message="feat: list free berths",
)
snapshot(dest, [app])
print(dest)
