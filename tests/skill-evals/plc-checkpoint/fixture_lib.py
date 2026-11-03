"""Build small git repositories with a plan packet for the plc-checkpoint,
wrap-this-up and plc-planning eval cases.

Each case's fixture/build.py calls these helpers to create, under a destination
folder: a bare `<name>.git` remote, a primary checkout `<name>/`, and campaign
worktrees under `<name>-wt/<campaign>/<checkout>`. Nothing here needs network
access or a PR host.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

# Every fixture packet's owner. An invented handle: fixtures never name real people.
OWNER = "@alex"

# The shared template's packet status and phase state words. The older
# variants after them are accepted too, because a moved packet keeps its words.
PACKET_STATUS_WORDS = (
    *("Planned", "In progress", "Blocked", "Complete", "Archived", "Superseded"),
    *("Draft", "Ready", "Proposed", "In-progress", "Developing", "Reviewing", "Active"),
    *("Completed", "Closed", "Done"),
)
PHASE_STATE_WORDS = (
    *("Planned", "In progress", "Implemented", "Merged", "Verified", "Live"),
    *("Blocked", "Deferred", "Dropped"),
    *("Not started", "Pending", "Todo", "Active", "Started", "Delivered"),
    *("Complete", "Completed", "Done", "Accepted", "Passed"),
)
PHASES_HEADER = "| Phase | Name | Owner | State |"


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def commit(checkout: Path, message: str, files: dict[str, str]) -> str:
    write(checkout, files)
    git(checkout, "add", "--all")
    git(checkout, "commit", "-q", "-m", message)
    return git(checkout, "rev-parse", "--short", "HEAD")


def configure(checkout: Path) -> None:
    git(checkout, "config", "user.name", "Eval Fixture")
    git(checkout, "config", "user.email", "eval@example.invalid")
    git(checkout, "config", "core.autocrlf", "false")


def make_repo(
    dest: Path, name: str, files: dict[str, str], message: str = "docs: add plan"
) -> Path:
    """Create `<name>.git` and a primary checkout `<name>/` with one commit on main."""
    remote = dest / f"{name}.git"
    checkout = dest / name
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(remote)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(checkout)],
        check=True,
        capture_output=True,
    )
    configure(checkout)
    git(checkout, "checkout", "-q", "-B", "main")
    commit(checkout, message, files)
    git(checkout, "push", "-q", "-u", "origin", "main")
    return checkout


def add_worktree(
    checkout: Path, campaign: str, name: str, branch: str, base: str = "main"
) -> Path:
    path = checkout.parent / f"{checkout.name}-wt" / campaign / name
    git(checkout, "worktree", "add", "-q", "-b", branch, str(path), base)
    return path


def second_clone(dest: Path, name: str, clone_name: str) -> Path:
    """Clone the remote again to push work the primary checkout has not fetched."""
    path = dest / "_others" / clone_name
    subprocess.run(
        ["git", "clone", "-q", str(dest / f"{name}.git"), str(path)],
        check=True,
        capture_output=True,
    )
    configure(path)
    return path


def checkout_state(path: Path) -> dict:
    """Head, status, and packet file hashes for one checkout or worktree."""
    plans = path / "docs" / "plans"
    packet_files = {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(plans.rglob("*"))
        if file.is_file()
    }
    return {
        "head": git(path, "rev-parse", "HEAD"),
        "branch": git(path, "branch", "--show-current"),
        "status": git(path, "status", "--short", "--untracked-files=all"),
        "packet_files": packet_files,
    }


def snapshot(dest: Path, checkouts: list[Path]) -> None:
    """Record repo state so check_state.py can classify what a run changed."""
    state: dict = {"checkouts": {}, "remotes": {}}
    for checkout in checkouts:
        worktrees = [
            Path(line.removeprefix("worktree "))
            for line in git(checkout, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        ]
        state["checkouts"][checkout.relative_to(dest).as_posix()] = {
            "branches": git(
                checkout,
                "for-each-ref",
                "--format=%(refname) %(objectname)",
                "refs/heads",
            ),
            "worktrees": {
                worktree.resolve().relative_to(dest).as_posix(): checkout_state(
                    worktree
                )
                for worktree in worktrees
            },
        }
    for remote in sorted(dest.glob("*.git")):
        state["remotes"][remote.name] = subprocess.run(
            [
                "git",
                "--git-dir",
                str(remote),
                "for-each-ref",
                "--format=%(refname) %(objectname)",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    (dest / "_snapshot.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def expect(
    dest: Path,
    removed_worktrees: list[str] = (),
    deleted_branches: dict[str, list[str]] | None = None,
    deleted_remote_branches: dict[str, list[str]] | None = None,
    no_packet_changes: bool = False,
) -> None:
    """Record the tidying a run must do. Anything removed beyond this fails.

    Paths are relative to `dest`; branches are short names such as `plc/x-p1`.
    """
    data = {
        "removed_worktrees": list(removed_worktrees),
        "deleted_branches": deleted_branches or {},
        "deleted_remote_branches": deleted_remote_branches or {},
        "no_packet_changes": no_packet_changes,
    }
    (dest / "_expect.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def current_work(
    last_updated: str,
    next_action: str,
    current_state: str,
    checkouts: list[tuple[str, str, str, str]] = (),
    status: str = "In progress",
    blocker: str = "None",
    depends_on: str = "None",
    more_keys: list[str] = (),
) -> str:
    """The `## Current Work` block of the shared PLC template.

    `checkouts` rows are (checkout, branch, owner, state) for the "Where the
    work lives" table. `more_keys` are extra `Key: value` lines, such as a
    `Resume check` or `Replaces` line, added after the standard keys.
    """
    keys = [
        f"Status: {status}",
        f"Owner: {OWNER}",
        f"Last updated: {last_updated}",
        f"Next action: {next_action}",
        f"Blocker: {blocker}",
        f"Depends on: {depends_on}",
        f"Current state: {current_state}",
        *more_keys,
    ]
    rows = [f"| `{a}` | `{b}` | {c} | {d} |" for a, b, c, d in checkouts] or ["| None | | | |"]
    return (
        "## Current Work\n\n"
        + "".join(f"- {key}\n" for key in keys)
        + "\nWhere the work lives:\n\n"
        + "| Checkout | Branch | Owner | State |\n| --- | --- | --- | --- |\n"
        + "".join(f"{row}\n" for row in rows)
    )


def destination() -> Path:
    if len(sys.argv) != 2:
        sys.exit("usage: build.py <empty-destination-folder>")
    dest = Path(sys.argv[1]).resolve()
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"destination is not empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def packet(
    slug: str,
    title: str,
    summary: str,
    status: str,
    phases: list[tuple[str, str, str]],
    requirements: str,
    plan: str,
    log: list[str] = ("2026-10-20 Created.",),
    extra: str = "",
) -> dict[str, str]:
    """Return a packet in the shared PLC template, under `docs/plans/<slug>/`.

    `status` is a `current_work(...)` block. `phases` rows are (phase, name,
    state) for the README `## Phases` table; their owner is the packet owner.
    `extra` holds whole sections, each ending in a blank line, that go between
    the Phases table and the packet links, such as `## Open questions`.
    `plan` is the implementation plan's body, with `### P1: <name>` sections
    and no state table.
    """
    root = f"docs/plans/{slug}"
    phase_rows = "".join(f"| {phase} | {name} | | {state} |\n" for phase, name, state in phases)
    readme = "\n".join(
        [
            f"# {title}\n",
            f"{summary}\n",
            status,
            f"## Phases\n\n{PHASES_HEADER}\n| --- | --- | --- | --- |\n{phase_rows}",
            f"{extra}## Packet\n",
            "- [SRD.md](SRD.md): requirements and their checks.",
            "- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): phase details and evidence.\n",
            "## Log\n",
            "".join(f"- {line}\n" for line in log),
        ]
    )
    return {
        f"{root}/README.md": readme,
        f"{root}/SRD.md": f"# {title} requirements\n\n{requirements}",
        f"{root}/IMPLEMENTATION_PLAN.md": (
            f"# {title} implementation plan\n\n"
            "Phase state lives in the README's [Phases](README.md#phases) table.\n\n"
            f"{plan}"
        ),
    }


def _starts_with_word(text: str, words: tuple[str, ...]) -> bool:
    text = text.strip().strip("*_`").lower()
    return any(
        text.startswith(word.lower()) and not text[len(word) : len(word) + 1].isalnum()
        for word in words
    )


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def packet_shape_problems(readme: str, plan: str = "") -> list[str]:
    """List the ways a packet README, and its plan, differ from the shared template.

    It covers the structure the evals rely on, not every rule: a summary under
    the title; one `## Current Work` first, starting with Status, Owner (by
    @handle) and a date-first Last updated; `## Phases` next, with a Phase
    table whose State (or, in a moved packet, Status) column starts with a
    state word; `## Log` last, with dated lines; no empty sections or
    placeholders; and no phase table with a State or Status column in the plan.
    An empty list means the shape is right.
    """
    problems = []
    lines = readme.splitlines()
    heads = [i for i, line in enumerate(lines) if line.startswith("## ")]
    names = [lines[i][3:].strip() for i in heads]
    bodies = {
        name: [line for line in lines[a + 1 : b] if line.strip()]
        for name, a, b in zip(names, heads, heads[1:] + [len(lines)])
    }
    title = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    first = next((line for line in lines[(title or 0) + 1 :] if line.strip()), "")
    if title is None or first.startswith("#"):
        problems.append("no summary directly under the title")
    if names.count("Current Work") != 1 or names[:1] != ["Current Work"]:
        problems.append("needs exactly one ## Current Work, directly after the summary")
    if names[1:2] != ["Phases"]:
        problems.append("## Phases must follow ## Current Work")
    if names[-1:] != ["Log"]:
        problems.append("## Log must be the last section")
    for name in names:
        if name.lower().startswith(("status", "lifecycle")):
            problems.append(f"old status section: ## {name}")
        if not bodies.get(name):
            problems.append(f"empty section: ## {name}")
    keys = [
        (match[1], match[2])
        for line in bodies.get("Current Work", [])
        if (match := re.match(r"- ([A-Z][A-Za-z ]*?): (.*)", line))
    ]
    values = dict(keys)
    if [key for key, _ in keys[:3]] != ["Status", "Owner", "Last updated"]:
        problems.append("Current Work must start with Status, Owner and Last updated")
    if len(keys) > 12:
        problems.append(f"Current Work has {len(keys)} keys (at most 12)")
    if not _starts_with_word(values.get("Status", ""), PACKET_STATUS_WORDS):
        problems.append(f"Status has no packet status word: {values.get('Status')!r}")
    if "@" not in values.get("Owner", ""):
        problems.append("Owner names nobody by @handle")
    if not re.match(r"\d{4}-\d{2}-\d{2}", values.get("Last updated", "")):
        problems.append("Last updated does not start with a date")
    phase_lines = [line for line in bodies.get("Phases", []) if line.startswith("|")]
    header = [cell.lower() for cell in _cells(phase_lines[0])] if phase_lines else []
    column = next((header.index(name) for name in ("state", "status") if name in header), None)
    if header[:1] != ["phase"] or column is None:
        problems.append("## Phases needs a table with Phase and State columns")
    else:
        for row in phase_lines[2:]:
            cells = _cells(row)
            if len(cells) != len(header) or not _starts_with_word(cells[column], PHASE_STATE_WORDS):
                problems.append(f"phase row needs every cell and a state word: {row}")
    if not any(re.match(r"- \d{4}-\d{2}-\d{2} ", line) for line in bodies.get("Log", [])):
        problems.append("## Log has no dated line")
    if re.search(r"\bN/A\b|\bTBD\b|<(?!https?:)[^>\n]+>", readme):
        problems.append("placeholder text (N/A, TBD or <...>) left in the README")
    for line in plan.splitlines():
        cells = [cell.lower() for cell in _cells(line)] if line.startswith("|") else []
        if cells[:1] == ["phase"] and ("state" in cells or "status" in cells):
            problems.append(f"phase state table outside the README: {line}")
    return problems
