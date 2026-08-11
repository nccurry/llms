"""Public command-line contract tests."""

import json
from pathlib import Path
from typing import cast

import pytest
import yaml

from piw.cli import build_parser, emit, main
from piw.errors import ExitCode, PiwError
from piw.models import (
    AppConfig,
    BranchMode,
    DoctorCheck,
    EffectiveBranchConfig,
    EffectiveSessionConfig,
    HostChangesPolicy,
    OutputFormat,
    ThinkingLevel,
)
from piw.process import SubprocessRunner
from piw.service import PiwService
from piw.state import StateStore


class FakeService:
    """Return stable values for CLI dispatch coverage."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.branch_config_kwargs: dict[str, object] = {}
        self.branch_kwargs: dict[str, object] = {}
        self.chat_args: tuple[object, ...] = ()
        self.chat_kwargs: dict[str, object] = {}

    def effective_session_config(self, **kwargs: object) -> EffectiveSessionConfig:
        del kwargs
        return EffectiveSessionConfig(
            read_only_refs=(),
            skill_paths=(),
            model=None,
            thinking=ThinkingLevel.HIGH,
            profile=None,
            extensions=(),
            models_file=None,
            settings_file=None,
            mcp_file=None,
            cpus=0,
            memory=None,
            timeout_seconds=60,
        )

    def doctor(self, *, live: bool, timeout_seconds: int) -> list[DoctorCheck]:
        del live, timeout_seconds
        return [DoctorCheck("fake", "pass", "ready")]

    def effective_branch_config(self, **kwargs: object) -> EffectiveBranchConfig:
        self.branch_config_kwargs = kwargs
        return EffectiveBranchConfig(
            repo=self.repo,
            mode=BranchMode.NEW,
            base_ref="HEAD",
            base_commit=None,
            branch="piw/task",
            source_ref=None,
            upstream=None,
            upstream_ref=None,
            read_only_refs=(),
            skill_paths=(),
            model=None,
            thinking=ThinkingLevel.HIGH,
            profile=None,
            extensions=(),
            models_file=None,
            settings_file=None,
            mcp_file=None,
            cpus=0,
            memory=None,
            timeout_seconds=60,
        )

    def create_branch(self, **kwargs: object) -> dict[str, object]:
        self.branch_kwargs = kwargs
        return {"action": "created"}

    def chat(
        self,
        name: str | None,
        session_config: EffectiveSessionConfig,
        *,
        temporary: bool,
        batch: bool,
        dry_run: bool,
    ) -> dict[str, object]:
        self.chat_args = (name, session_config)
        self.chat_kwargs = {
            "temporary": temporary,
            "batch": batch,
            "dry_run": dry_run,
        }
        return {"action": "created", "name": name, "temporary": temporary}

    def resume(self, name: str, *, timeout_seconds: int) -> dict[str, object]:
        del name, timeout_seconds
        return {"action": "resumed"}

    def list_sessions(self) -> list[dict[str, object]]:
        return [{"name": "task", "type": "branch", "status": "running"}]

    def status(self, name: str) -> dict[str, object]:
        return {"name": name, "status": "running"}

    def shell(self, name: str, cwd: Path | None = None) -> None:
        del name, cwd

    def execute(
        self,
        name: str,
        command: tuple[str, ...],
        cwd: Path | None = None,
    ) -> dict[str, object]:
        del name, cwd
        return {"returncode": 3 if command == ("false",) else 0}

    def stop(self, name: str, *, dry_run: bool) -> dict[str, object]:
        del name, dry_run
        return {"action": "stopped"}

    def clean(self, name: str, *, dry_run: bool, force: bool) -> dict[str, object]:
        del name, dry_run, force
        return {"action": "removed"}

    def secret_status(self) -> list[dict[str, object]]:
        return [{"sandbox_env": "EXAMPLE_API_KEY", "status": "synced"}]

    def sync_secrets(self, *, dry_run: bool, force: bool) -> list[dict[str, object]]:
        del dry_run, force
        return [{"sandbox_env": "EXAMPLE_API_KEY", "action": "unchanged"}]

    def template_status(self) -> dict[str, object]:
        return {"installed": True}

    def ensure_template(self, **kwargs: object) -> dict[str, object]:
        del kwargs
        return {"action": "unchanged"}

    def prune_templates(self, *, dry_run: bool) -> dict[str, object]:
        del dry_run
        return {"removed": []}


def install_fake_service(monkeypatch: pytest.MonkeyPatch, fake: FakeService) -> None:
    """Replace the application service constructor for CLI-only tests."""

    def constructor(
        config: AppConfig,
        runner: SubprocessRunner,
        store: StateStore,
    ) -> PiwService:
        del config, runner, store
        return cast("PiwService", fake)

    monkeypatch.setattr("piw.cli.PiwService", constructor)


def test_parser_exposes_complete_command_tree() -> None:
    """Every documented v1 command parses through the public entry point."""

    parser = build_parser()
    examples = [
        ["init", "--dry-run"],
        ["doctor"],
        ["branch", "task", "--batch", "--dry-run"],
        ["branch", "review", "--existing", "origin/feature/review", "--dry-run"],
        ["branch", "task", "--ignore-host-changes", "--dry-run"],
        ["branch", "task", "--carry-host-changes", "--dry-run"],
        ["chat", "research", "--batch", "--dry-run"],
        ["chat", "--temporary", "--dry-run"],
        ["resume", "task"],
        ["list"],
        ["status", "task"],
        ["shell", "task"],
        ["exec", "task", "--", "true"],
        ["stop", "task", "--dry-run"],
        ["clean", "task", "--dry-run"],
        ["secrets", "status"],
        ["secrets", "sync", "--dry-run"],
        ["config", "path"],
        ["config", "show", "--effective"],
        ["config", "validate"],
        ["config", "edit"],
        ["template", "status"],
        ["template", "ensure", "--dry-run"],
        ["template", "rebuild", "--dry-run"],
        ["template", "prune", "--dry-run"],
    ]
    for argv in examples:
        assert parser.parse_args(argv).command


def test_start_is_not_a_compatibility_alias() -> None:
    """The public command vocabulary has one unambiguous branch entry point."""

    with pytest.raises(PiwError):
        build_parser().parse_args(["start", "task"])


def test_branch_host_change_flags_are_explicit_and_mutually_exclusive() -> None:
    """Branch defaults to fail-closed and accepts exactly one override policy."""

    parser = build_parser()
    assert parser.parse_args(["branch", "task"]).host_changes is HostChangesPolicy.FAIL
    assert (
        parser.parse_args(["branch", "task", "--ignore-host-changes"]).host_changes
        is HostChangesPolicy.IGNORE
    )
    assert (
        parser.parse_args(["branch", "task", "--carry-host-changes"]).host_changes
        is HostChangesPolicy.CARRY
    )
    with pytest.raises(PiwError) as captured:
        parser.parse_args(["branch", "task", "--ignore-host-changes", "--carry-host-changes"])
    assert "not allowed with argument" in str(captured.value)

    with pytest.raises(PiwError) as source_conflict:
        parser.parse_args(["branch", "task", "--base", "main", "--existing", "feature/task"])
    assert "not allowed with argument" in str(source_conflict.value)


def test_branch_dispatch_forwards_host_change_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The parsed override reaches branch orchestration as a typed policy."""

    fake = FakeService(tmp_path)
    install_fake_service(monkeypatch, fake)
    code = main(
        [
            "branch",
            "task",
            "--carry-host-changes",
            "--batch",
            "--config",
            str(tmp_path / "missing.toml"),
        ]
    )
    assert code == ExitCode.SUCCESS
    assert fake.branch_kwargs["host_changes"] is HostChangesPolicy.CARRY
    capsys.readouterr()


def test_branch_dispatch_forwards_existing_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The existing branch selector reaches Git configuration unchanged."""

    fake = FakeService(tmp_path)
    install_fake_service(monkeypatch, fake)
    code = main(
        [
            "branch",
            "review",
            "--existing",
            "origin/feature/review",
            "--batch",
            "--config",
            str(tmp_path / "missing.toml"),
        ]
    )

    assert code == ExitCode.SUCCESS
    assert fake.branch_config_kwargs["existing"] == "origin/feature/review"
    capsys.readouterr()


def test_chat_dispatch_forwards_lifecycle_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Chat names and persistence flags reach orchestration unchanged."""

    fake = FakeService(tmp_path)
    install_fake_service(monkeypatch, fake)
    code = main(
        [
            "chat",
            "research",
            "--batch",
            "--config",
            str(tmp_path / "missing.toml"),
        ]
    )

    assert code == ExitCode.SUCCESS
    assert fake.chat_args[0] == "research"
    assert fake.chat_kwargs == {
        "temporary": False,
        "batch": True,
        "dry_run": False,
    }
    capsys.readouterr()


def test_init_dry_run_has_stable_json_envelope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mutating commands expose a machine-readable preview."""

    config = tmp_path / "config.toml"
    code = main(["init", "--config", str(config), "--dry-run", "--output", "json"])
    payload: object = json.loads(capsys.readouterr().out)
    assert code == ExitCode.SUCCESS
    assert isinstance(payload, dict)
    assert payload["schema_version"] == 1
    assert payload["command"] == "init"
    assert payload["data"]["action"] == "would_create"
    assert not config.exists()


def test_init_then_validate_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The generated starter configuration is immediately valid."""

    config = tmp_path / "config.toml"
    assert main(["init", "--config", str(config)]) == ExitCode.SUCCESS
    capsys.readouterr()
    assert main(["config", "validate", "--config", str(config), "--output", "json"]) == 0
    validate: object = json.loads(capsys.readouterr().out)
    assert isinstance(validate, dict)
    assert validate["command"] == "config validate"
    assert validate["data"]["valid"] is True

    assert main(["config", "show", "--config", str(config), "--effective", "--output", "json"]) == 0
    show: object = json.loads(capsys.readouterr().out)
    assert isinstance(show, dict)
    assert show["command"] == "config show"
    assert show["data"]["config_version"] == 1


def test_recovery_commands_work_with_malformed_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Users can inspect and replace a configuration that no longer parses."""

    config = tmp_path / "config.toml"
    config.write_text("not valid toml = [")
    assert main(["config", "show", "--config", str(config)]) == 0
    assert "not valid toml" in capsys.readouterr().out
    assert main(["init", "--force", "--config", str(config)]) == 0
    capsys.readouterr()
    assert main(["config", "validate", "--config", str(config)]) == 0


def test_global_output_option_survives_subparser_defaults(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Global flags work before the command as well as after it."""

    assert main(["--output", "json", "config", "path"]) == 0
    payload: object = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)
    assert payload["command"] == "config path"


def test_usage_failure_is_json_when_requested(capsys: pytest.CaptureFixture[str]) -> None:
    """Agents receive structured errors even when argument parsing fails."""

    code = main(["--output", "json", "not-a-command"])
    payload: object = json.loads(capsys.readouterr().out)
    assert code == ExitCode.USAGE
    assert isinstance(payload, dict)
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "invalid_usage"


def test_success_and_parser_failures_support_yaml(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """YAML uses the same stable envelope for successful commands and early failures."""

    config = tmp_path / "config.toml"
    assert main(["config", "path", "--config", str(config), "--output", "yaml"]) == 0
    success: object = yaml.safe_load(capsys.readouterr().out)
    assert isinstance(success, dict)
    assert success["command"] == "config path"
    assert success["data"] == str(config)

    code = main(["--output=yaml", "not-a-command"])
    failure: object = yaml.safe_load(capsys.readouterr().out)
    assert code == ExitCode.USAGE
    assert isinstance(failure, dict)
    assert failure["ok"] is False
    assert failure["error"]["kind"] == "invalid_usage"


def test_equals_output_form_and_invalid_timeout_keep_json_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Early parser failures honor both documented argparse option forms."""

    code = main(["doctor", "--timeout", "0", "--output=json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == ExitCode.USAGE
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "invalid_usage"


def test_filesystem_failure_has_stable_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ordinary host I/O failures never produce an agent-hostile traceback."""

    def fail_load(path: Path) -> AppConfig:
        raise OSError(5, f"cannot read {path}")

    monkeypatch.setattr("piw.cli.load_config", fail_load)
    code = main(["list", "--config", str(tmp_path / "config.toml"), "--output=json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == ExitCode.PREREQUISITE
    assert payload["error"]["kind"] == "os_error"


def test_config_path_for_missing_file_is_not_an_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Users can discover a config path before running init."""

    config = tmp_path / "missing.toml"
    assert main(["config", "path", "--config", str(config)]) == 0
    assert capsys.readouterr().out.strip() == str(config)


@pytest.mark.parametrize(
    ("argv", "expected_code"),
    [
        (["doctor"], 0),
        (["branch", "task", "--batch"], 0),
        (["chat", "research"], 0),
        (["chat", "--temporary"], 0),
        (["resume", "task"], 0),
        (["list"], 0),
        (["status", "task"], 0),
        (["shell", "task"], 0),
        (["exec", "task", "--", "true"], 0),
        (["exec", "task", "--", "false"], ExitCode.COMMAND),
        (["stop", "task", "--yes"], 0),
        (["clean", "task", "--yes"], 0),
        (["secrets", "status"], 0),
        (["secrets", "sync", "--dry-run"], 0),
        (["template", "status"], 0),
        (["template", "ensure"], 0),
        (["template", "rebuild", "--yes"], 0),
        (["template", "prune", "--yes"], 0),
    ],
)
def test_command_dispatch_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    expected_code: int,
) -> None:
    """Every operational command emits one JSON envelope and a stable status."""

    install_fake_service(monkeypatch, FakeService(tmp_path))
    full_argv = ["--output", "json", "--config", str(tmp_path / "missing.toml"), *argv]
    assert main(full_argv) == expected_code
    payload: object = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)
    assert payload["ok"] is (expected_code == ExitCode.SUCCESS)


def test_doctor_failure_sets_prerequisite_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Doctor reports all checks while failing automation on a hard error."""

    fake = FakeService(tmp_path)

    def failed_doctor(*, live: bool, timeout_seconds: int) -> list[DoctorCheck]:
        del live, timeout_seconds
        return [DoctorCheck("fake", "fail", "broken")]

    fake.doctor = failed_doctor
    install_fake_service(monkeypatch, fake)
    code = main(["doctor", "--output", "json", "--config", str(tmp_path / "none")])
    assert code == ExitCode.PREREQUISITE
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_existing_config_requires_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Init never overwrites configuration accidentally."""

    config = tmp_path / "config.toml"
    config.write_text("config_version = 1\n")
    code = main(["init", "--config", str(config), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == ExitCode.UNSAFE
    assert payload["error"]["kind"] == "config_exists"


def test_confirmation_is_required_for_batch_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Destructive commands fail closed when no terminal can confirm them."""

    install_fake_service(monkeypatch, FakeService(tmp_path))
    code = main(
        [
            "--output",
            "json",
            "--config",
            str(tmp_path / "none"),
            "clean",
            "task",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == ExitCode.UNSAFE
    assert payload["error"]["kind"] == "confirmation_required"


def test_missing_config_cannot_be_edited(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Config editing reports the concrete initialization command."""

    code = main(["config", "edit", "--config", str(tmp_path / "none"), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == ExitCode.CONFIG
    assert payload["error"]["kind"] == "missing_config"


def test_missing_command_has_stable_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Invoking piw without a command is an ordinary usage failure."""

    code = main(["--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == ExitCode.USAGE
    assert payload["error"]["kind"] == "missing_command"


@pytest.mark.parametrize(
    "value",
    [None, True, {"nested": [1, 2]}, [], [1, "two"], object()],
)
def test_text_output_handles_all_json_shapes(
    value: object,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Human output remains defined for scalars, collections, and empty results."""

    emit("test", value, OutputFormat.TEXT)
    assert capsys.readouterr().out


def test_version_command_reports_runtime_components(capsys: pytest.CaptureFixture[str]) -> None:
    """Version output includes the wrapper and available runtime tools."""

    assert main(["--version", "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["piw"]
    assert payload["data"]["python"]
