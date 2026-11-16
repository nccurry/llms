"""Build fake GitHub (default), GitLab plain, or GitLab scoped tag-label cases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tag_fixture import build

build(
    Path(sys.argv[1]).resolve(),
    sys.argv[2] if len(sys.argv) > 2 else "github",
    scoped="--scoped" in sys.argv,
)
