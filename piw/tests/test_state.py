"""Session state persistence tests."""

import json
import os
from pathlib import Path

import pytest

from piw.errors import ExitCode, PiwError
from piw.models import SecretRecord, SessionKind, SessionRecord
from piw.state import SecretStateStore, StateStore


def record(name: str = "sample", *, kind: SessionKind = SessionKind.BRANCH) -> SessionRecord:
    """Create a complete current session record."""

    return SessionRecord(
        schema_version=2,
        name=name,
        kind=kind,
        sandbox=f"piw-{name}",
        workspace=f"/workspaces/{name}",
        branch=f"piw/{name}" if kind is SessionKind.BRANCH else None,
        base_commit="a" * 40 if kind is SessionKind.BRANCH else None,
        template="piw-pi-123:latest",
        model=None,
        thinking="high",
        read_only_refs=(),
        skill_paths=(),
        profile=None,
        created_at="2026-01-01T00:00:00+00:00",
        last_used_at="2026-01-01T00:00:00+00:00",
        session_started=False,
    )


def test_state_round_trip_and_permissions(tmp_path: Path) -> None:
    """Session records are atomically stored with user-only permissions."""

    store = StateStore(tmp_path / "tasks")
    expected = record()
    store.save(expected)
    assert store.load("sample") == expected
    if os.name != "nt":
        assert store.path_for("sample").stat().st_mode & 0o777 == 0o600


def test_state_list_is_sorted_and_delete_is_idempotent(tmp_path: Path) -> None:
    """Inventory order is stable and repeated deletion is safe."""

    store = StateStore(tmp_path)
    store.save(record("zeta"))
    store.save(record("alpha"))
    assert [item.name for item in store.list()] == ["alpha", "zeta"]
    store.delete("alpha")
    store.delete("alpha")
    assert [item.name for item in store.list()] == ["zeta"]


def test_missing_and_invalid_state_have_stable_errors(tmp_path: Path) -> None:
    """Missing and corrupt records are distinguishable."""

    store = StateStore(tmp_path)
    with pytest.raises(PiwError) as missing:
        store.load("absent")
    assert missing.value.code is ExitCode.SESSION

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


def test_legacy_task_state_loads_and_migrates_on_save(tmp_path: Path) -> None:
    """Schema-v1 branch tasks remain usable and move to current session storage on write."""

    current = tmp_path / "sessions"
    legacy = tmp_path / "tasks"
    legacy.mkdir()
    legacy_path = legacy / "old-branch.json"
    legacy_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task": "old-branch",
                "sandbox": "piw-old-branch",
                "repo": "/repo",
                "branch": "piw/old-branch",
                "base_commit": "a" * 40,
                "template": "piw-pi-123:latest",
                "model": None,
                "thinking": "high",
                "read_only_refs": [],
                "skill_paths": [],
                "profile": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_used_at": "2026-01-01T00:00:00+00:00",
                "session_started": False,
            }
        )
    )
    store = StateStore(current, legacy)

    migrated = store.load("old-branch")
    assert migrated.kind is SessionKind.BRANCH
    assert migrated.workspace == "/repo"
    assert migrated.schema_version == 2
    assert not store.path_for("old-branch").exists()

    store.save(migrated)
    assert store.path_for("old-branch").is_file()
    assert not legacy_path.exists()


def test_chat_state_rejects_git_fields(tmp_path: Path) -> None:
    """A corrupt chat record cannot silently acquire branch-only state."""

    store = StateStore(tmp_path)
    value = record("chat", kind=SessionKind.CHAT).to_json_object()
    value["branch"] = "piw/not-a-chat"
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "chat.json").write_text(json.dumps(value))

    with pytest.raises(PiwError) as captured:
        store.load("chat")
    assert captured.value.detail.kind == "invalid_session_state"


def test_state_write_failure_has_stable_error(tmp_path: Path) -> None:
    """Filesystem failures do not escape as raw exceptions."""

    root = tmp_path / "not-a-directory"
    root.write_text("occupied")
    with pytest.raises(PiwError) as captured:
        StateStore(root).save(record())
    assert captured.value.detail.kind == "session_state_write_failed"


def test_state_delete_failure_has_stable_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State deletion reports a typed error and retains the retryable record."""

    store = StateStore(tmp_path)
    store.save(record())
    state_path = store.path_for("sample")
    original_unlink = Path.unlink

    def fail_current_state(path: Path, *, missing_ok: bool = False) -> None:
        """Reject deletion only for the state file under test."""

        if path == state_path:
            raise PermissionError("permission denied")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_current_state)

    with pytest.raises(PiwError) as captured:
        store.delete("sample")

    assert captured.value.detail.kind == "session_state_delete_failed"
    assert state_path.is_file()


def secret_record() -> SecretRecord:
    """Create redacted secret synchronization metadata."""

    return SecretRecord(
        schema_version=1,
        source_env="HOST_TOKEN",
        sandbox_env="EXAMPLE_API_KEY",
        hosts=("api.example.test",),
        placeholder_template="sk-{rand}",
        placeholder="sk-placeholder",
        fingerprint="f" * 64,
        synced_at="2026-01-01T00:00:00+00:00",
    )


def test_secret_state_round_trip_is_redacted_and_private(tmp_path: Path) -> None:
    """Secret sync state contains only fingerprints and placeholders."""

    path = tmp_path / "secrets.json"
    store = SecretStateStore(path)
    store.save((secret_record(),))
    assert store.load() == (secret_record(),)
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    assert "high-entropy-value" not in path.read_text()


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        '{"schema_version": 9, "records": []}',
        '{"schema_version": 1}',
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        **secret_record().to_json_object(),
                        "placeholder": "",
                    }
                ],
            }
        ),
    ],
)
def test_invalid_secret_state_has_stable_error(payload: str, tmp_path: Path) -> None:
    """Malformed redacted state is never silently trusted."""

    path = tmp_path / "secrets.json"
    path.write_text(payload)
    with pytest.raises(PiwError) as captured:
        SecretStateStore(path).load()
    assert captured.value.detail.kind == "invalid_secret_state"
