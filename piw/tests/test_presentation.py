"""Human and YAML output rendering tests."""

import yaml

from piw.presentation import dump_yaml, render_text


def test_session_list_uses_a_compact_command_specific_table() -> None:
    """Session text keeps the useful summary while structured output retains every field."""

    output = render_text(
        "list",
        [
            {
                "name": "fix-exporter-metrics",
                "type": "branch",
                "sandbox": "piw-exporter-fix-exporter-metrics-a1b2c3d4",
                "status": "running",
                "repo": "/work/github.com/example/exporter",
                "branch": "piw/fix-exporter-metrics",
                "model": "provider/team/kimi-k3-max-preview",
                "created_at": "2026-08-11T17:51:20+00:00",
                "last_used_at": "2026-08-11T17:57:51+00:00",
            }
        ],
        terminal_width=160,
    )

    assert "NAME" in output
    assert "TYPE" in output
    assert "REPOSITORY" in output
    assert "example/exporter" in output
    assert "kimi-k3-max-preview" in output
    assert "sandbox" not in output.lower()
    assert "name=" not in output
    assert "+00:00" not in output


def test_record_tables_omit_columns_that_have_no_values() -> None:
    """Optional columns do not consume terminal width when every value is empty."""

    output = render_text(
        "doctor",
        [{"name": "git", "status": "pass", "message": "/usr/bin/git", "hint": None}],
        terminal_width=100,
    )

    assert "CHECK" in output
    assert "DETAIL" in output
    assert "NEXT STEP" not in output


def test_chat_list_marks_branch_only_columns_as_unavailable() -> None:
    """Repository-free chats render clear placeholders beside their session type."""

    output = render_text(
        "list",
        [
            {
                "name": "architecture-research",
                "type": "chat",
                "status": "stopped",
                "repo": None,
                "branch": None,
                "model": "provider/team/kimi-k3-max-preview",
                "last_used_at": "2026-08-11T17:57:51+00:00",
            },
            {
                "name": "fix-exporter-metrics",
                "type": "branch",
                "status": "running",
                "repo": "/work/example/exporter",
                "branch": "piw/fix-exporter-metrics",
                "model": "provider/team/kimi-k3-max-preview",
                "last_used_at": "2026-08-11T17:57:51+00:00",
            },
        ],
        terminal_width=160,
    )

    chat_row = next(line for line in output.splitlines() if "architecture-research" in line)
    assert chat_row.split()[:5] == ["architecture-research", "chat", "stopped", "-", "-"]


def test_chat_only_list_retains_branch_column_placeholders() -> None:
    """The stable list shape keeps branch-only columns visible for chat inventories."""

    output = render_text(
        "list",
        [
            {
                "name": "research",
                "type": "chat",
                "status": "running",
                "repo": None,
                "branch": None,
                "model": None,
                "last_used_at": None,
            }
        ],
        terminal_width=120,
    )

    assert "REPOSITORY" in output
    assert "BRANCH" in output
    chat_row = output.splitlines()[-1]
    assert chat_row.split() == ["research", "chat", "running", "-", "-"]


def test_nested_text_uses_readable_sections_and_lists() -> None:
    """Mapping output separates nested state instead of embedding JSON on one line."""

    output = render_text(
        "status",
        {
            "name": "example",
            "git": {"dirty": True, "safe_to_clean": False},
            "read_only_refs": ["/work/reference"],
        },
    )

    assert "name: example" in output
    assert "git:\n  dirty: yes" in output
    assert "safe to clean: no" in output
    assert "read only refs:\n  - /work/reference" in output


def test_narrow_tables_ellipsize_cells_without_breaking_alignment() -> None:
    """Long values remain one row when the terminal is narrow."""

    output = render_text(
        "doctor",
        [
            {
                "name": "a-very-long-check-name",
                "status": "pass",
                "message": "a detail that is intentionally much longer than the terminal",
            }
        ],
        terminal_width=48,
    )

    assert "…" in output
    assert len(output.splitlines()) == 3


def test_yaml_dump_is_safe_and_uses_literal_multiline_strings() -> None:
    """YAML remains round-trippable while keeping help text readable."""

    value = {"ok": False, "hint": "first line\nsecond line\n"}
    output = dump_yaml(value)

    assert "hint: |" in output
    assert yaml.safe_load(output) == value
