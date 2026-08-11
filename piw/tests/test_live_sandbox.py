"""Opt-in integration test against a real Docker Sandbox daemon."""

import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from piw.config import load_config
from piw.models import AppConfig, SandboxConfig
from piw.process import SubprocessRunner
from piw.service import PiwService
from piw.state import SecretStateStore, StateStore


@pytest.mark.live
def test_real_chat_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create, inspect, execute in, stop, and remove one real chat sandbox."""

    if os.environ.get("PIW_RUN_LIVE_TESTS") != "1":
        pytest.skip("set PIW_RUN_LIVE_TESTS=1 to run real Docker Sandbox tests")
    if shutil.which("sbx") is None:
        pytest.skip("sbx is not installed")

    def persistent_workspace(session_name: str) -> Path:
        """Keep the live chat workspace inside pytest's temporary directory."""

        return tmp_path / "workspaces" / session_name

    def isolated_cache_home() -> Path:
        """Keep template bootstrap files inside pytest's temporary directory."""

        return tmp_path / "cache"

    monkeypatch.setattr("piw.service._persistent_chat_workspace", persistent_workspace)
    monkeypatch.setattr("piw.service.cache_home", isolated_cache_home)
    name = f"live-chat-{uuid4().hex[:10]}"
    store = StateStore(tmp_path / "sessions")
    profile = os.environ.get("PIW_LIVE_PROFILE") or load_config().sandbox.profile
    config = AppConfig(sandbox=SandboxConfig(profile=profile))
    service = PiwService(
        config,
        SubprocessRunner(),
        store,
        SecretStateStore(tmp_path / "secrets.json"),
    )
    workspace: Path | None = None

    try:
        created = service.chat(
            name,
            service.effective_session_config(),
            temporary=False,
            batch=True,
            dry_run=False,
        )
        record = store.load(name)
        workspace = Path(record.workspace)

        assert created["action"] == "created"
        assert created["type"] == "chat"
        assert service.status(name)["status"] == "running"

        executed = service.execute(name, ("pwd",))
        assert executed["returncode"] == 0
        assert str(executed["stdout"]).strip() == record.workspace

        assert service.stop(name, dry_run=False)["action"] == "stopped"
        assert service.status(name)["status"] == "stopped"
    finally:
        if store.exists(name):
            service.clean(name, dry_run=False, force=True)

    assert not store.exists(name)
    assert workspace is not None
    assert not workspace.exists()
