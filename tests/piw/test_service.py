"""Task and template orchestration tests."""

import json
from pathlib import Path

import pytest

from piw.errors import ExitCode, PiwError
from piw.models import (
    AppConfig,
    EffectiveTaskConfig,
    PiConfig,
    SandboxConfig,
    TaskPhase,
    ThinkingLevel,
)
from piw.sandbox import desired_template
from piw.service import PiwService, normalize_task_name, sandbox_name
from piw.state import StateStore
from tests.piw.fakes import ScenarioRunner


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
    service = PiwService(config, runner, StateStore(tmp_path / "state"))
    return service, runner, repo


def effective(
    service: PiwService,
    repo: Path,
    task: str = "Feature Work",
) -> EffectiveTaskConfig:
    """Resolve a default test task configuration."""

    return service.effective_task_config(repo_candidate=repo, task=task)


@pytest.mark.parametrize(
    ("label", "expected"),
    [("Fix Exporter Metrics", "fix-exporter-metrics"), ("  A/B  ", "a-b")],
)
def test_task_names_are_stable(label: str, expected: str, tmp_path: Path) -> None:
    """Task labels become readable identifiers and collision-safe sandbox names."""

    assert normalize_task_name(label) == expected
    assert sandbox_name(label, tmp_path).startswith("piw-")


def test_empty_task_name_is_rejected() -> None:
    """A task must have a usable persistent identifier."""

    with pytest.raises(PiwError) as captured:
        normalize_task_name("!!!")
    assert captured.value.code is ExitCode.USAGE


def test_effective_config_merges_repeatable_overrides(tmp_path: Path) -> None:
    """CLI additions extend rather than erase user defaults."""

    refs = tmp_path / "refs"
    skills = tmp_path / "skills"
    extra = tmp_path / "extra"
    for path in (refs, skills, extra):
        path.mkdir()
    service, _, repo = make_service(
        tmp_path,
        sandbox_config=SandboxConfig(read_only_refs=(refs,), mcp_servers=("jira",)),
        pi_config=PiConfig(skill_paths=(skills,), extensions=("base",)),
    )
    resolved = service.effective_task_config(
        repo_candidate=repo,
        task="test",
        refs=(extra,),
        skills=(extra,),
        mcp_servers=("gitlab",),
        extensions=("extra",),
        model="provider/model",
        thinking=ThinkingLevel.XHIGH,
    )
    assert resolved.read_only_refs == (refs, extra)
    assert resolved.skill_paths == (skills, extra)
    assert resolved.mcp_servers == ("jira", "gitlab")
    assert resolved.extensions == ("base", "extra")
    assert resolved.thinking is ThinkingLevel.XHIGH


def test_effective_config_rejects_invalid_git_branch(tmp_path: Path) -> None:
    """Branch names fail before template or sandbox work begins."""

    service, _, repo = make_service(tmp_path)
    with pytest.raises(PiwError) as captured:
        service.effective_task_config(
            repo_candidate=repo,
            task="test",
            branch="bad..branch",
        )
    assert captured.value.detail.kind == "invalid_branch"


def test_start_dry_run_is_read_only(tmp_path: Path) -> None:
    """Dry-run resolves names and templates without creating state."""

    service, runner, repo = make_service(tmp_path)
    data = service.start(
        task="Feature Work",
        task_config=effective(service, repo),
        batch=True,
        dry_run=True,
    )
    assert data["action"] == "create"
    assert data["task"] == "feature-work"
    assert not runner.sandboxes
    assert not service.store.exists("feature-work")


def test_start_batch_seeds_state_and_list(tmp_path: Path) -> None:
    """A successful batch start creates the branch, metadata, and task record."""

    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"example": {"models": []}}}))
    service, runner, repo = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    data = service.start(
        task="Feature Work",
        task_config=effective(service, repo),
        batch=True,
        dry_run=False,
    )
    assert data["action"] == "created"
    record = service.store.load("feature-work")
    assert record.branch == "piw/feature-work"
    assert record.sandbox in runner.sandboxes
    assert "models.json" in runner.seeded_files
    assert service.list_tasks()[0]["status"] == TaskPhase.RUNNING


def test_start_rejects_dirty_host_and_missing_mcp(tmp_path: Path) -> None:
    """Non-reproducible host state and unknown MCP aliases fail before creation."""

    service, runner, repo = make_service(tmp_path)
    runner.host_clean = False
    with pytest.raises(PiwError) as dirty:
        service.start(
            task="dirty", task_config=effective(service, repo, "dirty"), batch=True, dry_run=False
        )
    assert dirty.value.code is ExitCode.UNSAFE

    runner.host_clean = True
    mcp_config = service.effective_task_config(
        repo_candidate=repo, task="mcp", mcp_servers=("jira",)
    )
    with pytest.raises(PiwError) as mcp:
        service.start(task="mcp", task_config=mcp_config, batch=True, dry_run=False)
    assert mcp.value.detail.kind == "missing_mcp_registration"


def test_status_exec_stop_resume_and_clean(tmp_path: Path) -> None:
    """A task survives stop/resume and is removed only after Git safety checks."""

    service, runner, repo = make_service(tmp_path)
    service.start(
        task="lifecycle",
        task_config=effective(service, repo, "lifecycle"),
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
    service.resume("lifecycle", timeout_seconds=30)
    assert service.store.load("lifecycle").session_started is True
    service.resume("lifecycle", timeout_seconds=30)
    pi_calls = [call for call in runner.calls if "pi" in call]
    assert "--continue" not in pi_calls[-2]
    assert "--continue" in pi_calls[-1]
    cleaned = service.clean("lifecycle", dry_run=False, force=False)
    assert cleaned["action"] == "removed"
    assert not runner.sandboxes
    assert not service.store.exists("lifecycle")


def test_clean_refuses_dirty_or_unpushed_work(tmp_path: Path) -> None:
    """Cleanup preserves work unless force is explicit."""

    service, runner, repo = make_service(tmp_path)
    service.start(
        task="unsafe", task_config=effective(service, repo, "unsafe"), batch=True, dry_run=False
    )
    runner.sandbox_dirty = True
    with pytest.raises(PiwError) as dirty:
        service.clean("unsafe", dry_run=False, force=False)
    assert dirty.value.code is ExitCode.UNSAFE
    assert service.clean("unsafe", dry_run=False, force=True)["action"] == "removed"


def test_cleanup_fails_closed_when_unpushed_count_fails(tmp_path: Path) -> None:
    """A Git inspection failure can never be mistaken for zero unpushed commits."""

    service, runner, repo = make_service(tmp_path)
    service.start(
        task="count-failure",
        task_config=effective(service, repo, "count-failure"),
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


def test_start_removes_partial_sandbox_when_reference_snapshot_fails(tmp_path: Path) -> None:
    """Creation rollback includes failures after sbx has allocated the sandbox."""

    service, runner, repo = make_service(tmp_path)
    note = tmp_path / "note.txt"
    note.write_text("reference")
    runner.snapshot_error = True
    task_config = service.effective_task_config(
        repo_candidate=repo,
        task="snapshot-failure",
        refs=(tmp_path,),
    )
    with pytest.raises(PiwError) as captured:
        service.start(
            task="snapshot-failure",
            task_config=task_config,
            batch=True,
            dry_run=False,
        )
    assert captured.value.detail.kind == "reference_snapshot_failed"
    assert not runner.sandboxes
    assert not service.store.exists("snapshot-failure")


def test_start_rejects_pi_metadata_errors_before_saving_state(tmp_path: Path) -> None:
    """The template's Pi version validates copied configuration before use."""

    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"broken": {"models": []}}}))
    service, runner, repo = make_service(tmp_path, pi_config=PiConfig(models_file=models))
    runner.pi_config_error = "Warning: errors loading models.json: missing api"
    with pytest.raises(PiwError) as captured:
        service.start(
            task="invalid-models",
            task_config=effective(service, repo, "invalid-models"),
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


def test_doctor_reports_tools_paths_template_and_mcp(tmp_path: Path) -> None:
    """Doctor returns independent checks instead of stopping at the first problem."""

    refs = tmp_path / "refs"
    refs.mkdir()
    service, runner, _ = make_service(
        tmp_path,
        sandbox_config=SandboxConfig(read_only_refs=(refs,), mcp_servers=("jira",)),
    )
    runner.registered_mcp.add("jira")
    checks = service.doctor(live=False, timeout_seconds=30)
    names = {check.name for check in checks}
    assert {"git", "sbx", "uv", "sbx-capabilities", "mcp:jira", "pi-template"} <= names


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
    """Non-secret settings are merged and MCP uses the sandbox gateway."""

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"packages": ["supplied"], "theme": "dark"}))
    service, runner, repo = make_service(
        tmp_path,
        sandbox_config=SandboxConfig(mcp_servers=("jira",)),
        pi_config=PiConfig(settings_file=settings),
    )
    runner.registered_mcp.add("jira")
    service.start(
        task="interactive",
        task_config=effective(service, repo, "interactive"),
        batch=False,
        dry_run=False,
    )
    seeded = json.loads(runner.seeded_files["settings.json"])
    assert seeded["packages"] == ["existing", "supplied"]
    assert "mcp.json" in runner.seeded_files
    pi_calls = [
        call
        for call in runner.calls
        if call[:2] == ("sbx", "exec") and "pi" in call and "--list-models" not in call
    ]
    assert len(pi_calls) == 1
    assert "--name" in pi_calls[0]
    assert "--interactive" in pi_calls[0]


def test_missing_sandbox_and_stale_list_are_reported(tmp_path: Path) -> None:
    """Lost runtime state remains visible and gives a recovery error."""

    service, runner, repo = make_service(tmp_path)
    service.start(
        task="stale", task_config=effective(service, repo, "stale"), batch=True, dry_run=False
    )
    runner.sandboxes.clear()
    assert service.list_tasks()[0]["status"] == TaskPhase.MISSING
    with pytest.raises(PiwError) as missing:
        service.status("stale")
    assert missing.value.detail.kind == "missing_sandbox"


def test_shell_stop_preview_and_unpushed_cleanup(tmp_path: Path) -> None:
    """Shell access works, stop previews are inert, and unpushed commits are retained."""

    service, runner, repo = make_service(tmp_path)
    service.start(
        task="work", task_config=effective(service, repo, "work"), batch=True, dry_run=False
    )
    service.shell("work")
    assert service.stop("work", dry_run=True)["action"] == "would_stop"
    assert next(iter(runner.sandboxes.values())) == TaskPhase.RUNNING
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
