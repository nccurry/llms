"""Build a tiny workload with a deterministic operations metric."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from fixture_lib import destination, make_repo, snapshot

dest = destination()
checkout = make_repo(
    dest,
    "score",
    {
        "score.py": "def score(load):\n    return sum(load()) + len(load())\n",
        "check.py": """import sys

from score import score

data = [2, 4]
calls = 0


def load():
    global calls
    calls += 1
    return data.copy()


if sys.argv[1] == "benchmark":
    score(load)
    print(f"loader_calls={calls}")
elif sys.argv[1] == "correctness":
    assert score(load) == 8
    data[:] = [9]
    assert score(load) == 10
else:
    raise SystemExit("choose benchmark or correctness")
""",
    },
)
snapshot(dest, [checkout])
print(dest)
