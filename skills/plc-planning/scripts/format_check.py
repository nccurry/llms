"""Check PLC packets against the shared PLC template.

Usage:
  python3 format_check.py [PLANS_FOLDER ...] [--packet PATH ...]
                          [--people NAME=HANDLE ...] [--lifecycle FOLDER]
                          [--strict]

A plans folder: checks every packet in its planned/ and in-progress/ folders.
  It skips flat design files, such as plc-012-retry-srd.md.
--packet: checks one packet folder or one-file plan, in any lifecycle folder.
--people: NAME=HANDLE pairs. An Owner line that names NAME must also give
  @HANDLE. HANDLE may start with @. Put plans folders before --people.
--lifecycle: checks each --packet as if it were in this lifecycle folder, for
  example `completed` before a finished packet moves there.

Default mode checks the structure every active packet needs: a summary under
the title; one ## Current Work block that starts with Status, Owner and Last
updated, uses known words and names an @handle; a ## Log section; and status
only in the README. Phase state belongs in the README's ## Phases table, not
in IMPLEMENTATION_PLAN.md, SRD.md or SADD.md: not in a phase table, a
`- Status:` or `- State:` line that starts with a status or phase state word,
or a `- Lifecycle:` line that starts with a status word. When SRD.md exists,
it holds the requirements: the README's ## Done when holds one line pointing
there, and no requirement ID from SRD.md's requirements table (the table
whose first column is ID). HTML comments in ## Done when do not count. Fenced
code blocks are ignored.

--strict also checks the five rules across fields:
  1. Status matches the lifecycle folder.
  2. A Blocked packet names its Blocker.
  3. A Verified or Live phase has evidence after " — ".
  4. A Dropped phase, and an Archived or Superseded packet, starts its note
     with a reason word: superseded, duplicate, obsolete or won't do.
  5. A packet in completed/ has only Verified, Live, Deferred or Dropped
     phases.

Prints one line per finding. Exit 0: nothing found. 1: findings. 2: a bad path
or argument, nothing to check, or a file that could not be read.

Python API, for tools that load this file by path:
  PACKET_WORDS, PHASE_WORDS
      Each canonical word, mapped to the older spellings it accepts.
  cells(line) -> list[str]
      The cells of a Markdown table row.
  lookup_word(words, text) -> str | None
      The canonical word from PACKET_WORDS or PHASE_WORDS that starts text.
  check_packet(path, people=(), strict=False, lifecycle=None) -> list[str]
      The finding lines for one packet, exactly as printed. Raises ReadError
      when a file cannot be read.
  is_packet(path) -> bool
      Whether an entry of a lifecycle folder is a packet: a folder with
      Markdown files, or a one-file plc-*.md plan that is not a side file.
  requirement_rows(lines) -> list[tuple[int, list[str]]]
      The rows of SRD.md's requirements table, the table whose first column
      is ID, as (1-based line, cells).
  unfenced(lines) -> list[str]
      The lines with each fenced code block, fences included, replaced by
      empty strings, so line numbers stay the same.
  main(argv=None) -> int
      The command line. Returns the exit code.
"""

import argparse
import re
import sys
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple

# Each canonical word, mapped to the older spellings it accepts.
PACKET_WORDS = {
    "Planned": ["Draft", "Ready", "Proposed"],
    "In progress": ["In-progress", "Developing", "Reviewing", "Active"],
    "Blocked": [],
    "Complete": ["Completed", "Closed", "Done"],
    "Archived": [],
    "Superseded": [],
}
PHASE_WORDS = {
    "Planned": ["Not started", "Pending", "Todo"],
    "In progress": ["Active", "Started"],
    "Implemented": [],
    "Merged": ["Delivered"],
    "Verified": ["Complete", "Completed", "Done", "Accepted", "Passed"],
    "Live": [],
    "Blocked": [],
    "Deferred": [],
    "Dropped": [],
}

# The rules across fields (--strict).
FOLDER_STATUS = {
    "planned": ("Planned", "Blocked"),
    "in-progress": ("In progress", "Blocked"),
    "completed": ("Complete",),
    "archived": ("Archived", "Superseded"),
}
ALLOWED_IN_COMPLETED = ("Verified", "Live", "Deferred", "Dropped")
NEEDS_EVIDENCE = ("Verified", "Live")
NEEDS_REASON = ("Dropped", "Archived", "Superseded")
REASON = re.compile(r"(superseded|duplicate|obsolete|won['’]?t do)\b", re.IGNORECASE)

# Structure.
OUTSIDE = "Phases: phase state outside the README ## Phases table"
ACTIVE_FOLDERS = ("planned", "in-progress")
FIRST_KEYS = ["status", "owner", "last updated"]
MAX_KEYS = 12
STATE_KEYS = {"status", "state"}
# Key lines that give status outside the README, by key, with the words that
# make them status. A Status line such as "Approved; ..." is not status.
OUTSIDE_STATUS_KEYS = {
    "status": (PHASE_WORDS, PACKET_WORDS),
    "state": (PHASE_WORDS, PACKET_WORDS),
    "lifecycle": (PACKET_WORDS,),
}
STATE_COLUMNS = ("state", "status")
OLD_STATE_COLUMNS = {"implementation", "verification", "delivery"}
MAX_BYTES = 4 * 1024 * 1024
OTHER_FILES = ("IMPLEMENTATION_PLAN.md", "SRD.md", "SADD.md")

# Flat design files sit beside a one-file plan, as plc-012-retry-srd.md sits
# beside plc-012-retry.md. They are not packets, so a plans folder skips them.
# A -plan.md file is such a side file only when a design file for the same
# name sits beside it; on its own it is a one-file plan.
SIDE_FILE = re.compile(r"-(?:srd|sadd|prd)\.md$")
PLAN_SIDE_FILE = re.compile(r"-(?:implementation-)?plan\.md$")

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
DIVIDER = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
PIPE = re.compile(r"(?<!\\)\|")
KEY = re.compile(r"- (?:\*\*)?([A-Z][A-Za-z /-]*?)(?:\*\*)?:(?:\*\*)?(?:\s+(.*))?$")
OLD_KEY = re.compile(r"\s*(?:[-*+]\s+)?(?:\*\*)?([A-Z][A-Za-z /-]*?)(?:\*\*)?:(?:\*\*)?(?:\s+(.*))?$")
# Old status sections: any heading that starts with Status, Lifecycle or
# Current status. An Owner line counts only under one of the exact headings.
OLD_STATUS_HEADING = re.compile(r"(?:status|lifecycle|current status)\b", re.IGNORECASE)
OWNER_HEADING = re.compile(r"(?:status(?: \(.*\)| — .*)?|lifecycle|current status)", re.IGNORECASE)
HANDLE = re.compile(r"(?<![\w@])@\w[\w.-]*")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
EMPHASIS = re.compile(r"^[*_`\s]+")


class ReadError(Exception):
    """A packet file that could not be read."""


class Section(NamedTuple):
    name: str  # the heading text after "## "
    start: int  # index of the heading line
    end: int  # index of the next "## " heading, or the line count


class Key(NamedTuple):
    name: str  # lowercased
    line: int  # 1-based
    value: str


class Table(NamedTuple):
    line: int  # 1-based line of the header row
    header: list
    rows: list  # (1-based line, cells)


def lookup_word(words, text):
    """The canonical word that starts text, ignoring case and emphasis, or None."""
    text = EMPHASIS.sub("", text).lower()
    spellings = {
        spelling.lower(): canonical
        for canonical, older in words.items()
        for spelling in [canonical, *older]
    }
    for spelling in sorted(spellings, key=len, reverse=True):
        ends_word = not re.match(r"[\w-]", text[len(spelling):])
        if text.startswith(spelling) and ends_word:
            return spellings[spelling]
    return None


def note(text):
    """The text after ' — ', or ''."""
    return text.split(" — ", 1)[1].strip() if " — " in text else ""


def has_reason(text):
    return bool(REASON.match(EMPHASIS.sub("", note(text))))


def is_none(value):
    """True when a value is empty or None, ignoring emphasis, code marks and a final period."""
    return value.strip(" *_`").rstrip(".").strip(" *_`").lower() in ("", "none")


def escape(text):
    """Text with non-printable characters, such as terminal escapes, written as escapes."""
    return "".join(char if char.isprintable() else repr(char)[1:-1] for char in text)


def shown(path):
    """A path as printed: forward slashes, non-printable characters escaped."""
    return escape(path.as_posix())


def finding(path, line, text):
    where = f"{shown(path)}:{line}" if line else shown(path)
    return f"{where}: {escape(text)}"


def read_lines(path):
    """The lines of a regular UTF-8 file. Raises ReadError when it cannot be read."""
    try:
        if not path.exists():
            raise ReadError(f"{shown(path)}: no such file")
        if not path.is_file():
            raise ReadError(f"{shown(path)}: not a regular file")
        if path.stat().st_size > MAX_BYTES:
            raise ReadError(f"{shown(path)}: larger than {MAX_BYTES // (1024 * 1024)} MiB")
        return path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ReadError(f"{shown(path)}: cannot read: {escape(str(error))}") from error


def unfenced(lines):
    """The lines with each fenced code block, fences included, blanked out."""
    out, fence = [], None
    for line in lines:
        marker = FENCE.match(line)
        if fence is None:
            if marker:
                fence = marker[1]
            out.append("" if marker else line)
            continue
        closes = (
            marker is not None
            and marker[1][0] == fence[0]
            and len(marker[1]) >= len(fence)
            and not line[marker.end():].strip()
        )
        if closes:
            fence = None
        out.append("")
    return out


def uncommented(lines):
    """The lines with HTML comments removed. A comment's line breaks stay, so
    line numbers stay the same."""
    if not lines:
        return []
    text = COMMENT.sub(lambda match: "\n" * match[0].count("\n"), "\n".join(lines))
    return text.split("\n")


def sections(lines):
    """Each ## section, in order."""
    heads = [i for i, line in enumerate(lines) if line.startswith("## ")]
    return [Section(lines[a][3:].strip(), a, b) for a, b in pairwise([*heads, len(lines)])]


def named(parts, name):
    """The sections whose heading is name, ignoring case."""
    return [part for part in parts if part.name.lower() == name]


def cells(line):
    """The cells of a Markdown table row. An escaped pipe (\\|) stays inside its cell."""
    line = line.strip()
    line = line[1:] if line.startswith("|") else line
    line = line[:-1] if line.endswith("|") and not line.endswith("\\|") else line
    return [cell.strip() for cell in PIPE.split(line)]


def is_row(line):
    """True for a table row: a line with an unescaped pipe, with or without edge pipes."""
    return bool(line.strip()) and bool(PIPE.search(line))


def tables(lines, start=0, end=None):
    """Each Markdown table between start and end, with or without edge pipes."""
    end = len(lines) if end is None else end
    out, i = [], start
    while i < end:
        has_divider = i + 1 < end and is_row(lines[i + 1]) and DIVIDER.match(lines[i + 1])
        if not (is_row(lines[i]) and has_divider):
            i += 1
            continue
        rows, j = [], i + 2
        while j < end and is_row(lines[j]):
            rows.append((j + 1, cells(lines[j])))
            j += 1
        out.append(Table(i + 1, cells(lines[i]), rows))
        i = j
    return out


def is_phase_table(table):
    return bool(table.header) and table.header[0].lower() == "phase"


def state_column(table):
    """The index of a phase table's State or Status column, or None."""
    heads = [head.lower() for head in table.header]
    return next((heads.index(name) for name in STATE_COLUMNS if name in heads), None)


def holds_phase_state(table):
    """True for a phase table with a State, Status, Implementation, Verification or
    Delivery column."""
    heads = {head.lower() for head in table.header}
    has_state = state_column(table) is not None or bool(heads & OLD_STATE_COLUMNS)
    return is_phase_table(table) and has_state


def check_summary(readme, raw, lines):
    title = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    start = 0 if title is None else title + 1
    after = next((line for line in raw[start:] if line.strip()), "")
    no_paragraph = title is None or not after or after.startswith("#") or FENCE.match(after)
    if not no_paragraph:
        return []
    return [finding(readme, 1, "summary: no paragraph directly under the title")]


def looks_like_status(key, value, heading):
    """True when a key line under an old status heading gives the packet's status."""
    if key in STATE_KEYS:
        return lookup_word(PACKET_WORDS, value) is not None
    if key in ("updated", "last updated"):
        return bool(DATE.match(EMPHASIS.sub("", value)))
    if key in ("owner", "owners"):
        return bool(OWNER_HEADING.fullmatch(heading))
    return False


def current_work_keys(lines, block):
    keys = []
    for i in range(block.start + 1, block.end):
        match = KEY.match(lines[i])
        if match:
            keys.append(Key(match[1].lower(), i + 1, match[2] or ""))
    return keys


def check_current_work(readme, lines, parts, people, strict, lifecycle):
    blocks = named(parts, "current work")
    found = []
    if len(blocks) != 1:
        message = f"Current Work: {len(blocks)} ## Current Work sections; a packet needs exactly one"
        found.append(finding(readme, 1, message))
    for part in parts:
        if not OLD_STATUS_HEADING.match(part.name):
            continue
        for i in range(part.start + 1, part.end):
            key = OLD_KEY.match(lines[i])
            if key and looks_like_status(key[1].lower(), key[2] or "", part.name):
                message = f"Current Work: {key[1]} line belongs in ## Current Work, not ## {part.name}"
                found.append(finding(readme, i + 1, message))
    if len(blocks) != 1:
        return found

    heading = blocks[0].start + 1
    keys = current_work_keys(lines, blocks[0])
    if [key.name for key in keys[:3]] != FIRST_KEYS:
        message = "Current Work: Status, Owner and Last updated must come first, in that order"
        found.append(finding(readme, heading, message))
    if len(keys) > MAX_KEYS:
        message = f"Current Work: {len(keys)} keys; at most {MAX_KEYS} are allowed"
        found.append(finding(readme, heading, message))
    first = {}
    for key in keys:
        first.setdefault(key.name, key)

    status = first.get("status")
    status_word = lookup_word(PACKET_WORDS, status.value) if status else None
    if status is None:
        found.append(finding(readme, heading, "Current Work: no Status line"))
    elif status_word is None:
        value = status.value[:60] or "(empty)"
        message = f"Current Work: Status does not start with a packet status word: {value}"
        found.append(finding(readme, status.line, message))

    owner = first.get("owner")
    if owner is None:
        found.append(finding(readme, heading, "Current Work: no Owner line"))
    else:
        if not HANDLE.search(owner.value):
            found.append(finding(readme, owner.line, "Current Work: Owner names no @handle"))
        for name, handle in people:
            handle = handle.removeprefix("@")
            names_person = re.search(rf"(?<![@\w]){re.escape(name)}\b", owner.value)
            gives_handle = re.search(rf"(?<![\w@])@{re.escape(handle)}(?![\w-]|\.\w)", owner.value)
            if names_person and not gives_handle:
                message = f"Current Work: Owner names {name} without @{handle}"
                found.append(finding(readme, owner.line, message))

    updated = first.get("last updated")
    if updated is None:
        found.append(finding(readme, heading, "Current Work: no Last updated line"))
    elif not DATE.match(updated.value):
        message = "Current Work: Last updated does not start with a YYYY-MM-DD date"
        found.append(finding(readme, updated.line, message))

    if strict and status_word:
        allowed = FOLDER_STATUS.get(lifecycle)
        if allowed and status_word not in allowed:
            needs = " or ".join(allowed)
            message = (
                f"strict: Status {status_word} does not match the {lifecycle}/ folder, "
                f"which needs {needs}"
            )
            found.append(finding(readme, status.line, message))
        blocker = first.get("blocker")
        if status_word == "Blocked" and (blocker is None or is_none(blocker.value)):
            message = "strict: Status is Blocked, but the Blocker line is missing or None"
            found.append(finding(readme, status.line, message))
        if status_word in NEEDS_REASON and not has_reason(status.value):
            message = f"strict: {status_word} note does not start with a reason word"
            found.append(finding(readme, status.line, message))
    return found


def check_phase_rows(readme, table, lifecycle, strict):
    found = []
    column = state_column(table)
    for line, row in table.rows:
        if row[0] in ("", "—", "-"):
            continue  # a note row
        if len(row) != len(table.header):
            message = f"Phases: row has {len(row)} cells, but the header has {len(table.header)}"
            found.append(finding(readme, line, message))
            continue
        cell = row[column]
        state = lookup_word(PHASE_WORDS, cell)
        if state is None:
            value = cell[:60] or "(empty)"
            message = f"Phases: State does not start with a phase state word: {value}"
            found.append(finding(readme, line, message))
            continue
        if not strict:
            continue
        if state in NEEDS_EVIDENCE and not note(cell):
            message = f"strict: {state} phase has no evidence after ' — '"
            found.append(finding(readme, line, message))
        if state in NEEDS_REASON and not has_reason(cell):
            message = f"strict: {state} note does not start with a reason word"
            found.append(finding(readme, line, message))
        if lifecycle == "completed" and state not in ALLOWED_IN_COMPLETED:
            allowed = ", ".join(ALLOWED_IN_COMPLETED[:-1]) + f" or {ALLOWED_IN_COMPLETED[-1]}"
            message = f"strict: {state} phase in a completed/ packet, which allows only {allowed}"
            found.append(finding(readme, line, message))
    return found


def check_phases_section(readme, lines, part, lifecycle, strict):
    """Findings for the README's ## Phases section, and whether it has a phase table."""
    in_section = tables(lines, part.start + 1, part.end)
    phase_tables = [table for table in in_section if is_phase_table(table)]
    if not phase_tables and in_section:
        message = "Phases: the ## Phases table's first column is not Phase"
        return [finding(readme, in_section[0].line, message)], False
    if not phase_tables:
        return [finding(readme, part.start + 1, "Phases: ## Phases has no table")], False
    found = []
    if state_column(phase_tables[0]) is None:
        message = "Phases: the ## Phases table has no State column"
        found.append(finding(readme, phase_tables[0].line, message))
    for table in phase_tables:
        if state_column(table) is not None:
            found += check_phase_rows(readme, table, lifecycle, strict)
    return found, True


def check_phase_tables(readme, lines, parts, lifecycle, strict):
    phases = named(parts, "phases")
    found, has_phase_table = [], False
    if phases:
        found, has_phase_table = check_phases_section(readme, lines, phases[0], lifecycle, strict)
    for table in tables(lines):
        inside = bool(phases) and phases[0].start < table.line - 1 < phases[0].end
        if inside or not is_phase_table(table):
            continue
        if holds_phase_state(table):
            found.append(finding(readme, table.line, OUTSIDE))
        if not has_phase_table:
            found.append(finding(readme, table.line, "Phases: phase table is not under ## Phases"))
    return found


def check_other_file(path, lines):
    """Findings for status kept in IMPLEMENTATION_PLAN.md, SRD.md or SADD.md."""
    found = [finding(path, table.line, OUTSIDE) for table in tables(lines) if holds_phase_state(table)]
    for i, line in enumerate(lines):
        key = KEY.match(line)
        words = OUTSIDE_STATUS_KEYS.get(key[1].lower()) if key else None
        if words and any(lookup_word(table, key[2] or "") for table in words):
            message = (
                f"Phases: {key[1]} line outside the README; "
                "status lives in its ## Current Work and ## Phases"
            )
            found.append(finding(path, i + 1, message))
    return found


def requirement_rows(lines):
    """The rows of SRD.md's requirements table, the table whose first column is
    ID, as (1-based line, cells)."""
    return [
        row
        for table in tables(lines)
        if table.header and table.header[0].strip("*_` ").lower() == "id"
        for row in table.rows
    ]


def requirement_id(row):
    """The ID in a requirements table row's first cell, or None for a note row."""
    words = row[1][0].strip("*_` ").split()
    return words[0].strip("*_`") if words and words[0] not in ("—", "-") else None


def check_done_when(readme, lines, parts, srd_lines):
    """Findings for a README ## Done when beside SRD.md, which holds the requirements."""
    done_when = named(parts, "done when")
    if not done_when:
        return []
    part = done_when[0]
    body = uncommented(lines[part.start + 1 : part.end])
    found = []
    filled = [line for line in body if line.strip()]
    if len(filled) > 1:
        message = f"Done when: {len(filled)} lines; with SRD.md it holds only the line pointing there"
        found.append(finding(readme, part.start + 1, message))
    ids = [req for req in map(requirement_id, requirement_rows(srd_lines)) if req]
    seen = set()
    for i, line in enumerate(body):
        for req in ids:
            if req in seen or not re.search(rf"(?<![\w-]){re.escape(req)}(?![\w-])", line):
                continue
            seen.add(req)
            message = f"Done when: {req} is also in SRD.md's requirements table; keep each requirement in one place"
            found.append(finding(readme, part.start + 2 + i, message))
    return found


def check_packet(path, people=(), strict=False, lifecycle=None):
    """The finding lines for one packet folder or one-file plan, exactly as printed.

    people: (name, handle) pairs. lifecycle: the lifecycle folder to check
    against; by default, the folder the packet is in. Raises ReadError when a
    file cannot be read.
    """
    target = Path(path)
    if target.name == "README.md" and target.is_file():
        target = target.parent
    found = []
    if target.is_dir() and target.name in FOLDER_STATUS:
        message = (
            f"packet folder is named like the {target.name}/ lifecycle folder; "
            "put it in a folder of its own"
        )
        found.append(finding(target, None, message))
    readme = target / "README.md" if target.is_dir() else target
    if target.is_dir() and not readme.exists():
        return [*found, finding(target, None, "packet folder has no README.md")]
    lifecycle = lifecycle or target.resolve().parent.name

    raw = read_lines(readme)
    others = []
    if readme.name == "README.md":
        for name in OTHER_FILES:
            other = readme.with_name(name)
            if other.exists():
                others.append((other, unfenced(read_lines(other))))
    lines = unfenced(raw)
    parts = sections(lines)

    found += check_summary(readme, raw, lines)
    found += check_current_work(readme, lines, parts, people, strict, lifecycle)
    if not named(parts, "log"):
        found.append(finding(readme, 1, "Log: no ## Log section"))
    found += check_phase_tables(readme, lines, parts, lifecycle, strict)
    srd = next((other_lines for other, other_lines in others if other.name == "SRD.md"), None)
    if srd is not None:
        found += check_done_when(readme, lines, parts, srd)
    for other, other_lines in others:
        found += check_other_file(other, other_lines)
    return found


def is_side_file(entry):
    if SIDE_FILE.search(entry.name):
        return True
    plan = PLAN_SIDE_FILE.search(entry.name)
    if not plan:
        return False
    stem = entry.name[: plan.start()]
    designs = [f"{stem}.md", f"{stem}-srd.md", f"{stem}-sadd.md", f"{stem}-prd.md"]
    return any((entry.parent / name).is_file() for name in designs)


def is_packet(entry):
    """Whether a lifecycle folder entry is a packet folder or a one-file plan."""
    if entry.is_dir():
        return any(entry.glob("*.md"))
    is_plan_file = entry.name.startswith("plc-") and entry.suffix == ".md"
    return is_plan_file and not is_side_file(entry)


def packets_in(plans):
    """The packets in a plans folder's planned/ and in-progress/ folders."""
    found = []
    for name in ACTIVE_FOLDERS:
        folder = plans / name
        if folder.is_dir():
            found += [entry for entry in sorted(folder.iterdir()) if is_packet(entry)]
    return found


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="format_check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("plans", nargs="*", help="plans folders, such as docs/plans")
    parser.add_argument("--packet", action="append", default=[], help="one packet folder or one-file plan")
    parser.add_argument(
        "--people",
        nargs="*",
        default=[],
        help="NAME=HANDLE pairs; an Owner line naming NAME must give @HANDLE",
    )
    parser.add_argument(
        "--lifecycle",
        choices=sorted(FOLDER_STATUS),
        help="check --packet paths as if they were in this lifecycle folder",
    )
    parser.add_argument("--strict", action="store_true", help="also check the rules across fields")
    args = parser.parse_args(argv)
    for pair in args.people:
        if "=" not in pair:
            hint = "put plans folders before --people"
            parser.error(f"--people takes NAME=HANDLE pairs, got {pair!r}; {hint}")
    if not args.plans and not args.packet:
        parser.error("give at least one plans folder or --packet")
    if args.lifecycle and args.plans:
        parser.error("--lifecycle works only with --packet")
    return args


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        args = parse_args(argv)
    except SystemExit as error:  # argparse exits on --help (0) and on bad arguments (2)
        return error.code if isinstance(error.code, int) else 2
    people = [tuple(pair.split("=", 1)) for pair in args.people]
    for path in [*args.plans, *args.packet]:
        if not Path(path).exists():
            print(f"no such path: {escape(path)}", file=sys.stderr)
            return 2

    packets = []
    for plans in map(Path, args.plans):
        if not any((plans / name).is_dir() for name in ACTIVE_FOLDERS):
            print(f"{shown(plans)}: no planned/ or in-progress/ folder", file=sys.stderr)
            return 2
        packets += packets_in(plans)
    packets += [Path(path) for path in args.packet]
    if not packets:
        print("nothing to check: no packets found", file=sys.stderr)
        return 2

    code = 0
    for packet in packets:
        try:
            found = check_packet(packet, people, args.strict, args.lifecycle)
        except ReadError as error:
            print(error, file=sys.stderr)
            code = 2
            continue
        for line in found:
            print(line)
        if found and code == 0:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
