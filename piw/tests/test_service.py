"""Session and template orchestration tests."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from piw.errors import ExitCode, PiwError
from piw.models import (
    AppConfig,
    BranchMode,
    EffectiveBranchConfig,
    HostChangesPolicy,
    PiConfig,
    SandboxConfig,
    SandboxPhase,
    SandboxSecretConfig,
    SessionKind,
    ThinkingLevel,
)
from piw.sandbox import desired_template, sandbox_guest_path
from piw.service import PiwService, branch_sandbox_name, normalize_session_name
from piw.state import SecretStateStore, StateStore
from tests.fakes import ScenarioRunner


def make_service(
    tmp_path: Path,
    *,
    sandbox_config: SandboxConfig | None = None,
    pi_config: PiConfig | None = None,
) -> tuple[PiwService, ScenarioRunner, Path]:
    """Create a service backed by a deterministic runner."""

    repo = tmp_path / "repo"
    repo.mkdir()
    runner = ScenarioRunner(repo)
    config = AppConfig(
        sandbox=sandbox_config or SandboxConfig(),
        pi=pi_config or PiConfig(),
    )
    runner.templates.add(desired_template(config))
    service = PiwService(
        config,
        runner,
        StateStore(tmp_path / "state"),
        SecretStateStore(tmp_path / "secrets.json"),
    )
    return service, runner, repo


def effective(
    service: PiwService,
    repo: Path,
    name: str = "Feature Work",
) -> EffectiveBranchConfig:
    """Resolve a default test branch configuration."""

    return service.effective_branch_config(
        session_config=service.effective_session_config(),
        repo_candidate=repo,
        name=name,
    )


@pytest.mark.parametrize(
    ("label", "expected"),
    [("Fix Exporter Metrics", "fix-exporter-metrics"), ("  A/B  ", "a-b")],
)
def test_session_names_are_stable(label: str, expected: str, tmp_path: Path) -> None:
    """Session labels become readable identifiers and collision-safe sandbox names."""

    assert normalize_session_name(label) == expected
    assert branch_sandbox_name(label, tmp_path).startswith("piw-")


def test_empty_session_name_is_rejected() -> None:
    """A persistent session must have a usable identifier."""

    with pytest.raises(PiwError) as captured:
        normalize_session_name("!!!")
    assert captured.value.code is ExitCode.USAGE


def test_effective_config_merges_repeatable_overrides(tmp_path: Path) -> None:
    """CLI additions extend rather than erase user defaults."""

    refs = tmp_path / "refs"
    skills = tmp_path / "skills"
    extra = tmp_path / "extra"
    for path in (refs, skills, extra):
        path.mkdir()
    service, _runner, _repo = make_service(
        tmp_path,
        sandbox_config=SandboxConfig(read_only_refs=(refs,)),
        pi_config=PiConfig(skill_paths=(skills,), extensions=("base",)),
    )
    resolved = service.effective_session_config(
        refs=(extra,),
        skills=(extra,),
        extensions=("extra",),
        model="provider/model",
        thinking=ThinkingLevel.XHIGH,
    )
    assert resolved.read_only_refs == (refs, extra)
    assert resolved.skill_paths == (skills, extra)
    assert resolved.extensions == ("base", "extra")
    assert resolved.thinking is ThinkingLevel.XHIGH


def test_effective_config_rejects_invalid_git_branch(tmp_path: Path) -> None:
    """Branch names fail before template or sandbox work begins."""

    service, _, repo = make_service(tmp_path)
    with pytest.raises(PiwError) as captured:
        service.effective_branch_config(
            session_config=service.effective_session_config(),
            repo_candidate=repo,
            name="test",
            branch="bad..branch",
        )
    assert captured.value.detail.kind == "invalid_branch"


def test_branch_dry_run_is_read_only(tmp_path: Path) -> None:
    """Dry-run resolves names and templates without creating state."""

    service, runner, repo = make_service(tmp_path)
    data = service.create_branch(
        name="Feature Work",
        branch_config=effective(service, repo),
        batch=True,
        dry_run=True,
    )
    assert data["action"] == "create"
    assert data["name"] == "feature-work"
    assert data["type"] == "branch"
    assert data["mode"] == "new"
    assert data["source_ref"] is None
    assert not runner.sandboxes
    assert not service.store.exists("feature-work")


def test_existing_branch_mode_rejects_new_branch_options(tmp_path: Path) -> None:
    """Adoption cannot silently reinterpret new-branch base or naming options."""

    service, _, repo = make_service(tmp_path)
    with pytest.raises(PiwError) as captured:
        service.effective_branch_config(
            session_config=service.effective_session_config(),
            repo_candidate=repo,
            name="adopt",
            existing="feature/existing",
            base_ref="main",
        )
    assert captured.value.detail.kind == "invalid_existing_branch_options"


def test_existing_local_branch_is_recreated_with_its_upstream(tmp_path: Path) -> None:
    """A local branch starts at its exact commit and retains tracking configuration."""

    service, runner, repo = make_service(tmp_path)
    commit = "c" * 40
    runner.local_branches["feature/existing"] = commit
    runner.remote_branches["origin/feature/existing"] = commit
    runner.branch_upstreams["feature/existing"] = "origin/feature/existing"
    branch_config = service.effective_branch_config(
        session_config=service.effective_session_config(),
        repo_candidate=repo,
        name="adopt-local",
        existing="feature/existing",
    )

    assert branch_config.mode is BranchMode.EXISTING
    assert branch_config.branch == "feature/existing"
    assert branch_config.base_ref == "refs/heads/feature/existing"
    result = service.create_branch(
        name="adopt-local",
        branch_config=branch_config,
        batch=True,
        dry_run=False,
    )

    assert result["mode"] == "existing"
    assert result["source_ref"] == "feature/existing"
    assert result["base_commit"] == commit
    assert result["upstream"] == "origin/feature/existing"
    switch = next(call for call in runner.calls if "--force-create" in call)
    assert switch[-3:] == ("--force-create", "feature/existing", commit)
    copied = next(call for call in runner.calls if call[-5:-3] == ("git", "fetch"))
    assert copied[-5:] == (
        "git",
        "fetch",
        "--no-tags",
        "origin",
        "+refs/remotes/origin/feature/existing:refs/remotes/origin/feature/existing",
    )
    assert runner.sandbox_upstreams == {"feature/existing": "origin/feature/existing"}
    record = service.store.load("adopt-local")
    assert record.branch == "feature/existing"
    assert record.base_commit == commit


def test_existing_remote_branch_infers_local_name(tmp_path: Path) -> None:
    """An explicit remote-tracking ref becomes a same-named local tracking branch."""

    service, runner, repo = make_service(tmp_path)
    runner.remote_branches["origin/feature/review"] = "d" * 40
    resolved = service.effective_branch_config(
        session_config=service.effective_session_config(),
        repo_candidate=repo,
        name="review",
        existing="origin/feature/review",
    )

    assert resolved.mode is BranchMode.EXISTING
    assert resolved.branch == "feature/review"
    assert resolved.base_ref == "refs/remotes/origin/feature/review"
    assert resolved.upstream == "origin/feature/review"


def test_existing_branch_upstream_failure_rolls_back(tmp_path: Path) -> None:
    """A tracking failure cannot leave a partial sandbox or session record."""

    service, runner, repo = make_service(tmp_path)
    runner.local_branches["feature/existing"] = "c" * 40
    runner.remote_branches["origin/feature/existing"] = "c" * 40
    runner.branch_upstreams["feature/existing"] = "origin/feature/existing"
    runner.upstream_config_error = True
    branch_config = service.effective_branch_config(
        session_config=service.effective_session_config(),
        repo_candidate=repo,
        name="bad-upstream",
        existing="feature/existing",
    )

    with pytest.raises(PiwError) as captured:
        service.create_branch(
            name="bad-upstream",
            branch_config=branch_config,
            batch=True,
            dry_run=False,
        )

    assert captured.value.detail.kind == "upstream_config_failed"
    assert not runner.sandboxes
    assert not service.store.exists("bad-upstream")


def test_existing_branch_upstream_copy_failure_rolls_back(tmp_path: Path) -> None:
    """A missing sandbox tracking ref cannot leave a partial branch session."""

    service, runner, repo = make_service(tmp_path)
    runner.remote_branches["origin/feature/review"] = "d" * 40
    runner.upstream_copy_error = True
    branch_config = service.effective_branch_config(
        session_config=service.effective_session_config(),
        repo_candidate=repo,
        name="bad-copy",
        existing="origin/feature/review",
    )

    with pytest.raises(PiwError) as captured:
        service.create_branch(
            name="bad-copy",
            branch_config=branch_config,
            batch=True,
            dry_run=False,
        )

    assert captured.value.detail.kind == "upstream_copy_failed"
    assert not runner.sandboxes
    assert not service.store.exists("bad-copy")


def test_persistent_chat_requires_a_name(tmp_path: Path) -> None:
    """Unnamed chats must opt into temporary cleanup explicitly."""

    service, _, _ = make_service(tmp_path)
    with pytest.raises(PiwError) as captured:
        service.chat(
            None,
            service.effective_session_config(),
            temporary=False,
            batch=False,
            dry_run=True,
        )
    assert captured.value.detail.kind == "missing_session_name"


def test_persistent_chat_dry_run_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Named chat preview describes durable state without allocating it."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    service, runner, _ = make_service(tmp_path)
    result = service.chat(
        "Research Notes",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=True,
    )

    assert result["action"] == "create"
    assert result["name"] == "research-notes"
    assert result["type"] == "chat"
    assert result["temporary"] is False
    assert result["batch"] is True
    assert not runner.sandboxes
    assert not Path(str(result["workspace"])).exists()
    assert not service.store.exists("research-notes")
    assert not any(call[0] == "git" for call in runner.calls)


def test_persistent_chat_supports_complete_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Named chats retain their workspace and work with every lifecycle operation."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"example": {"models": []}}}))
    service, runner, _ = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    runner.executables.remove("git")

    result = service.chat(
        "Research Notes",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=False,
    )

    assert result["action"] == "created"
    record = service.store.load("research-notes")
    assert record.kind is SessionKind.CHAT
    assert record.branch is None
    assert record.base_commit is None
    assert record.sandbox in runner.sandboxes
    assert Path(record.workspace).is_dir()
    assert Path(record.workspace).parent == tmp_path / "xdg-state" / "piw" / "chats"
    assert service.list_sessions()[0]["type"] == "chat"
    create = next(call for call in runner.calls if call[:2] == ("sbx", "create"))
    assert "--clone" not in create
    assert "models.json" in runner.seeded_files

    assert service.execute("research-notes", ("printf", "ok"))["returncode"] == 0
    service.shell("research-notes")
    assert service.stop("research-notes", dry_run=False)["action"] == "stopped"
    service.attach("research-notes", timeout_seconds=30)
    assert service.store.load("research-notes").session_started is True
    status = service.status("research-notes")
    assert status["git"] is None
    assert status["git_inspection_deferred"] is False
    assert service.clean("research-notes", dry_run=True, force=False)["safety"] is None

    assert service.clean("research-notes", dry_run=False, force=False)["action"] == "removed"
    assert not runner.sandboxes
    assert not Path(record.workspace).exists()
    assert not service.store.exists("research-notes")


def test_persistent_chat_pi_failure_retains_resumable_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed attached Pi process does not destroy a persistent chat."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    service, runner, _ = make_service(tmp_path)
    runner.pi_exit_code = 1

    with pytest.raises(PiwError) as captured:
        service.chat(
            "keep-me",
            service.effective_session_config(),
            temporary=False,
            batch=False,
            dry_run=False,
        )

    assert captured.value.detail.kind == "pi_failed"
    record = service.store.load("keep-me")
    assert record.session_started is True
    assert record.sandbox in runner.sandboxes
    assert Path(record.workspace).is_dir()


def test_persistent_chat_rejects_an_existing_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistent names remain unique across branch and chat session types."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    service, _, _ = make_service(tmp_path)
    service.chat(
        "research",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=False,
    )

    with pytest.raises(PiwError) as captured:
        service.chat(
            "research",
            service.effective_session_config(),
            temporary=False,
            batch=True,
            dry_run=True,
        )

    assert captured.value.detail.kind == "session_exists"


def test_named_temporary_chat_can_reuse_a_persistent_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disposable sandbox does not conflict with a saved chat of the same name."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    service, runner, _ = make_service(tmp_path)
    service.chat(
        "research",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=False,
    )

    result = service.chat(
        "research",
        service.effective_session_config(),
        temporary=True,
        batch=False,
        dry_run=False,
    )

    assert result["temporary"] is True
    assert service.store.exists("research")
    assert len(runner.sandboxes) == 1


def test_clean_removes_a_chat_after_its_sandbox_was_lost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale chats remain cleanable because they have no Git recovery remote."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    service, runner, _ = make_service(tmp_path)
    service.chat(
        "stale-chat",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=False,
    )
    record = service.store.load("stale-chat")
    runner.sandboxes.clear()

    result = service.clean("stale-chat", dry_run=False, force=False)

    assert result["previous_status"] == "missing"
    assert not Path(record.workspace).exists()
    assert not service.store.exists("stale-chat")


def test_chat_cleanup_failure_retains_retryable_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A workspace deletion failure leaves state that a later cleanup can retry."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    service, runner, _ = make_service(tmp_path)
    service.chat(
        "retry-cleanup",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=False,
    )
    record = service.store.load("retry-cleanup")

    def fail_workspace_delete(_path: str | Path) -> None:
        """Simulate an operating-system refusal to delete the workspace."""

        raise PermissionError("permission denied")

    with monkeypatch.context() as cleanup_patch:
        cleanup_patch.setattr(
            "piw.service.shutil.rmtree",
            fail_workspace_delete,
        )
        with pytest.raises(PiwError) as captured:
            service.clean("retry-cleanup", dry_run=False, force=False)

    assert captured.value.detail.kind == "workspace_cleanup_failed"
    assert record.sandbox not in runner.sandboxes
    assert Path(record.workspace).is_dir()
    assert service.store.exists("retry-cleanup")

    assert service.clean("retry-cleanup", dry_run=False, force=False)["action"] == "removed"
    assert not Path(record.workspace).exists()
    assert not service.store.exists("retry-cleanup")


def test_clean_refuses_an_unmanaged_chat_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrupt state cannot make chat cleanup delete an arbitrary directory."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    service, runner, _ = make_service(tmp_path)
    service.chat(
        "guarded-chat",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=False,
    )
    record = service.store.load("guarded-chat")
    outside = tmp_path / "outside"
    outside.mkdir()
    service.store.save(replace(record, workspace=str(outside)))

    with pytest.raises(PiwError) as captured:
        service.clean("guarded-chat", dry_run=False, force=False)

    assert captured.value.detail.kind == "invalid_session_state"
    assert outside.is_dir()
    assert record.sandbox in runner.sandboxes


def test_temporary_chat_attaches_then_removes_everything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A temporary chat accepts no name and leaves no persistent resources."""

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    service, runner, _ = make_service(tmp_path)
    runner.executables.remove("git")

    result = service.chat(
        None,
        service.effective_session_config(),
        temporary=True,
        batch=False,
        dry_run=False,
    )

    assert result["action"] == "completed"
    assert result["temporary"] is True
    assert result["removed"] is True
    assert not runner.sandboxes
    assert not Path(str(result["workspace"])).exists()
    assert service.store.list() == ()


def test_temporary_chat_configuration_failure_still_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuration failures cannot strand a disposable chat sandbox."""

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"broken": {"models": []}}}))
    service, runner, _ = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    runner.pi_config_error = "errors loading models.json"

    with pytest.raises(PiwError):
        service.chat(
            None,
            service.effective_session_config(),
            temporary=True,
            batch=False,
            dry_run=False,
        )

    assert not runner.sandboxes
    assert not any((tmp_path / "cache" / "piw" / "chats").glob("*"))


def test_temporary_chat_pi_failure_still_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed interactive Pi process cannot strand its chat sandbox."""

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    service, runner, _ = make_service(tmp_path)
    runner.pi_exit_code = 1

    with pytest.raises(PiwError) as captured:
        service.chat(
            "throwaway",
            service.effective_session_config(),
            temporary=True,
            batch=False,
            dry_run=False,
        )

    assert captured.value.detail.kind == "pi_failed"
    assert not runner.sandboxes
    assert not any((tmp_path / "cache" / "piw" / "chats").glob("*"))


def test_temporary_chat_rejects_batch_mode(tmp_path: Path) -> None:
    """Batch creation cannot produce an unreachable temporary sandbox."""

    service, _, _ = make_service(tmp_path)
    with pytest.raises(PiwError) as captured:
        service.chat(
            None,
            service.effective_session_config(),
            temporary=True,
            batch=True,
            dry_run=True,
        )
    assert captured.value.detail.kind == "invalid_usage"


def secret_config(*, required: bool = True) -> SandboxConfig:
    """Return one generic host-to-sandbox secret declaration."""

    return SandboxConfig(
        secrets=(
            SandboxSecretConfig(
                source_env="HOST_TOKEN",
                sandbox_env="EXAMPLE_API_KEY",
                hosts=("api.example.test",),
                placeholder="sk-{rand}",
                required=required,
            ),
        )
    )


def test_secret_sync_create_idempotence_rotation_and_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronization creates once, rotates in place, and repairs external drift."""

    service, runner, _ = make_service(tmp_path, sandbox_config=secret_config())
    monkeypatch.setenv("HOST_TOKEN", "first-high-entropy-value")
    status = service.secret_status()[0]
    assert status["status"] == "pending"
    assert status["action"] == "create"

    preview = service.sync_secrets(dry_run=True, force=False)[0]
    assert preview["action"] == "would_create"
    assert not runner.custom_secrets
    created = service.sync_secrets(dry_run=False, force=False)[0]
    placeholder = str(created["placeholder"])
    assert created["action"] == "created"
    assert placeholder.startswith("sk-")
    assert runner.secret_inputs == ["first-high-entropy-value"]
    assert "first-high-entropy-value" not in service.secret_store.path.read_text()

    unchanged = service.sync_secrets(dry_run=False, force=False)[0]
    assert unchanged["action"] == "unchanged"
    assert len(runner.secret_inputs) == 1

    monkeypatch.setenv("HOST_TOKEN", "rotated-high-entropy-value")
    updated = service.sync_secrets(dry_run=False, force=False)[0]
    assert updated["action"] == "updated"
    assert updated["placeholder"] == placeholder
    assert "rotated-high-entropy-value" not in service.secret_store.path.read_text()

    runner.custom_secrets.clear()
    assert service.secret_status()[0]["action"] == "restore"
    restored = service.sync_secrets(dry_run=False, force=False)[0]
    assert restored["action"] == "restored"
    assert restored["placeholder"] == placeholder

    monkeypatch.delenv("HOST_TOKEN")
    assert service.secret_status()[0]["status"] == "synced"
    with pytest.raises(PiwError) as forced:
        service.sync_secrets(dry_run=False, force=True)
    assert forced.value.detail.kind == "missing_secret_source"


def test_secret_sync_fails_closed_before_partial_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing required source blocks the complete synchronization batch."""

    config = SandboxConfig(
        secrets=(
            SandboxSecretConfig(
                source_env="AVAILABLE_TOKEN",
                sandbox_env="AVAILABLE_API_KEY",
                hosts=("available.example.test",),
            ),
            SandboxSecretConfig(
                source_env="MISSING_TOKEN",
                sandbox_env="MISSING_API_KEY",
                hosts=("missing.example.test",),
            ),
        )
    )
    service, runner, _ = make_service(tmp_path, sandbox_config=config)
    monkeypatch.setenv("AVAILABLE_TOKEN", "available-value")
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    with pytest.raises(PiwError) as captured:
        service.sync_secrets(dry_run=False, force=False)
    assert captured.value.detail.kind == "missing_secret_source"
    assert not runner.custom_secrets


def test_failed_secret_write_does_not_create_redacted_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Piw records a fingerprint only after Docker accepts the corresponding value."""

    service, runner, _ = make_service(tmp_path, sandbox_config=secret_config())
    monkeypatch.setenv("HOST_TOKEN", "write-failure-value")
    runner.secret_error = True
    with pytest.raises(PiwError) as captured:
        service.sync_secrets(dry_run=False, force=False)
    assert captured.value.detail.kind == "secret_sync_failed"
    assert not service.secret_store.path.exists()
    assert not runner.custom_secrets


def test_optional_missing_secret_is_reported_without_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional providers remain inactive until their source variable appears."""

    service, _, _ = make_service(tmp_path, sandbox_config=secret_config(required=False))
    monkeypatch.delenv("HOST_TOKEN", raising=False)
    result = service.sync_secrets(dry_run=False, force=False)[0]
    assert result["action"] == "skip"
    assert result["status"] == "optional_unavailable"


def test_branch_synchronizes_declared_secrets_automatically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normal branch command makes provider credentials available before creation."""

    service, runner, repo = make_service(tmp_path, sandbox_config=secret_config())
    monkeypatch.setenv("HOST_TOKEN", "automatic-value")
    result = service.create_branch(
        name="automatic-secret",
        branch_config=effective(service, repo, "automatic-secret"),
        batch=True,
        dry_run=False,
    )
    secrets = result["secrets"]
    assert isinstance(secrets, list)
    assert secrets[0]["action"] == "created"
    assert "EXAMPLE_API_KEY" in runner.custom_secrets

    placeholder = runner.custom_secrets["EXAMPLE_API_KEY"][0]
    monkeypatch.setenv("HOST_TOKEN", "rotated-on-attach")
    attached = service.attach("automatic-secret")
    attached_secrets = attached["secrets"]
    assert isinstance(attached_secrets, list)
    assert attached_secrets[0]["action"] == "updated"
    assert runner.custom_secrets["EXAMPLE_API_KEY"][0] == placeholder


def test_doctor_reports_required_secret_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor distinguishes an absent required source from a synchronized mapping."""

    service, _, _ = make_service(tmp_path, sandbox_config=secret_config())
    monkeypatch.delenv("HOST_TOKEN", raising=False)
    missing = next(
        check
        for check in service.doctor(live=False, timeout_seconds=30)
        if check.name == "secret:EXAMPLE_API_KEY"
    )
    assert missing.status == "fail"
    monkeypatch.setenv("HOST_TOKEN", "doctor-value")
    service.sync_secrets(dry_run=False, force=False)
    synced = next(
        check
        for check in service.doctor(live=False, timeout_seconds=30)
        if check.name == "secret:EXAMPLE_API_KEY"
    )
    assert synced.status == "pass"


def test_branch_batch_seeds_state_and_list(tmp_path: Path) -> None:
    """A successful batch command creates the branch, metadata, and session record."""

    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"example": {"models": []}}}))
    service, runner, repo = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    data = service.create_branch(
        name="Feature Work",
        branch_config=effective(service, repo),
        batch=True,
        dry_run=False,
    )
    assert data["action"] == "created"
    record = service.store.load("feature-work")
    assert record.branch == "piw/feature-work"
    assert record.sandbox in runner.sandboxes
    switch = next(call for call in runner.calls if call[-5:-3] == ("git", "switch"))
    assert "--create" in switch
    assert "--force-create" not in switch
    assert "models.json" in runner.seeded_files
    assert service.list_sessions()[0]["status"] == SandboxPhase.RUNNING


def test_branch_rejects_dirty_host(tmp_path: Path) -> None:
    """Non-reproducible host state fails before sandbox creation."""

    service, runner, repo = make_service(tmp_path)
    runner.host_clean = False
    with pytest.raises(PiwError) as dirty:
        service.create_branch(
            name="dirty", branch_config=effective(service, repo, "dirty"), batch=True, dry_run=False
        )
    assert dirty.value.code is ExitCode.UNSAFE
    assert dirty.value.detail.kind == "dirty_host_repository"
    assert "--ignore-host-changes" in (dirty.value.detail.hint or "")
    assert "--carry-host-changes" in (dirty.value.detail.hint or "")


def test_branch_can_ignore_or_carry_dirty_host_changes(tmp_path: Path) -> None:
    """Explicit policies either omit changes or apply them to only the private clone."""

    ignored_root = tmp_path / "ignored"
    ignored_root.mkdir()
    ignored_service, ignored_runner, ignored_repo = make_service(ignored_root)
    ignored_runner.host_clean = False
    ignored = ignored_service.create_branch(
        name="ignored",
        branch_config=effective(ignored_service, ignored_repo, "ignored"),
        batch=True,
        dry_run=False,
        host_changes=HostChangesPolicy.IGNORE,
    )
    assert ignored["host_changes"] == {
        "policy": "ignore",
        "dirty": True,
        "paths": ["host-change.txt"],
        "included_paths": [],
        "action": "ignore",
    }
    assert not ignored_runner.applied_host_patches

    carried_root = tmp_path / "carried"
    carried_root.mkdir()
    carried_service, carried_runner, carried_repo = make_service(carried_root)
    carried_runner.host_clean = False
    carried_runner.host_patch_paths = ("host-change.txt",)
    carried_runner.host_patch = "diff --git a/host-change.txt b/host-change.txt\n"
    carried = carried_service.create_branch(
        name="carried",
        branch_config=effective(carried_service, carried_repo, "carried"),
        batch=True,
        dry_run=False,
        host_changes=HostChangesPolicy.CARRY,
    )
    carried_changes = carried["host_changes"]
    assert isinstance(carried_changes, dict)
    assert carried_changes["policy"] == "carry"
    assert carried_changes["included_paths"] == ["host-change.txt"]
    assert carried_runner.applied_host_patches == [carried_runner.host_patch]


def test_branch_carry_dry_run_reports_paths_without_creating_sandbox(tmp_path: Path) -> None:
    """Carry previews expose the policy and files while remaining read-only."""

    service, runner, repo = make_service(tmp_path)
    runner.host_clean = False
    runner.host_patch_paths = ("host-change.txt",)
    runner.host_patch = "diff --git a/host-change.txt b/host-change.txt\n"
    preview = service.create_branch(
        name="preview",
        branch_config=effective(service, repo, "preview"),
        batch=True,
        dry_run=True,
        host_changes=HostChangesPolicy.CARRY,
    )
    changes = preview["host_changes"]
    assert isinstance(changes, dict)
    assert changes == {
        "policy": "carry",
        "dirty": True,
        "paths": ["host-change.txt"],
        "included_paths": ["host-change.txt"],
        "action": "carry",
    }
    assert not runner.sandboxes
    assert not runner.applied_host_patches


@pytest.mark.parametrize("policy", list(HostChangesPolicy))
def test_branch_rejects_unresolved_host_conflicts(
    tmp_path: Path,
    policy: HostChangesPolicy,
) -> None:
    """No host-change policy can silently discard unresolved merge state."""

    service, runner, repo = make_service(tmp_path)
    runner.host_conflicts = ("conflicted.txt",)
    with pytest.raises(PiwError) as captured:
        service.create_branch(
            name="conflicted",
            branch_config=effective(service, repo, "conflicted"),
            batch=True,
            dry_run=True,
            host_changes=policy,
        )
    assert captured.value.detail.kind == "unresolved_host_conflicts"


def test_branch_rolls_back_when_carried_changes_do_not_apply(tmp_path: Path) -> None:
    """A base mismatch cannot leave a partial sandbox or saved session behind."""

    service, runner, repo = make_service(tmp_path)
    runner.host_clean = False
    runner.host_patch_paths = ("host-change.txt",)
    runner.host_patch = "diff --git a/host-change.txt b/host-change.txt\n"
    runner.host_patch_apply_error = True
    with pytest.raises(PiwError) as captured:
        service.create_branch(
            name="bad-patch",
            branch_config=effective(service, repo, "bad-patch"),
            batch=True,
            dry_run=False,
            host_changes=HostChangesPolicy.CARRY,
        )
    assert captured.value.detail.kind == "host_changes_apply_failed"
    assert not runner.sandboxes
    assert not service.store.exists("bad-patch")


def test_status_exec_stop_attach_and_clean(tmp_path: Path) -> None:
    """A branch session survives stop/attach and is removed only after Git safety checks."""

    service, runner, repo = make_service(tmp_path)
    service.create_branch(
        name="lifecycle",
        branch_config=effective(service, repo, "lifecycle"),
        batch=True,
        dry_run=False,
    )
    assert service.status("lifecycle")["git"] is not None
    executed = service.execute("lifecycle", ("printf", "ok"))
    assert executed["returncode"] == 0
    assert service.stop("lifecycle", dry_run=False)["action"] == "stopped"
    stopped_status = service.status("lifecycle")
    assert stopped_status["git_inspection_deferred"] is True
    assert service.clean("lifecycle", dry_run=True, force=False)["safety"] is None
    first = service.attach("lifecycle", timeout_seconds=30)
    assert service.store.load("lifecycle").session_started is True
    second = service.attach("lifecycle", timeout_seconds=30)
    pi_calls = [call for call in runner.calls if "pi" in call]
    assert first["conversation_mode"] == "new"
    assert first["conversation_name"] == "lifecycle"
    assert second["conversation_mode"] == "continue"
    assert "--continue" not in pi_calls[-2]
    assert "--continue" in pi_calls[-1]
    cleaned = service.clean("lifecycle", dry_run=False, force=False)
    assert cleaned["action"] == "removed"
    assert not runner.sandboxes
    assert not service.store.exists("lifecycle")


def test_attach_starts_named_conversation_with_runtime_overrides(tmp_path: Path) -> None:
    """A new conversation can use another model without changing stored defaults."""

    service, runner, repo = make_service(tmp_path)
    service.create_branch(
        name="source",
        branch_config=effective(service, repo, "source"),
        batch=True,
        dry_run=False,
    )

    attached = service.attach(
        "source",
        new="reviewer",
        model="anthropic/reviewer",
        thinking=ThinkingLevel.XHIGH,
        prompt="Review the current changes.",
    )

    pi_call = next(call for call in reversed(runner.calls) if "pi" in call)
    assert attached["conversation_mode"] == "new"
    assert attached["conversation_name"] == "reviewer"
    assert attached["model"] == "anthropic/reviewer"
    assert attached["thinking"] == "xhigh"
    assert "--continue" not in pi_call
    assert "--resume" not in pi_call
    pi_index = pi_call.index("pi")
    assert pi_call[pi_index:] == (
        "pi",
        "--name",
        "reviewer",
        "--model",
        "anthropic/reviewer",
        "--thinking",
        "xhigh",
        "Review the current changes.",
    )


def test_attach_selects_a_chat_conversation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Conversation selection uses the same command for repository-free chats."""

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    service, runner, _ = make_service(tmp_path)
    service.chat(
        "research",
        service.effective_session_config(),
        temporary=False,
        batch=True,
        dry_run=False,
    )

    attached = service.attach("research", select=True)
    pi_call = next(call for call in reversed(runner.calls) if "pi" in call)
    assert attached["type"] == "chat"
    assert attached["conversation_mode"] == "select"
    assert "--resume" in pi_call
    assert "--continue" not in pi_call


@pytest.mark.parametrize(
    ("new", "select", "kind"),
    [
        ("", False, "missing_conversation_name"),
        ("reviewer", True, "invalid_usage"),
    ],
)
def test_attach_rejects_invalid_conversation_modes(
    tmp_path: Path,
    new: str,
    select: bool,
    kind: str,
) -> None:
    """Direct service callers receive the same fail-closed validation as the CLI."""

    service, _, repo = make_service(tmp_path)
    service.create_branch(
        name="source",
        branch_config=effective(service, repo, "source"),
        batch=True,
        dry_run=False,
    )

    with pytest.raises(PiwError) as captured:
        service.attach("source", new=new, select=select)
    assert captured.value.detail.kind == kind


def test_clean_refuses_dirty_or_unpushed_work(tmp_path: Path) -> None:
    """Cleanup preserves work unless force is explicit."""

    service, runner, repo = make_service(tmp_path)
    service.create_branch(
        name="unsafe", branch_config=effective(service, repo, "unsafe"), batch=True, dry_run=False
    )
    runner.sandbox_dirty = True
    with pytest.raises(PiwError) as dirty:
        service.clean("unsafe", dry_run=False, force=False)
    assert dirty.value.code is ExitCode.UNSAFE
    assert service.clean("unsafe", dry_run=False, force=True)["action"] == "removed"


def test_cleanup_fails_closed_when_unpushed_count_fails(tmp_path: Path) -> None:
    """A Git inspection failure can never be mistaken for zero unpushed commits."""

    service, runner, repo = make_service(tmp_path)
    service.create_branch(
        name="count-failure",
        branch_config=effective(service, repo, "count-failure"),
        batch=True,
        dry_run=False,
    )
    runner.head_commit = "b" * 40
    runner.rev_list_error = True
    with pytest.raises(PiwError) as captured:
        service.clean("count-failure", dry_run=False, force=False)
    assert captured.value.detail.kind == "sandbox_git_failed"
    assert service.store.exists("count-failure")
    assert runner.sandboxes


def test_branch_removes_partial_sandbox_when_reference_snapshot_fails(tmp_path: Path) -> None:
    """Creation rollback includes failures after sbx has allocated the sandbox."""

    service, runner, repo = make_service(tmp_path)
    note = tmp_path / "note.txt"
    note.write_text("reference")
    runner.snapshot_error = True
    branch_config = service.effective_branch_config(
        session_config=service.effective_session_config(refs=(tmp_path,)),
        repo_candidate=repo,
        name="snapshot-failure",
    )
    with pytest.raises(PiwError) as captured:
        service.create_branch(
            name="snapshot-failure",
            branch_config=branch_config,
            batch=True,
            dry_run=False,
        )
    assert captured.value.detail.kind == "reference_snapshot_failed"
    assert not runner.sandboxes
    assert not service.store.exists("snapshot-failure")


def test_branch_rejects_pi_metadata_errors_before_saving_state(tmp_path: Path) -> None:
    """The template's Pi version validates copied configuration before use."""

    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"broken": {"models": []}}}))
    service, runner, repo = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    runner.pi_config_error = "Warning: errors loading models.json: missing api"
    with pytest.raises(PiwError) as captured:
        service.create_branch(
            name="invalid-models",
            branch_config=effective(service, repo, "invalid-models"),
            batch=True,
            dry_run=False,
        )
    assert captured.value.detail.kind == "invalid_pi_metadata"
    assert not runner.sandboxes
    assert not service.store.exists("invalid-models")


def test_template_build_and_prune_preserve_desired_template(tmp_path: Path) -> None:
    """Template creation is reusable and prune removes only obsolete piw images."""

    service, runner, _ = make_service(tmp_path)
    runner.templates.clear()
    preview = service.ensure_template(dry_run=True)
    assert preview["action"] == "build"
    built = service.ensure_template()
    assert built["installed"] is True
    desired = desired_template(service.config)
    runner.templates.add("piw-pi-obsolete:latest")
    pruned = service.prune_templates(dry_run=False)
    assert pruned["removed"] == ["piw-pi-obsolete:latest"]
    assert desired in runner.templates


def test_template_creation_failure_rolls_back_partial_sandbox(tmp_path: Path) -> None:
    """A failed sbx create cannot leave a bootstrap sandbox behind."""

    service, runner, _ = make_service(tmp_path)
    runner.templates.clear()
    runner.create_error = True
    with pytest.raises(PiwError) as captured:
        service.ensure_template(profile="restricted")
    assert captured.value.detail.kind == "template_bootstrap_create_failed"
    assert not runner.sandboxes
    create = next(call for call in runner.calls if call[:2] == ("sbx", "create"))
    assert create[create.index("--profile") + 1] == "restricted"


def test_doctor_reports_tools_paths_template_and_mcp_config(tmp_path: Path) -> None:
    """Doctor returns independent checks instead of stopping at the first problem."""

    refs = tmp_path / "refs"
    refs.mkdir()
    mcp = tmp_path / "mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {}}))
    service, _, _ = make_service(
        tmp_path,
        sandbox_config=SandboxConfig(read_only_refs=(refs,)),
        pi_config=PiConfig(mcp_file=mcp),
    )
    checks = service.doctor(live=False, timeout_seconds=30)
    names = {check.name for check in checks}
    assert {
        "git",
        "sbx",
        "uv",
        "sbx-capabilities",
        "mcp-file",
        "pi-template",
    } <= names


def test_doctor_rejects_metadata_that_contains_credentials(tmp_path: Path) -> None:
    """Readiness checks validate configured files instead of checking existence alone."""

    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"example": {"apiKey": "secret"}}}))
    service, _, _ = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    check = next(
        item
        for item in service.doctor(live=False, timeout_seconds=30)
        if item.name == "models-file"
    )
    assert check.status == "fail"
    assert "may contain a secret" in check.message


def test_settings_mcp_and_interactive_pi_are_seeded(tmp_path: Path) -> None:
    """Non-secret Pi settings and native MCP client config are copied into the sandbox."""

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"packages": ["supplied"], "theme": "dark"}))
    mcp = tmp_path / "mcp.json"
    mcp.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "public-tools": {
                        "transport": "streamable-http",
                        "url": "https://mcp.example.test/mcp",
                        "auth": {"type": "oauth"},
                    }
                }
            }
        )
    )
    service, runner, repo = make_service(
        tmp_path,
        pi_config=PiConfig(settings_file=settings, mcp_file=mcp),
    )
    service.create_branch(
        name="interactive",
        branch_config=effective(service, repo, "interactive"),
        batch=False,
        dry_run=False,
    )
    seeded = json.loads(runner.seeded_files["settings.json"])
    assert seeded["packages"] == ["existing", "supplied"]
    seeded_mcp = json.loads(runner.seeded_files["mcp.json"])
    assert seeded_mcp["mcpServers"]["public-tools"]["auth"] == {"type": "oauth"}
    pi_calls = [
        call
        for call in runner.calls
        if call[:2] == ("sbx", "exec") and "pi" in call and "--list-models" not in call
    ]
    assert len(pi_calls) == 1
    assert "--name" in pi_calls[0]
    assert "--interactive" in pi_calls[0]


def test_interactive_pi_uses_guest_skill_paths(tmp_path: Path) -> None:
    """Pi receives paths as they appear inside the Linux sandbox."""

    skills = tmp_path / "skills"
    skills.mkdir()
    service, runner, repo = make_service(tmp_path, pi_config=PiConfig(skill_paths=(skills,)))
    service.create_branch(
        name="skills",
        branch_config=effective(service, repo, "skills"),
        batch=False,
        dry_run=False,
    )
    pi_call = next(
        call
        for call in runner.calls
        if call[:2] == ("sbx", "exec") and "pi" in call and "--list-models" not in call
    )
    skill_index = pi_call.index("--skill")
    assert pi_call[skill_index + 1] == sandbox_guest_path(skills)


def test_missing_sandbox_and_stale_list_are_reported(tmp_path: Path) -> None:
    """Lost runtime state remains visible and gives a recovery error."""

    service, runner, repo = make_service(tmp_path)
    service.create_branch(
        name="stale", branch_config=effective(service, repo, "stale"), batch=True, dry_run=False
    )
    runner.sandboxes.clear()
    assert service.list_sessions()[0]["status"] == SandboxPhase.MISSING
    with pytest.raises(PiwError) as missing:
        service.status("stale")
    assert missing.value.detail.kind == "missing_sandbox"


def test_shell_stop_preview_and_unpushed_cleanup(tmp_path: Path) -> None:
    """Shell access works, stop previews are inert, and unpushed commits are retained."""

    service, runner, repo = make_service(tmp_path)
    service.create_branch(
        name="work", branch_config=effective(service, repo, "work"), batch=True, dry_run=False
    )
    service.shell("work")
    assert service.stop("work", dry_run=True)["action"] == "would_stop"
    assert next(iter(runner.sandboxes.values())) == SandboxPhase.RUNNING
    runner.head_commit = "b" * 40
    runner.upstream_exists = False
    with pytest.raises(PiwError) as unpushed:
        service.clean("work", dry_run=False, force=False)
    assert unpushed.value.detail.kind == "unsafe_cleanup"


def test_live_doctor_probe_is_removed(tmp_path: Path) -> None:
    """The live probe validates runtime behavior and always cleans itself up."""

    service, runner, _ = make_service(tmp_path)
    checks = service.doctor(live=True, timeout_seconds=30)
    live = next(check for check in checks if check.name == "live-sandbox")
    assert live.status == "pass"
    assert not any(name.startswith("piw-doctor-") for name in runner.sandboxes)


def test_live_doctor_uses_template_pi_to_reject_bad_metadata(tmp_path: Path) -> None:
    """The opt-in live probe validates metadata with the configured Pi package."""

    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"broken": {"models": []}}}))
    service, runner, _ = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    runner.pi_config_error = "Warning: errors loading models.json: missing api"
    live = next(
        check
        for check in service.doctor(live=True, timeout_seconds=30)
        if check.name == "live-sandbox"
    )
    assert live.status == "fail"
    assert "errors loading models.json" in live.message
    assert not any(name.startswith("piw-doctor-") for name in runner.sandboxes)


def test_live_doctor_uses_template_pi_to_reject_bad_mcp_config(tmp_path: Path) -> None:
    """An MCP-only setup still runs the extension-aware Pi metadata probe."""

    mcp = tmp_path / "mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {"broken": {}}}))
    service, runner, _ = make_service(tmp_path, pi_config=PiConfig(mcp_file=mcp))
    runner.pi_config_error = "Error loading mcp.json: missing transport"
    live = next(
        check
        for check in service.doctor(live=True, timeout_seconds=30)
        if check.name == "live-sandbox"
    )
    assert live.status == "fail"
    assert "Error loading mcp.json" in live.message
    assert not any(name.startswith("piw-doctor-") for name in runner.sandboxes)
