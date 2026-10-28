"""Build the `notify` repo with a digest PLC for wrap-this-up eval cases.

Every variant has a bare `notify.git` remote, a primary checkout `notify/`, and
child worktrees under `notify-wt/digest/`. The repo's AGENTS.md says to merge
straight into main, push, and run `run_tests.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plc-checkpoint"))
from fixture_lib import (  # noqa: E402
    add_worktree,
    commit,
    git,
    make_repo,
    packet,
    snapshot,
    current_work,
)

RUN_TESTS = '''"""Run every test_* function in tests/test_*.py; exit 1 on any failure."""

import importlib.util
import pathlib
import sys
import traceback

sys.path.insert(0, ".")
failed = 0
for path in sorted(pathlib.Path("tests").glob("test_*.py")):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in sorted(dir(module)):
        if name.startswith("test_"):
            try:
                getattr(module, name)()
                print("PASS", path.name, name)
            except Exception:
                failed += 1
                print("FAIL", path.name, name)
                traceback.print_exc()
sys.exit(1 if failed else 0)
'''

BASE_DIGEST = 'def email_digest(items):\n    return "\\n".join(f"- {item}" for item in items)\n'
BASE_TEST = (
    "from src.digest import email_digest\n\n\n"
    "def test_email_items():\n"
    '    assert email_digest(["a", "b"]).endswith("- a\\n- b")\n'
)

REQ_P1 = "| DIG-001 | The email digest starts with a `Digest:` header line. | `test_email_header` passes. |\n"
REQ_P2 = (
    "| DIG-002 | A Slack digest has the same text as the email digest and posts "
    "to the configured channel. | `test_slack_text` and `test_slack_channel` pass. |\n"
)


def agents_md() -> str:
    return f"""# notify

## Delivery

Merge finished branches straight into `main` and push to `origin`. No PRs.
Plan updates are committed straight to `main`.

## Checks

From the repository root:

```sh
"{sys.executable}" run_tests.py
```

## Worktrees

Root: `../notify-wt/<campaign>/<checkout>`.
"""


def plan_files(with_p2: bool, as_of: str, rows, checkouts, next_step: str) -> dict:
    requirements = "| ID | Requirement | Acceptance |\n| --- | --- | --- |\n" + REQ_P1
    phases = (
        "## Phase Summary\n\n"
        "| Phase | Goal | Requirements | Validation |\n| --- | --- | --- | --- |\n"
        "| P1 | Email header | DIG-001 | `test_email_header` |\n"
    )
    if with_p2:
        requirements += REQ_P2
        phases += "| P2 | Slack digest | DIG-002 | `test_slack_text`, `test_slack_channel` |\n"
    return packet(
        "digest",
        requirements,
        phases,
        status=current_work(as_of, rows, checkouts, next_step),
    )


def build(dest: Path, variant: str) -> dict:
    """Build a variant; return the commit tips of each child branch."""
    with_p2 = variant != "complete"
    app = make_repo(
        dest,
        "notify",
        {
            "AGENTS.md": agents_md(),
            "run_tests.py": RUN_TESTS,
            "src/digest.py": BASE_DIGEST,
            "tests/test_digest.py": BASE_TEST,
        },
    )
    start = git(app, "rev-parse", "--short", "HEAD")
    rows = [("P1 (DIG-001)", "in progress", "p1 child", "none yet")]
    checkouts = [("notify-wt/digest/p1-email", "plc/digest-p1", "in progress")]
    if with_p2:
        rows.append(("P2 (DIG-002)", "in progress", "p2 child", "none yet"))
        checkouts.append(("notify-wt/digest/p2-slack", "plc/digest-p2", "in progress"))
    commit(
        app,
        "docs(plan): add digest PLC",
        plan_files(with_p2, f"2026-10-26, `main` at `{start}`", rows, checkouts, "finish P1 and P2"),
    )
    git(app, "push", "-q", "origin", "main")

    tips = {}
    p1 = add_worktree(app, "digest", "p1-email", "plc/digest-p1")
    commit(
        p1,
        "feat(digest): add a Digest: header to the email digest (DIG-001)",
        {
            "src/digest.py": (
                "def email_digest(items):\n"
                '    lines = ["Digest:"] + [f"- {item}" for item in items]\n'
                '    return "\\n".join(lines)\n'
            ),
            "tests/test_digest.py": BASE_TEST
            + (
                "\n\ndef test_email_header():\n"
                '    assert email_digest(["a"]).splitlines()[0] == "Digest:"\n'
            ),
        },
    )
    git(p1, "push", "-q", "-u", "origin", "plc/digest-p1")
    tips["p1"] = git(p1, "rev-parse", "HEAD")

    if with_p2:
        # The failing variant's test pins the old text, so it breaks only once
        # P1's header is merged in.
        expected = '"- a"' if variant == "failing" else 'email_digest(["a"])'
        p2 = add_worktree(app, "digest", "p2-slack", "plc/digest-p2")
        commit(
            p2,
            "feat(slack): Slack digest text (DIG-002, channel posting still to do)",
            {
                "src/slack.py": (
                    "from src.digest import email_digest\n\n\n"
                    "def slack_digest(items):\n"
                    '    return {"text": email_digest(items)}\n'
                ),
                "tests/test_slack.py": (
                    "from src.digest import email_digest\n"
                    "from src.slack import slack_digest\n\n\n"
                    "def test_slack_text():\n"
                    f'    assert slack_digest(["a"])["text"] == {expected}\n'
                ),
            },
        )
        tips["p2"] = git(p2, "rev-parse", "HEAD")
        if variant == "active-agent":
            git(
                app,
                "worktree",
                "lock",
                "--reason",
                "p2 child (another session); keep until test_slack_channel passes; 2026-10-27",
                str(p2),
            )

    snapshot(dest, [app])
    return tips


def expect(dest: Path, **data) -> None:
    (dest / "_expect.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
