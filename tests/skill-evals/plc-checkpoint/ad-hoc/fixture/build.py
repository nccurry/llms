"""Ad-hoc work with no plan: a worktree with two commits and an uncommitted edit."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_lib import add_worktree, commit, destination, expect, make_repo, snapshot, write

dest = destination()
app = make_repo(
    dest,
    "cli",
    {"src/render.py": "def render(text, color=False):\n    return text\n"},
)
work = add_worktree(app, "color-output", "color", "ncurry/color-output")
commit(
    work,
    "feat(cli): add --color flag",
    {
        "src/render.py": (
            "def render(text, color=False):\n"
            "    return f'\x1b[32m{text}\x1b[0m' if color else text\n"
        ),
        "src/main.py": (
            "import argparse\n\nfrom src.render import render\n\n\n"
            "def main(argv=None):\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--color', action='store_true')\n"
            "    parser.add_argument('text')\n"
            "    args = parser.parse_args(argv)\n"
            "    print(render(args.text, args.color))\n"
        ),
    },
)
commit(
    work,
    "test(cli): cover --color",
    {
        "tests/test_render.py": (
            "from src.render import render\n\n\n"
            "def test_color():\n"
            "    assert render('hi', True) == '\x1b[32mhi\x1b[0m'\n"
            "    assert render('hi') == 'hi'\n"
        )
    },
)
# Work in progress on NO_COLOR, not committed yet.
write(
    work,
    {
        "src/render.py": (
            "import os\n\n\n"
            "def render(text, color=False):\n"
            "    if os.environ.get('NO_COLOR'):\n"
            "        color = False\n"
            "    return f'\x1b[32m{text}\x1b[0m' if color else text\n"
        )
    },
)
snapshot(dest, [app])
expect(dest, no_packet_changes=True)
print(dest)
