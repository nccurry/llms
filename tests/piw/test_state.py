"""Task state persistence tests."""

import json
from pathlib import Path

import pytest

from piw.errors import ExitCode, PiwError
from piw.models import TaskRecord
from piw.state import StateStore


def record(task: str = "sample") -> TaskRecord:
    """Create a complete test task record."""

    return TaskRecord(
        schema_version=1,
        task=task,
        sandbox=f"piw-{task}",
        repo="/repo",
        branch=f"piw/{task}",
        base_commit="a" * 40,
        template="piw-pi-123:latest",
        model=None,
        thinking="high",
        mcp_servers=(),
        read_only_refs=(),
        skill_paths=(),
        profile=None,
        created_at="2026-01-01T00:00:00+00:00",
        last_used_at="2026-01-01T00:00:00+00:00",
        session_started=False,
    )


def test_state_round_trip_and_permissions(tmp_path: Path) -> None:
    """Task records are atomically stored with user-only permissions."""

    store = StateStore(tmp_path / "tasks")
    expected = record()
    store.save(expected)
    assert store.load("sample") == expected
    assert store.path_for("sample").stat().st_mode & 0o777 == 0o600


def test_state_list_is_sorted_and_delete_is_idempotent(tmp_path: Path) -> None:
    """Inventory order is stable and repeated deletion is safe."""

    store = StateStore(tmp_path)
    store.save(record("zeta"))
    store.save(record("alpha"))
    assert [item.task for item in store.list()] == ["alpha", "zeta"]
    store.delete("alpha")
    store.delete("alpha")
    assert [item.task for item in store.list()] == ["zeta"]


def test_missing_and_invalid_state_have_stable_errors(tmp_path: Path) -> None:
    """Missing and corrupt records are distinguishable."""

    store = StateStore(tmp_path)
    with pytest.raises(PiwError) as missing:
        store.load("absent")
    assert missing.value.code is ExitCode.TASK

    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "broken.json").write_text(json.dumps({"schema_version": "wrong"}))
    with pytest.raises(PiwError) as broken:
        store.load("broken")
    assert broken.value.code is ExitCode.STATE

    invalid_thinking = record("invalid-thinking").to_json_object()
    invalid_thinking["thinking"] = "unbounded"
    (tmp_path / "invalid-thinking.json").write_text(json.dumps(invalid_thinking))
    with pytest.raises(PiwError) as unsupported:
        store.load("invalid-thinking")
    assert unsupported.value.code is ExitCode.STATE


def test_state_write_failure_has_stable_error(tmp_path: Path) -> None:
    """Filesystem failures do not escape as raw exceptions."""

    root = tmp_path / "not-a-directory"
    root.write_text("occupied")
    with pytest.raises(PiwError) as captured:
        StateStore(root).save(record())
    assert captured.value.detail.kind == "task_state_write_failed"
