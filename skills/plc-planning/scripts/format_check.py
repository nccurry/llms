"""Check PLC packets against the shared template.

Usage:
  python3 format_check.py [PLANS_FOLDER ...] [--packet PATH ...]
                          [--people NAME=HANDLE ...] [--strict]

Plans folders: checks every packet in their planned/ and in-progress/ folders.
--packet: checks one packet folder or one-file plan, in any lifecycle folder.
--people: names that must appear with their handle in Owner lines.
Default mode checks the structure every active packet must have. --strict
adds the content rules: evidence, reasons, blockers and folder agreement.
Prints one line per finding. Exit 0: nothing found; 1: findings; 2: bad path
or arguments.
"""
import argparse, pathlib, re, sys

# The shared template's words (packet status and phase state, with the older words it accepts).
PACKET_WORDS = {"Planned": ["Draft", "Ready", "Proposed"],
                "In progress": ["In-progress", "Developing", "Reviewing", "Active"],
                "Blocked": [], "Complete": ["Completed", "Closed", "Done"],
                "Archived": [], "Superseded": []}
PHASE_WORDS = {"Planned": ["Not started", "Pending", "Todo"], "In progress": ["Active", "Started"],
               "Implemented": [], "Merged": ["Delivered"],
               "Verified": ["Complete", "Completed", "Done", "Accepted", "Passed"],
               "Live": [], "Blocked": [], "Deferred": [], "Dropped": []}
FOLDER_STATUS = {"planned": {"Planned", "Blocked"}, "in-progress": {"In progress", "Blocked"},
                 "completed": {"Complete"}, "archived": {"Archived", "Superseded"}}
FINISHED = {"Verified", "Live", "Deferred", "Dropped"}
FIRST_KEYS = ["status", "owner", "last updated"]
REASONS = re.compile(r"(superseded|duplicate|obsolete|won'?t do)\b", re.I)
FLAT = re.compile(r"-(?:srd|sadd|prd|plan|implementation-plan)\.md$")
CURRENT = re.compile(r"## current work\s*$", re.I)
OTHER_STATUS = re.compile(r"## (lifecycle|status)\b", re.I)
KEY = re.compile(r"- (?:\*\*)?([A-Z][A-Za-z /-]*?):(?:\*\*)?(?:\s+(.*))?$")
STATUS_KEYS = {"status", "state", "owner", "owners", "last updated", "updated"}

found = 0


def report(path, line, text):
    global found
    found += 1
    print(f"{path}:{line}: {text}" if line else f"{path}: {text}")


def words(table):
    return {w.lower(): canon for canon, others in table.items() for w in [canon, *others]}


PACKET, PHASE = words(PACKET_WORDS), words(PHASE_WORDS)


def word(table, text):
    """The canonical word that starts the text, ignoring case and emphasis, or None."""
    text = re.sub(r"^[*_`\s]+", "", text).lower()
    for w in sorted(table, key=len, reverse=True):
        if text.startswith(w) and not re.match(r"[\w-]", text[len(w):len(w) + 1]):
            return table[w]
    return None


def note(text):
    """The text after ' — ', or ''."""
    return text.split(" — ", 1)[1].strip() if " — " in text else ""


def sections(lines):
    """Each ## section as (heading, first line index, end index)."""
    heads = [i for i, line in enumerate(lines) if line.startswith("## ")] + [len(lines)]
    return [(lines[a][3:].strip(), a, b) for a, b in zip(heads, heads[1:])]


def cells(line):
    """The cells of a table row. An escaped pipe (\\|) stays inside its cell."""
    line = line.strip()
    line = line[1:] if line.startswith("|") else line
    line = line[:-1] if line.endswith("|") and not line.endswith("\\|") else line
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def tables(lines, start=0, end=None):
    """Each Markdown table as (header line number, header cells, [(line number, cells)])."""
    out, i, end = [], start, len(lines) if end is None else end
    while i < end:
        if lines[i].lstrip().startswith("|") and i + 1 < end and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = cells(lines[i])
            rows, j = [], i + 2
            while j < end and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, cells(lines[j])))
                j += 1
            out.append((i + 1, header, rows))
            i = j
        else:
            i += 1
    return out


def state_column(header):
    heads = [h.lower() for h in header]
    if not heads or heads[0] != "phase":
        return None
    return next((heads.index(h) for h in ("state", "status") if h in heads), -1)


def check_phases(path, lines, start, end, lifecycle, strict):
    found_table = False
    for n, header, rows in tables(lines, start, end):
        column = state_column(header)
        if column is None:
            continue
        if not found_table and column < 0:
            report(path, n, "phases: the ## Phases table has no State column")
        found_table = True
        if column < 0:
            continue
        for m, cells in rows:
            if cells[0] in ("", "—", "-"):
                continue
            if len(cells) != len(header):
                report(path, m, f"phases: row has {len(cells)} cells, header has {len(header)}")
                continue
            cell = cells[column]
            state = word(PHASE, cell)
            if state is None:
                report(path, m, f"phase state: {cell[:60] or '(empty)'}")
                continue
            if not strict:
                continue
            if state in ("Verified", "Live") and not note(cell):
                report(path, m, f"strict: {state} with no evidence after ' — '")
            if state == "Dropped" and not REASONS.match(note(cell)):
                report(path, m, "strict: Dropped with no reason word")
            if lifecycle == "completed" and state not in FINISHED:
                report(path, m, f"strict: {state} phase in a completed packet")
    return found_table


def check_readme(path, lifecycle, people, strict):
    lines = path.read_text(encoding="utf-8").splitlines()
    title = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    after = next((line for line in lines[(title if title is not None else 0) + 1:] if line.strip()), "")
    if title is None or not after or after.startswith("#"):
        report(path, 1, "summary: no paragraph directly under the title")
    parts = sections(lines)
    current = [p for p in parts if CURRENT.match("## " + p[0])]
    keys = []
    if len(current) != 1:
        report(path, 1, f"status block: {len(current)} ## Current Work sections (needs 1)")
    else:
        _, a, b = current[0]
        keys = [(k[1].lower(), i + 1, k[2] or "") for i in range(a + 1, b) if (k := KEY.match(lines[i]))]
    for heading, a, b in parts:
        if OTHER_STATUS.match("## " + heading):
            for i in range(a + 1, b):
                k = KEY.match(lines[i])
                if k and k[1].lower() in STATUS_KEYS:
                    report(path, i + 1, f"status block: {k[1]} line outside ## Current Work")
    if len(current) == 1:
        names = [k[0] for k in keys]
        if names[:3] != FIRST_KEYS:
            report(path, current[0][1] + 1, "status block: Status, Owner and Last updated must come first, in that order")
        if len(keys) > 12:
            report(path, current[0][1] + 1, f"status block: {len(keys)} keys (at most 12)")
        get = {k[0]: (k[1], k[2]) for k in reversed(keys)}
        status = get.get("status")
        if status is None:
            report(path, current[0][1] + 1, "status block: no Status line")
        elif word(PACKET, status[1]) is None:
            report(path, status[0], f"status line: {status[1][:60] or '(empty)'}")
        owner = get.get("owner")
        if owner is None:
            report(path, current[0][1] + 1, "owner: no Owner line")
        else:
            for name, handle in people:
                if re.search(rf"(?<![@\w]){re.escape(name)}\b", owner[1]) and f"@{handle}" not in owner[1]:
                    report(path, owner[0], f"owner: {name} without @{handle}")
        updated = get.get("last updated")
        if updated is None or not re.match(r"\d{4}-\d{2}-\d{2}", updated[1]):
            report(path, updated[0] if updated else current[0][1] + 1, "updated: no date-first Last updated line")
        if strict and status is not None and word(PACKET, status[1]):
            value = word(PACKET, status[1])
            if lifecycle in FOLDER_STATUS and value not in FOLDER_STATUS[lifecycle]:
                report(path, status[0], f"strict: status {value} disagrees with folder {lifecycle}/")
            blocker = get.get("blocker")
            if value == "Blocked" and (blocker is None or blocker[1].strip().rstrip(".").lower() in ("", "none")):
                report(path, status[0], "strict: Blocked with no Blocker")
            if value in ("Archived", "Superseded") and not REASONS.match(note(status[1])):
                report(path, status[0], f"strict: {value} with no reason word")
    if not any(line.strip() == "## Log" for line in lines):
        report(path, 1, "log: no ## Log section")
    phases = [p for p in parts if p[0] == "Phases"]
    has_table = phases and check_phases(path, lines, phases[0][1], phases[0][2], lifecycle, strict)
    plan = path.with_name("IMPLEMENTATION_PLAN.md") if path.name == "README.md" else None
    for file, text in ((path, lines), (plan, plan.read_text(encoding="utf-8").splitlines() if plan and plan.exists() else [])):
        for n, header, _ in tables(text):
            column = state_column(header)
            if column is None:
                continue
            inside = file == path and phases and phases[0][1] < n <= phases[0][2]
            if not inside and column >= 0:
                report(file, n, "phases: phase state outside the README ## Phases table")
            if not inside and not has_table and file == path:
                report(file, n, "phases: phase table is not under ## Phases")


def check(target, people, strict):
    if target.name == "README.md" and target.is_file():
        target = target.parent
    readme = target / "README.md" if target.is_dir() else target
    lifecycle = target.resolve().parent.name
    if not readme.exists():
        report(target, None, "packet folder has no README.md")
        return
    check_readme(readme, lifecycle, people, strict)


parser = argparse.ArgumentParser()
parser.add_argument("plans", nargs="*", help="plans folders, such as docs/plans")
parser.add_argument("--packet", action="append", default=[], help="one packet folder or one-file plan")
parser.add_argument("--people", nargs="*", default=[], help="NAME=HANDLE pairs: names that need their @handle in Owner lines")
parser.add_argument("--strict", action="store_true", help="also check evidence, reasons, blockers and folders")
args = parser.parse_args()
for pair in args.people:
    if "=" not in pair:
        parser.error(f"--people takes NAME=HANDLE pairs, got {pair!r}; put plans folders before --people")
if not args.plans and not args.packet:
    parser.error("give at least one plans folder or --packet")
people = [tuple(p.split("=", 1)) for p in args.people]
for path in [*args.plans, *args.packet]:
    if not pathlib.Path(path).exists():
        print(f"no such path: {path}", file=sys.stderr)
        sys.exit(2)
for plans in args.plans:
    for lifecycle in ("planned", "in-progress"):
        folder = pathlib.Path(plans, lifecycle)
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir()):
            if entry.is_dir() and any(entry.glob("*.md")):
                check(entry, people, args.strict)
            elif entry.name.startswith("plc-") and entry.suffix == ".md" and not FLAT.search(entry.name):
                check(entry, people, args.strict)
for packet in args.packet:
    check(pathlib.Path(packet), people, args.strict)
sys.exit(1 if found else 0)
