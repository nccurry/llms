"""Shared helpers for the plc-checkpoint, wrap-this-up and plc-planning eval cases.

Each case's fixture/build.py calls these helpers to create, under a destination
folder: a bare `<name>.git` remote, a primary checkout `<name>/`, and campaign
worktrees under `<name>-wt/<campaign>/<checkout>`. Nothing here needs network
access or a PR host. Every git command runs without the developer's own git
config, so fixtures build the same way on every machine.

The checkers and fixture tests use the git helpers and `packet_shape_problems`,
which checks a packet against the shared PLC template.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

# Every fixture packet's owner. An invented handle: fixtures never name real people.
OWNER = "@alex"

# Each fixture repository ignores the bytecode its tests write.
GITIGNORE = "__pycache__/\n*.py[co]\n.pytest_cache/\n"

# The shared template's packet status and phase state words. The older
# variants after them are accepted too, because a converted packet keeps its
# words.
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
# The shared sections, in template order. Other sections go after them and
# before `## Log`, which is last.
SECTION_ORDER = ("Current Work", "Phases", "Done when", "Open questions")


def _isolated_git_env() -> dict[str, str]:
    """The environment for git commands: no global or system git config, and
    no GIT_* variables from the caller."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


GIT_ENV = _isolated_git_env()


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git in `cwd` with GIT_ENV; the caller checks the result."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=GIT_ENV,
    )


def git(cwd: Path, *args: str, check: bool = True) -> str:
    """Run git in `cwd` and return its output without surrounding whitespace.

    Raises CalledProcessError on failure unless `check` is False.
    """
    result = run_git(cwd, *args)
    if check and result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    return result.stdout.strip()


def is_ancestor(cwd: Path, older: str, newer: str) -> bool:
    return run_git(cwd, "merge-base", "--is-ancestor", older, newer).returncode == 0


def status_paths(checkout: Path) -> set[str]:
    """Every path `git status` lists in a checkout, untracked files included.

    Reads `--porcelain -z`, so paths need no unquoting. A rename gives its new
    path.
    """
    entries = run_git(
        checkout, "status", "--porcelain", "-z", "--untracked-files=all"
    ).stdout.split("\0")
    paths = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        paths.add(entry[3:])
        if entry[0] in "RC":
            index += 1  # The next entry is the old path.
    return paths


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
    """Create `<name>.git` and a primary checkout `<name>/` with one commit on main.

    The commit also adds a `.gitignore` for bytecode, so running a fixture's
    tests leaves its checkouts clean.
    """
    remote = dest / f"{name}.git"
    checkout = dest / name
    git(dest, "init", "-q", "--bare", "-b", "main", str(remote))
    git(dest, "clone", "-q", str(remote), str(checkout))
    configure(checkout)
    git(checkout, "checkout", "-q", "-B", "main")
    commit(checkout, message, {".gitignore": GITIGNORE, **files})
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
    git(dest, "clone", "-q", str(dest / f"{name}.git"), str(path))
    configure(path)
    return path


def checkout_state(path: Path) -> dict:
    """Head, changed paths, and packet file hashes for one checkout or worktree."""
    plans = path / "docs" / "plans"
    packet_files = {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(plans.rglob("*"))
        if file.is_file()
    }
    return {
        "head": git(path, "rev-parse", "HEAD"),
        "branch": git(path, "branch", "--show-current"),
        "status_paths": sorted(status_paths(path)),
        "packet_files": packet_files,
    }


def worktree_paths(checkout: Path, check: bool = True) -> list[Path]:
    """The worktrees a checkout's `git worktree list --porcelain` registers."""
    return [
        Path(line.removeprefix("worktree "))
        for line in git(checkout, "worktree", "list", "--porcelain", check=check).splitlines()
        if line.startswith("worktree ")
    ]


def remote_refs(dest: Path, remote: str, check: bool = True) -> str:
    """'refname objectname' lines for every ref in the bare repo `dest/remote`."""
    return git(
        dest,
        "--git-dir",
        str(dest / remote),
        "for-each-ref",
        "--format=%(refname) %(objectname)",
        check=check,
    )


def snapshot(dest: Path, checkouts: Sequence[Path]) -> None:
    """Record repo state so check_state.py can classify what a run changed."""
    state: dict = {"checkouts": {}, "remotes": {}}
    for checkout in checkouts:
        state["checkouts"][checkout.relative_to(dest).as_posix()] = {
            "branches": git(
                checkout, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"
            ),
            "worktrees": {
                worktree.resolve().relative_to(dest).as_posix(): checkout_state(worktree)
                for worktree in worktree_paths(checkout)
            },
        }
    for remote in sorted(dest.glob("*.git")):
        state["remotes"][remote.name] = remote_refs(dest, remote.name)
    (dest / "_snapshot.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def expect(
    dest: Path,
    removed_worktrees: Sequence[str] = (),
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
    checkouts: Sequence[tuple[str, str, str, str]] = (),
    status: str = "In progress",
    blocker: str = "None",
    depends_on: str = "None",
    more_keys: Sequence[str] = (),
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


def heading_anchor(heading: str) -> str:
    """The link anchor GitHub gives a Markdown heading's text."""
    kept = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return kept.replace(" ", "-")


def packet(
    slug: str,
    title: str,
    summary: str,
    current_work_block: str,
    phases: Sequence[tuple[str, str, str, str]],
    requirements: str,
    log: Sequence[str],
    plan_note: str = "",
) -> dict[str, str]:
    """Return a packet in the shared PLC template, under `docs/plans/<slug>/`.

    `current_work_block` comes from `current_work(...)`. Each phase is
    (phase, name, state, details): the README `## Phases` row links its name
    to the `### <phase>: <name>` section of the implementation plan, which
    holds `details`. A phase's owner is the packet owner. `## Done when`
    links to SRD.md, which holds `requirements`. `plan_note` follows the
    phase sections in the plan.
    """
    root = f"docs/plans/{slug}"
    rows = "".join(
        f"| {phase} | [{name}](IMPLEMENTATION_PLAN.md#{heading_anchor(f'{phase}: {name}')})"
        f" | | {state} |\n"
        for phase, name, state, _ in phases
    )
    sections = "\n".join(
        f"### {phase}: {name}\n\n{details.rstrip()}\n" for phase, name, _, details in phases
    )
    readme = "\n".join(
        [
            f"# {title}\n",
            f"{summary}\n",
            current_work_block,
            f"## Phases\n\n{PHASES_HEADER}\n| --- | --- | --- | --- |\n{rows}",
            "## Done when\n",
            "The requirements and their checks are in [SRD.md](SRD.md).\n",
            "## Log\n",
            "".join(f"- {line}\n" for line in log),
        ]
    )
    plan = (
        f"# {title} implementation plan\n\n"
        "Phase state lives in the README's [Phases](README.md#phases) table.\n\n"
        f"{sections}"
    )
    return {
        f"{root}/README.md": readme,
        f"{root}/SRD.md": f"# {title} requirements\n\n{requirements}",
        f"{root}/IMPLEMENTATION_PLAN.md": f"{plan}\n{plan_note}" if plan_note else plan,
    }


def destination() -> Path:
    if len(sys.argv) != 2:
        sys.exit("usage: build.py <empty-destination-folder>")
    dest = Path(sys.argv[1]).resolve()
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"destination is not empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _without_fences(lines: list[str]) -> list[str]:
    """Drop fenced code blocks, so their contents are not read as structure."""
    kept, fenced = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            kept.append(line)
    return kept


def _starts_with_word(text: str, words: Sequence[str]) -> bool:
    text = text.strip().strip("*_`").lower()
    return any(
        text.startswith(word.lower()) and not text[len(word) : len(word) + 1].isalnum()
        for word in words
    )


def cells(row: str) -> list[str]:
    """The trimmed cells of a Markdown table row."""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


# Placeholder text a template leaves behind: N/A, TBD, or `<Something ...>`.
# Autolinks such as <https://...> are not placeholders.
PLACEHOLDER = re.compile(r"\bN/A\b|\bTBD\b|<(?![A-Za-z][\w+.-]*:)[A-Za-z][^<>\n]*>")


def packet_shape_problems(readme: str, plan: str = "") -> list[str]:
    """List the ways a packet README, and its plan, differ from the shared template.

    It covers the structure the evals rely on, not every rule: a summary under
    the title; one `## Current Work` first, starting with Status, Owner (by
    @handle) and a date-first Last updated, with at most 12 keys; `## Phases`
    with a Phase table whose State (or, in a converted packet, Status) column
    starts with a state word; the shared sections in template order; `## Log`
    last, with every item dated; no empty sections; no placeholders outside
    code; and, in the plan, no phase table with a State or Status column and
    a heading for every phase row that links to one. Fenced code blocks are
    skipped. An empty list means the shape is right.
    """
    problems = []
    lines = _without_fences(readme.splitlines())
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
    if "Phases" not in names:
        problems.append("needs a ## Phases section")
    before_log = names[:-1] if names[-1:] == ["Log"] else names
    shared = [name for name in before_log if name in SECTION_ORDER]
    if before_log[: len(shared)] != shared or shared != sorted(shared, key=SECTION_ORDER.index):
        problems.append(f"sections out of template order: {names}")
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
    header = [cell.lower() for cell in cells(phase_lines[0])] if phase_lines else []
    column = next((header.index(name) for name in ("state", "status") if name in header), None)
    if "Phases" in names and (header[:1] != ["phase"] or column is None):
        problems.append("## Phases needs a table with Phase and State columns")
    elif column is not None:
        for row in phase_lines[2:]:
            row_cells = cells(row)
            if len(row_cells) != len(header) or not _starts_with_word(
                row_cells[column], PHASE_STATE_WORDS
            ):
                problems.append(f"phase row needs every cell and a state word: {row}")
    log_items = [line for line in bodies.get("Log", []) if line.startswith("- ")]
    dated = [line for line in log_items if re.match(r"- \d{4}-\d{2}-\d{2} ", line)]
    if not dated:
        problems.append("## Log has no dated line")
    for line in log_items:
        if line not in dated:
            problems.append(f"Log line has no date: {line}")
    outside_code = re.sub(r"`[^`\n]*`", "", "\n".join(lines))
    if PLACEHOLDER.search(outside_code):
        problems.append("placeholder text (N/A, TBD or <...>) left in the README")
    plan_lines = _without_fences(plan.splitlines())
    anchors = {heading_anchor(line[4:]) for line in plan_lines if line.startswith("### ")}
    for line in plan_lines:
        plan_cells = [cell.lower() for cell in cells(line)] if line.startswith("|") else []
        if plan_cells[:1] == ["phase"] and ("state" in plan_cells or "status" in plan_cells):
            problems.append(f"phase state table outside the README: {line}")
    if plan:
        for anchor in re.findall(r"\(IMPLEMENTATION_PLAN\.md#([^)]+)\)", "\n".join(phase_lines)):
            if anchor not in anchors:
                problems.append(f"phase row links to a missing plan heading: #{anchor}")
    return problems
