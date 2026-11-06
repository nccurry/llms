"""Build the `notify` repo with a digest PLC for plc-wrapup eval cases.

Every variant has a bare `notify.git` remote, a primary checkout `notify/`, and
child worktrees under `notify-wt/digest/`. The repo's AGENTS.md says to merge
straight into main, push, and run `run_tests.py`, and links to the plan.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture_lib import (
    add_worktree,
    commit,
    current_work,
    git,
    make_repo,
    packet,
    phase_rule,
    snapshot,
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

# Requirement rows for SRD.md. Each literal is one Markdown table row.
REQ_HEADER = (
    "| DIG-001 | The email digest starts with a `Digest:` header line. "
    "| `test_email_header` passes. |\n"
)
REQ_SLACK = (
    "| DIG-002 | A Slack digest has the same text as the email digest and posts "
    "to the configured channel. | `test_slack_text` and `test_slack_channel` pass. |\n"
)
REQ_FOOTER = (
    "| DIG-003 | The email digest ends with an `Unsubscribe:` line. "
    "| `test_email_footer` passes. |\n"
)
# AGENTS.md links here; a wrap-up that moves the plan must update the link.
PLAN_README = "docs/plans/digest/README.md"


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

## Plans

The digest plan is [{PLAN_README}]({PLAN_README}).
"""


def plan_files(variant: str, start: str) -> dict[str, str]:
    """The digest packet as written before work started, for one variant.

    Only the "unmet" variant gives P1 the footer requirement DIG-003, which no
    branch implements.
    """
    with_p2 = variant not in ("complete", "unmet")
    requirements = "| ID | Requirement | Acceptance |\n| --- | --- | --- |\n" + REQ_HEADER
    summary = "Start the daily notification email with a `Digest:` header."
    p1 = (
        "P1",
        "Email header",
        "In progress",
        "- Requirements: DIG-001\n- Check: `test_email_header` passes.",
    )
    if variant == "unmet":
        requirements += REQ_FOOTER
        summary = (
            "Frame the daily notification email with a `Digest:` header and an unsubscribe line."
        )
        p1 = (
            "P1",
            "Email header and footer",
            "In progress",
            "- Requirements: DIG-001, DIG-003\n"
            "- Checks: `test_email_header` and `test_email_footer` pass.",
        )
    phases = [p1]
    checkouts = [("notify-wt/digest/p1-email", "plc/digest-p1", "p1 child", "in progress")]
    if with_p2:
        requirements += REQ_SLACK
        summary = (
            "Send the daily notification digest by email, with a `Digest:` header,"
            " and post the same text to Slack."
        )
        phases.append(
            (
                "P2",
                "Slack digest",
                "In progress",
                "- Requirements: DIG-002\n"
                "- Checks: `test_slack_text` and `test_slack_channel` pass.",
            )
        )
        checkouts.append(("notify-wt/digest/p2-slack", "plc/digest-p2", "p2 child", "in progress"))
    return packet(
        "digest",
        "Digest",
        summary,
        current_work(
            last_updated=f"2026-10-26, `main` at `{start}`",
            next_action="finish P1 and P2" if with_p2 else "finish P1",
            current_state="Work in progress in the worktrees below; nothing merged yet.",
            checkouts=checkouts,
            resume_check="`python run_tests.py` → every test passes",
        ),
        phases,
        requirements,
        log=["2026-10-26 Created."],
    )


def build(dest: Path, variant: str) -> dict:
    """Build a variant; return the commit tips of each child branch.

    Variants: "mid-stream", "failing" and "active-agent" have P1 and P2;
    "complete" and "unmet" have P1 only.
    """
    with_p2 = variant not in ("complete", "unmet")
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
    commit(app, "docs(plan): add digest PLC", plan_files(variant, start))
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


# What check_wrap.py requires of the plan on origin/main, by where it ends up.
# In both, "Where the work lives" must not name a checkout the run removed.
OPEN_PLAN = {
    "path": "docs/plans/digest",
    "statuses": ["In progress", "Blocked"],
    "owner": "@alex",
    "historical": False,
    "lists_no_removed_checkouts": True,
}
COMPLETED_PLAN = {
    "path": "docs/plans/completed/digest",
    "statuses": ["Complete"],
    "owner": "@alex",
    "historical": True,
    "lists_no_removed_checkouts": True,
}


def open_plan_with_unbuilt_part(phase: str, phases_at_start: list[str]) -> dict:
    """OPEN_PLAN for a case where `phase` merges with a part nobody built.

    While the phase still holds that part it is In progress; once its note
    says `moved to P<n>` for a new row, one outside `phases_at_start`, it
    must be Merged or Verified instead.
    """
    rule = phase_rule(["In progress"], ["Merged", "Verified"], phases_at_start)
    return {**OPEN_PLAN, "phases": {phase: rule}}


def expect(dest: Path, **data) -> None:
    (dest / "_expect.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
