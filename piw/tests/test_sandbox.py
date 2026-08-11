"""Docker Sandboxes adapter tests."""

from pathlib import Path

import pytest

from piw.errors import PiwError
from piw.models import (
    AppConfig,
    BranchMode,
    EffectiveBranchConfig,
    EffectiveSessionConfig,
    PiConfig,
    SandboxSecretConfig,
    ThinkingLevel,
)
from piw.sandbox import SbxClient, desired_template, read_only_exposure, template_fingerprint
from tests.fakes import ScenarioRunner


def effective(repo: Path) -> EffectiveBranchConfig:
    """Create a representative branch configuration."""

    return EffectiveBranchConfig(
        repo=repo,
        mode=BranchMode.NEW,
        base_ref="HEAD",
        base_commit=None,
        branch="piw/example",
        source_ref=None,
        upstream=None,
        upstream_ref=None,
        read_only_refs=(repo.parent,),
        skill_paths=(repo.parent / "skills",),
        model="provider/model",
        thinking=ThinkingLevel.HIGH,
        profile="developer",
        extensions=("npm:extension@1",),
        models_file=None,
        settings_file=None,
        mcp_file=None,
        cpus=4,
        memory="8g",
        timeout_seconds=60,
    )


def session_config(reference: Path) -> EffectiveSessionConfig:
    """Create representative non-Git session settings."""

    return EffectiveSessionConfig(
        read_only_refs=(reference,),
        skill_paths=(),
        model="provider/model",
        thinking=ThinkingLevel.HIGH,
        profile="developer",
        extensions=(),
        models_file=None,
        settings_file=None,
        mcp_file=None,
        cpus=2,
        memory="4g",
        timeout_seconds=60,
    )


def test_template_fingerprint_is_stable_and_input_sensitive() -> None:
    """Only template-owned inputs affect the reusable tag."""

    base = AppConfig()
    changed = AppConfig(pi=PiConfig(extensions=("npm:extension@1",)))
    assert template_fingerprint(base) == template_fingerprint(base)
    assert template_fingerprint(base) != template_fingerprint(changed)
    assert desired_template(base).startswith("piw-pi-")


def test_sandbox_and_template_json_are_decoded(tmp_path: Path) -> None:
    """The adapter consumes sbx's stable JSON inventory formats."""

    runner = ScenarioRunner(tmp_path)
    runner.sandboxes["task"] = "stopped"
    runner.templates.add("piw-pi-test:latest")
    client = SbxClient(runner)
    assert client.list_sandboxes()[0].name == "task"
    assert client.list_sandboxes()[0].status == "stopped"
    assert client.list_templates()[0].reference == "piw-pi-test:latest"
    assert client.has_template("piw-pi-test:latest")


def test_create_uses_clone_resources_and_read_only_references(tmp_path: Path) -> None:
    """Creation preserves the writable clone while mounting references read-only."""

    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "skills").mkdir()
    runner = ScenarioRunner(repo)
    client = SbxClient(runner)
    client.create(
        name="piw-repo-example",
        branch_config=effective(repo),
        template="piw-pi-test:latest",
        timeout_seconds=60,
    )
    command = runner.calls[-1]
    assert "--clone" in command
    assert command[command.index("--cpus") : command.index("--cpus") + 2] == ("--cpus", "4")
    assert "--memory" in command
    assert "--static-mcp" not in command
    assert f"{tmp_path}:ro" not in command
    assert f"{tmp_path / 'skills'}:ro" in command


def test_create_workspace_omits_clone_and_mounts_references(tmp_path: Path) -> None:
    """Disposable workspaces use the same limits and read-only inputs without Git cloning."""

    workspace = tmp_path / "workspace"
    reference = tmp_path / "reference"
    workspace.mkdir()
    reference.mkdir()
    runner = ScenarioRunner(workspace)

    SbxClient(runner).create_workspace(
        name="piw-chat-example",
        workspace=workspace,
        session_config=session_config(reference),
        template="piw-pi-test:latest",
        timeout_seconds=60,
    )

    command = runner.calls[-1]
    assert "--clone" not in command
    assert command[command.index("--cpus") : command.index("--cpus") + 2] == ("--cpus", "2")
    assert f"{reference}:ro" in command


def test_ancestor_reference_expands_to_disjoint_siblings(tmp_path: Path) -> None:
    """A broad parent remains readable without making its nested clone read-only."""

    root = tmp_path / "programming"
    repo = root / "github" / "owner" / "active"
    siblings = (
        root / "gitlab",
        root / "github" / "other-owner",
        root / "github" / "owner" / "sibling",
    )
    repo.mkdir(parents=True)
    for sibling in siblings:
        sibling.mkdir(parents=True)
    root_file = root / "notes.txt"
    root_file.write_text("reference")
    exposure = read_only_exposure(repo, (root,), ())
    assert set(exposure.mounts) == set(siblings)
    assert exposure.snapshots == (root_file,)
    assert root not in exposure.mounts
    assert repo not in exposure.mounts


def test_paths_inside_clone_are_not_mounted_over_writable_files(tmp_path: Path) -> None:
    """References and skills already present in the clone need no host mount."""

    repo = tmp_path / "repo"
    nested = repo / "docs" / "skills"
    nested.mkdir(parents=True)
    exposure = read_only_exposure(repo, (repo / "docs",), (nested,))
    assert exposure == read_only_exposure(repo, (), ())


def test_overlapping_external_paths_collapse_to_one_mount(tmp_path: Path) -> None:
    """Nested references do not produce overlapping Docker workspaces."""

    repo = tmp_path / "repo"
    repo.mkdir()
    references = tmp_path / "references"
    nested = references / "nested"
    nested.mkdir(parents=True)
    exposure = read_only_exposure(repo, (references,), (nested,))
    assert exposure.mounts == (references,)


def test_create_snapshots_disjoint_reference_files(tmp_path: Path) -> None:
    """Files beside the active path are copied without mounting their parent."""

    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "skills").mkdir()
    note = tmp_path / "notes.txt"
    note.write_text("reference")
    runner = ScenarioRunner(repo)
    SbxClient(runner).create(
        name="piw-repo-example",
        branch_config=effective(repo),
        template="piw-pi-test:latest",
        timeout_seconds=60,
    )
    assert (
        "sbx",
        "cp",
        "--follow-link",
        str(note),
        f"piw-repo-example:{tmp_path}/",
    ) in runner.calls


def test_exec_stop_remove_and_template_lifecycle(tmp_path: Path) -> None:
    """Lifecycle calls preserve state until explicit removal."""

    runner = ScenarioRunner(tmp_path)
    runner.sandboxes["task"] = "running"
    client = SbxClient(runner)
    assert client.exec("task", ("printf", "ok")).returncode == 0
    client.stop("task")
    assert runner.sandboxes["task"] == "stopped"
    client.save_template("task", "piw-pi-test:latest", timeout_seconds=60)
    assert "piw-pi-test:latest" in runner.templates
    client.remove_template("piw-pi-test:latest")
    client.remove("task")
    assert not runner.sandboxes
    assert not runner.templates


def test_custom_secret_uses_stdin_and_redacted_inventory(tmp_path: Path) -> None:
    """Credential values never appear in the subprocess argument vector."""

    runner = ScenarioRunner(tmp_path)
    client = SbxClient(runner)
    declaration = SandboxSecretConfig(
        source_env="HOST_TOKEN",
        sandbox_env="EXAMPLE_API_KEY",
        hosts=("api.example.test",),
        placeholder="sk-{rand}",
    )
    result = client.set_custom_secret(
        declaration,
        placeholder="sk-placeholder",
        value="high-entropy-value",
    )
    assert "high-entropy-value" not in result.argv
    assert runner.secret_inputs == ["high-entropy-value"]
    inventory = client.list_global_secrets()
    assert "sk-placeholder" in inventory
    assert "high-entropy-value" not in inventory


@pytest.mark.parametrize("payload", ["not-json", "[]"])
def test_invalid_sbx_json_is_rejected(payload: str, tmp_path: Path) -> None:
    """Malformed runtime output never leaks untyped data into the application."""

    runner = ScenarioRunner(tmp_path, sandbox_list_output=payload)
    with pytest.raises(PiwError) as captured:
        SbxClient(runner).list_sandboxes()
    assert captured.value.detail.kind == "invalid_sbx_output"
