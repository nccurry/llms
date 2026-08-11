"""Human-readable tables and structured YAML output for CLI results."""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

import yaml


class _ReadableDumper(yaml.SafeDumper):
    """Safe YAML dumper that uses literal blocks for multiline strings."""


class _ScalarDumper(Protocol):
    """Typed subset of PyYAML's scalar representation API."""

    def represent_scalar(
        self,
        tag: str,
        value: str,
        style: str | None = None,
    ) -> yaml.nodes.ScalarNode:
        """Create one YAML scalar node."""

        ...


def _represent_string(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
    """Use YAML's literal style when a string contains line breaks."""

    style = "|" if "\n" in value else None
    typed_dumper = cast("_ScalarDumper", dumper)
    return typed_dumper.represent_scalar("tag:yaml.org,2002:str", value, style)


_ReadableDumper.add_representer(str, _represent_string)


@dataclass(frozen=True, slots=True)
class TableColumn:
    """One field selected for a compact command-specific table."""

    key: str
    heading: str
    max_width: int
    always: bool = False


_TABLE_VIEWS = {
    "list": (
        TableColumn("name", "NAME", 28, always=True),
        TableColumn("type", "TYPE", 7, always=True),
        TableColumn("status", "STATUS", 9, always=True),
        TableColumn("repo", "REPOSITORY", 26, always=True),
        TableColumn("branch", "BRANCH", 34, always=True),
        TableColumn("model", "MODEL", 28),
        TableColumn("last_used_at", "LAST USED", 16),
    ),
    "doctor": (
        TableColumn("name", "CHECK", 24),
        TableColumn("status", "STATUS", 8),
        TableColumn("message", "DETAIL", 56),
        TableColumn("hint", "NEXT STEP", 48),
    ),
    "secrets status": (
        TableColumn("sandbox_env", "SECRET", 28),
        TableColumn("status", "STATUS", 20),
        TableColumn("source_available", "SOURCE", 8),
        TableColumn("registered", "REGISTERED", 10),
        TableColumn("hosts", "HOSTS", 32),
        TableColumn("reason", "DETAIL", 48),
    ),
    "secrets sync": (
        TableColumn("sandbox_env", "SECRET", 28),
        TableColumn("action", "ACTION", 14),
        TableColumn("status", "STATUS", 20),
        TableColumn("registered", "REGISTERED", 10),
        TableColumn("hosts", "HOSTS", 32),
        TableColumn("reason", "DETAIL", 48),
    ),
}


def _scalar_text(value: object) -> str:
    """Render one scalar or compact nested value for human output."""

    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _repository_label(value: object) -> str:
    """Shorten a repository path to its owner and directory names."""

    path = Path(str(value))
    return "/".join(path.parts[-2:]) if len(path.parts) > 1 else str(path)


def _timestamp_label(value: object) -> str:
    """Render an RFC 3339 timestamp in compact local time."""

    try:
        timestamp = datetime.fromisoformat(str(value)).astimezone()
    except ValueError:
        return str(value)
    return timestamp.strftime("%Y-%m-%d %H:%M")


def _cell_text(key: str, value: object) -> str:
    """Render a value with field-specific shortening for table cells."""

    if value is None:
        return _scalar_text(value)
    if key == "repo":
        return _repository_label(value)
    if key == "model" and isinstance(value, str):
        return value.rsplit("/", maxsplit=1)[-1]
    if key in {"created_at", "last_used_at", "synced_at"}:
        return _timestamp_label(value)
    if key == "hosts" and isinstance(value, list):
        return ", ".join(str(item) for item in cast("list[object]", value))
    if isinstance(value, str) and "\n" in value:
        return " ".join(value.split())
    return _scalar_text(value)


def _ellipsize(value: str, width: int) -> str:
    """Fit one table cell into a fixed width using a visible ellipsis."""

    if len(value) <= width:
        return value
    if width <= 1:
        return "…"
    return f"{value[: width - 1]}…"


def _table_columns(command: str, records: tuple[dict[str, object], ...]) -> tuple[TableColumn, ...]:
    """Choose command-specific columns or infer them from record keys."""

    configured = _TABLE_VIEWS.get(command)
    if configured:
        return tuple(
            column
            for column in configured
            if column.always
            or any(
                record.get(column.key) is not None and record.get(column.key) != ""
                for record in records
            )
        )

    keys = tuple(dict.fromkeys(key for record in records for key in record))
    return tuple(TableColumn(key, key.replace("_", " ").upper(), 32) for key in keys)


def _fit_widths(widths: list[int], headings: tuple[str, ...], terminal_width: int) -> list[int]:
    """Shrink flexible table columns until the row fits the terminal."""

    separators = max(0, len(widths) - 1) * 2
    available = max(40, terminal_width) - separators
    minimums = [
        min(width, max(4, len(heading))) for width, heading in zip(widths, headings, strict=True)
    ]
    fitted = widths.copy()

    while sum(fitted) > available:
        index = max(range(len(fitted)), key=lambda item: fitted[item] - minimums[item])
        surplus = fitted[index] - minimums[index]
        if surplus <= 0:
            break
        fitted[index] -= min(surplus, sum(fitted) - available)

    return fitted


def _render_table(
    command: str,
    records: tuple[dict[str, object], ...],
    terminal_width: int,
) -> str:
    """Render a homogeneous record list as an aligned terminal table."""

    columns = _table_columns(command, records)
    if not columns:
        return "No results."

    headings = tuple(column.heading for column in columns)
    rows = tuple(
        tuple(_cell_text(column.key, record.get(column.key)) for column in columns)
        for record in records
    )
    widths = [
        min(column.max_width, max(len(column.heading), *(len(row[index]) for row in rows)))
        for index, column in enumerate(columns)
    ]
    widths = _fit_widths(widths, headings, terminal_width)

    def render_row(values: tuple[str, ...]) -> str:
        """Pad and join one row using the fitted column widths."""

        cells = [_ellipsize(value, width) for value, width in zip(values, widths, strict=True)]
        return "  ".join(
            cell.ljust(width) if index < len(cells) - 1 else cell
            for index, (cell, width) in enumerate(zip(cells, widths, strict=True))
        ).rstrip()

    header = render_row(headings)
    divider = render_row(tuple("-" * width for width in widths))
    return "\n".join((header, divider, *(render_row(row) for row in rows)))


def _render_tree(value: object, indent: int = 0) -> list[str]:
    """Render nested mappings and lists as a readable indented tree."""

    prefix = " " * indent
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        if not mapping:
            return [f"{prefix}{{}}"]

        lines: list[str] = []
        for key, child in mapping.items():
            label = str(key).replace("_", " ")
            if isinstance(child, str) and "\n" in child:
                lines.append(f"{prefix}{label}: |")
                lines.extend(f"{prefix}  {line}" for line in child.rstrip("\n").splitlines())
            elif isinstance(child, (dict, list, tuple)):
                if not child:
                    lines.append(f"{prefix}{label}: {'{}' if isinstance(child, dict) else '[]'}")
                else:
                    lines.append(f"{prefix}{label}:")
                    lines.extend(_render_tree(cast("object", child), indent + 2))
            else:
                lines.append(f"{prefix}{label}: {_scalar_text(child)}")
        return lines

    if isinstance(value, (list, tuple)):
        items = cast("list[object] | tuple[object, ...]", value)
        if not items:
            return [f"{prefix}[]"]

        lines = []
        for child in items:
            if isinstance(child, (dict, list, tuple)):
                lines.append(f"{prefix}-")
                lines.extend(_render_tree(cast("object", child), indent + 2))
            else:
                lines.append(f"{prefix}- {_scalar_text(child)}")
        return lines

    return [f"{prefix}{_scalar_text(value)}"]


def _record_list(value: list[object]) -> tuple[dict[str, object], ...] | None:
    """Return a typed record list when every item is a string-keyed mapping."""

    records: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        mapping = cast("dict[object, object]", item)
        if not all(isinstance(key, str) for key in mapping):
            return None
        records.append(cast("dict[str, object]", mapping))
    return tuple(records)


def render_text(command: str, value: object, *, terminal_width: int | None = None) -> str:
    """Render any CLI result as a table, tree, list, or scalar."""

    if isinstance(value, list):
        items = cast("list[object]", value)
        if not items:
            return "No results."

        records = _record_list(items)
        if records is not None:
            width = terminal_width or shutil.get_terminal_size(fallback=(120, 24)).columns
            return _render_table(command, records, width)

    return "\n".join(_render_tree(cast("object", value)))


def dump_yaml(value: object) -> str:
    """Serialize JSON-compatible command output as stable, readable YAML."""

    return yaml.dump(
        value,
        Dumper=_ReadableDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=120,
    )
