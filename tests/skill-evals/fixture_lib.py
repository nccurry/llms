"""Shared helpers for the plc-checkpoint, wrap-this-up and plc-planning eval cases.

Each case's fixture/build.py calls these helpers to create, under a destination
folder: a bare `<name>.git` remote, a primary checkout `<name>/`, and campaign
worktrees under `<name>-wt/<campaign>/<checkout>`. Nothing here needs network
access or a PR host. Every git command runs without the developer's own git
config, so fixtures build the same way on every machine.

The checkers and fixture tests use the git helpers and `packet_shape_problems`,
which checks a packet against the shared PLC template: the planning skill's
shipped format check, plus the rules only the evals hold new packets to.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

# Every fixture packet's owner. An invented handle: fixtures never name real people.
OWNER = "@alex"

# Each fixture repository ignores the bytecode its tests write.
GITIGNORE = "__pycache__/\n*.py[co]\n.pytest_cache/\n"

# The planning skill's format check, which owns the template's words and
# structure rules.
FORMAT_CHECK = Path(__file__).resolve().parents[2] / "skills/plc-planning/scripts/format_check.py"

PHASES_HEADER = "| Phase | Name | Owner | State |"


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


def packet_file_hashes(path: Path) -> dict[str, str]:
    """The SHA-256 of each file under a checkout's docs/plans, by relative path."""
    return {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted((path / "docs" / "plans").rglob("*"))
        if file.is_file()
    }


def checkout_state(path: Path) -> dict:
    """Head, changed paths, and packet file hashes for one checkout or worktree."""
    return {
        "head": git(path, "rev-parse", "HEAD"),
        "branch": git(path, "branch", "--show-current"),
        "status_paths": sorted(status_paths(path)),
        "packet_files": packet_file_hashes(path),
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


# Most fixtures' resume check: their work is in the checkouts they list.
RESUME_CHECK = "`git worktree list` → the primary checkout and the checkouts below"


def current_work(
    last_updated: str,
    next_action: str,
    current_state: str,
    checkouts: Sequence[tuple[str, str, str, str]] = (),
    status: str = "In progress",
    blocker: str = "None",
    depends_on: str = "None",
    resume_check: str = RESUME_CHECK,
    more_keys: Sequence[str] = (),
) -> str:
    """The `## Current Work` block of the shared PLC template, with every key.

    `checkouts` rows are (checkout, branch, owner, state) for the "Where the
    work lives" table. `more_keys` are optional `Key: value` lines, such as a
    `Replaces` line, added after the template's keys.
    """
    keys = [
        f"Status: {status}",
        f"Owner: {OWNER}",
        f"Last updated: {last_updated}",
        f"Next action: {next_action}",
        f"Blocker: {blocker}",
        f"Depends on: {depends_on}",
        f"Current state: {current_state}",
        f"Resume check: {resume_check}",
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


@functools.cache
def format_check() -> ModuleType:
    """The planning skill's shipped format check, loaded by file path.

    It loads on first use, so building a fixture does not need it, and it
    writes no bytecode into the skills folder.
    """
    spec = importlib.util.spec_from_file_location("format_check", FORMAT_CHECK)
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def _sections(text: str) -> list[tuple[str, list[str], list[str]]]:
    """Each `## ` section of Markdown text: (heading, lines, raw lines).

    Headings inside fenced code blocks don't count. `lines` has fenced lines
    blanked out, as the shipped check reads them; `raw lines` keeps them.
    """
    raw = text.splitlines()
    lines = format_check().unfenced(raw)
    heads = [i for i, line in enumerate(lines) if line.startswith("## ")]
    return [
        (lines[a][3:].strip(), lines[a + 1 : b], raw[a + 1 : b])
        for a, b in zip(heads, heads[1:] + [len(lines)])
    ]


def section_lines(text: str, name: str) -> list[str]:
    """The lines of the first `## <name>` section, with fenced lines blanked."""
    return next((lines for heading, lines, _ in _sections(text) if heading == name), [])


def _key_value(lines: Sequence[str], key: str) -> str | None:
    """The value of the first `- Key: value` line, allowing bold keys."""
    pattern = re.compile(rf"- (?:\*\*)?{re.escape(key)}(?:\*\*)?:(?:\*\*)?\s+(.*)$")
    return next((match[1] for line in lines if (match := pattern.match(line))), None)


def _phase_rows(readme: str) -> list[list[str]]:
    """The cells of each line of the `## Phases` table, header and divider included."""
    rows = section_lines(readme, "Phases")
    return [format_check().cells(line) for line in rows if line.lstrip().startswith("|")]


def phase_state(readme: str, phase: str) -> str | None:
    """The canonical state word of `phase`'s row in a README's `## Phases` table."""
    rows = _phase_rows(readme)
    header = [cell.lower() for cell in rows[0]] if rows else []
    column = next((header.index(name) for name in ("state", "status") if name in header), None)
    row = next((row for row in rows[2:] if row[0] == phase), None)
    if column is None or row is None or column >= len(row):
        return None
    fc = format_check()
    return fc.lookup_word(fc.PHASE_WORDS, row[column])


def packet_status(readme: str) -> str | None:
    """The canonical packet status word of a README's Current Work block."""
    value = _key_value(section_lines(readme, "Current Work"), "Status")
    fc = format_check()
    return fc.lookup_word(fc.PACKET_WORDS, value) if value is not None else None


def names_handle(text: str, handle: str) -> bool:
    """True when text names `handle`, such as @alex, and not a longer handle."""
    return re.search(rf"(?<![\w@]){re.escape(handle)}(?![\w-]|\.\w)", text) is not None


def owner_value(readme: str) -> str:
    """The value of a README's Owner line in Current Work, or ''."""
    return _key_value(section_lines(readme, "Current Work"), "Owner") or ""


def _readme_and_plan(packet: Path) -> tuple[str, str]:
    """The README text of a packet folder or one-file plan, and its plan text."""
    readme = packet / "README.md" if packet.is_dir() else packet
    plan = readme.with_name("IMPLEMENTATION_PLAN.md")
    has_plan = readme.name == "README.md" and plan.is_file()
    plan_text = plan.read_text(encoding="utf-8") if has_plan else ""
    return readme.read_text(encoding="utf-8"), plan_text


# The shared sections, in template order. Other sections go after them and
# before `## Log`, which is last.
SECTION_ORDER = ("Current Work", "Phases", "Done when", "Open questions")
# The template's Current Work keys after Status, Owner and Last updated, which
# the shipped check already requires.
MORE_TEMPLATE_KEYS = ("Next action", "Blocker", "Depends on", "Current state", "Resume check")
# Placeholder text a template leaves behind: N/A, TBD, or `<Something ...>`.
# Autolinks such as <https://...> are not placeholders.
PLACEHOLDER = re.compile(r"\bN/A\b|\bTBD\b|<(?![A-Za-z][\w+.-]*:)[A-Za-z][^<>\n]*>")
LOG_DATE = re.compile(r"- \d{4}-\d{2}-\d{2}\b")


def eval_only_problems(packet: Path, owner: str | None = None) -> list[str]:
    """The template rules the shipped format check leaves out, as `eval:` lines.

    The shipped check stays structural, so that converted packets, which keep
    their own sections and older words, pass it. The evals' packets are new:
    fixture packets and the plans an eval asks an agent to write. So these
    rules hold for them too:

    - the shared sections come first, in template order, and `## Log` is last;
    - there is a `## Phases` section;
    - Current Work has every template key and the "Where the work lives"
      table;
    - every Log item starts with a YYYY-MM-DD date;
    - no section is empty, and no placeholder (N/A, TBD, `<...>`) is left
      outside code;
    - each phase row's link to IMPLEMENTATION_PLAN.md finds its heading;
    - when `owner` is given, the Owner line names that handle, as a case's
      prompt asks.

    Fenced code blocks are read as the shipped check reads them: their lines
    are not structure, but they are content, so a section that holds only a
    code block is not empty.
    """
    readme, plan = _readme_and_plan(Path(packet))
    sections = _sections(readme)
    names = [name for name, _, _ in sections]
    problems = []
    before_log = names[:-1] if names[-1:] == ["Log"] else names
    shared = [name for name in before_log if name in SECTION_ORDER]
    in_order = shared == sorted(shared, key=SECTION_ORDER.index)
    if before_log[: len(shared)] != shared or not in_order:
        problems.append(f"eval: sections out of template order: {names}")
    if names[-1:] != ["Log"]:
        problems.append("eval: ## Log is not the last section")
    if "Phases" not in names:
        problems.append("eval: no ## Phases section")
    for name, _, raw in sections:
        if not any(line.strip() for line in raw):
            problems.append(f"eval: empty section ## {name}")
    current_work = section_lines(readme, "Current Work")
    if "Current Work" in names:
        for key in MORE_TEMPLATE_KEYS:
            if _key_value(current_work, key) is None:
                problems.append(f"eval: Current Work has no {key} line")
        table_start = next(
            (i for i, line in enumerate(current_work) if line.startswith("Where the work lives")),
            None,
        )
        rows = [] if table_start is None else current_work[table_start + 1 :]
        if not any(line.lstrip().startswith("|") for line in rows):
            problems.append('eval: Current Work has no "Where the work lives" table')
    for line in section_lines(readme, "Log"):
        if line.startswith("- ") and not LOG_DATE.match(line):
            problems.append(f"eval: Log line has no date: {line}")
    outside_code = re.sub(r"`[^`\n]*`", "", "\n".join(format_check().unfenced(readme.splitlines())))
    if PLACEHOLDER.search(outside_code):
        problems.append("eval: placeholder text (N/A, TBD or <...>) left in the README")
    if plan:
        plan_lines = format_check().unfenced(plan.splitlines())
        anchors = {heading_anchor(line[4:]) for line in plan_lines if line.startswith("### ")}
        for row in _phase_rows(readme)[2:]:
            for anchor in re.findall(r"\(IMPLEMENTATION_PLAN\.md#([^)]+)\)", " ".join(row)):
                if anchor not in anchors:
                    problems.append(f"eval: phase row links to a missing plan heading: #{anchor}")
    if owner is not None and not names_handle(owner_value(readme), owner):
        problems.append(f"eval: Owner does not name {owner}")
    return problems


def packet_shape_problems(
    packet: Path, lifecycle: str | None = None, owner: str | None = None
) -> list[str]:
    """Every way a packet folder or one-file plan breaks the shared template.

    The shipped format check's findings in strict mode, checked against
    `lifecycle` when given, then `eval_only_problems`. An empty list means the
    packet is right.
    """
    shipped = format_check().check_packet(Path(packet), strict=True, lifecycle=lifecycle)
    return [*shipped, *eval_only_problems(packet, owner)]
