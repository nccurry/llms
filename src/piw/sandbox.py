"""Typed adapter around the Docker Sandboxes CLI."""

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from piw.errors import ExitCode, PiwError
from piw.models import AppConfig, CommandResult, EffectiveTaskConfig, TaskPhase
from piw.process import Runner


@dataclass(frozen=True, slots=True)
class SandboxInfo:
    """Relevant fields returned by ``sbx ls --json``."""

    name: str
    status: TaskPhase


@dataclass(frozen=True, slots=True)
class TemplateInfo:
    """Relevant fields returned by ``sbx template ls --json``."""

    repository: str
    tag: str

    @property
    def reference(self) -> str:
        """Return a tag accepted by ``sbx --template``."""

        repository = self.repository.removeprefix("docker.io/library/")
        return f"{repository}:{self.tag}"


@dataclass(frozen=True, slots=True)
class ReadOnlyExposure:
    """Host inputs exposed without allowing writes back to their sources."""

    mounts: tuple[Path, ...]
    snapshots: tuple[Path, ...]


def template_fingerprint(config: AppConfig) -> str:
    """Return a stable fingerprint for all template-owned inputs."""

    payload = json.dumps(
        {
            "schema": 1,
            "node_version": config.template.node_version,
            "pi_package": config.pi.package,
            "extensions": sorted(config.pi.extensions),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def desired_template(config: AppConfig) -> str:
    """Return the desired local template tag."""

    return f"{config.template.prefix}-{template_fingerprint(config)}:latest"


def read_only_exposure(
    repo: Path,
    references: tuple[Path, ...],
    skills: tuple[Path, ...],
) -> ReadOnlyExposure:
    """Expand ancestors into disjoint directory mounts and file snapshots."""

    mounts: set[Path] = set()
    snapshots: set[Path] = set()
    for reference in (*references, *skills):
        if reference == repo or reference.is_relative_to(repo):
            continue
        try:
            relative_repo = repo.relative_to(reference)
        except ValueError:
            mounts.add(reference)
            continue

        current = reference
        try:
            for segment in relative_repo.parts:
                for child in current.iterdir():
                    if child.name == segment:
                        continue
                    if child.is_dir():
                        mounts.add(child)
                    elif child.is_file() or child.is_symlink():
                        snapshots.add(child)
                current /= segment
        except OSError as error:
            raise PiwError(
                f"cannot expand read-only ancestor {reference}: {error}",
                code=ExitCode.CONFIG,
                kind="unreadable_reference",
            ) from error
    disjoint_mounts = {
        mount
        for mount in mounts
        if not any(mount != other and mount.is_relative_to(other) for other in mounts)
    }
    disjoint_snapshots = {
        snapshot
        for snapshot in snapshots
        if not any(snapshot.is_relative_to(mount) for mount in disjoint_mounts)
    }
    return ReadOnlyExposure(tuple(sorted(disjoint_mounts)), tuple(sorted(disjoint_snapshots)))


def _decode_object(output: str, label: str) -> dict[str, object]:
    try:
        value = cast("object", json.loads(output))
    except json.JSONDecodeError as error:
        raise PiwError(
            f"{label} returned invalid JSON: {error}",
            code=ExitCode.SANDBOX,
            kind="invalid_sbx_output",
        ) from error
    if not isinstance(value, dict):
        raise PiwError(
            f"{label} returned a non-object JSON value",
            code=ExitCode.SANDBOX,
            kind="invalid_sbx_output",
        )
    return cast("dict[str, object]", value)


class SbxClient:
    """Docker Sandboxes operations with consistent error handling."""

    def __init__(self, runner: Runner) -> None:
        """Initialize the client with an external command runner."""

        self.runner = runner

    def _run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        interactive: bool = False,
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        try:
            return self.runner.run(
                argv,
                input_text=input_text,
                interactive=interactive,
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise PiwError(
                f"timed out after {timeout_seconds} seconds: {' '.join(argv[:3])}",
                code=ExitCode.TIMEOUT,
                kind="timeout",
            ) from error

    @staticmethod
    def _require(result: CommandResult, kind: str) -> CommandResult:
        if result.returncode == 0:
            return result
        message = result.stderr.strip() or result.stdout.strip() or "sbx command failed"
        raise PiwError(message, code=ExitCode.SANDBOX, kind=kind)

    def version(self) -> CommandResult:
        """Return ``sbx version`` without requiring success."""

        return self._run(("sbx", "version"), timeout_seconds=30)

    def capabilities(self) -> frozenset[str]:
        """Discover creation flags supported by the installed CLI."""

        result = self._require(
            self._run(("sbx", "create", "shell", "--help"), timeout_seconds=30),
            "sbx_help_failed",
        )
        flags = {flag for flag in ("--clone", "--profile", "--static-mcp") if flag in result.stdout}
        return frozenset(flags)

    def list_sandboxes(self) -> tuple[SandboxInfo, ...]:
        """Return all sandboxes from the stable JSON interface."""

        result = self._require(
            self._run(("sbx", "ls", "--json"), timeout_seconds=30),
            "sandbox_list_failed",
        )
        decoded = _decode_object(result.stdout, "sbx ls")
        values = decoded.get("sandboxes", [])
        if not isinstance(values, list):
            raise PiwError(
                "sbx ls JSON is missing a sandboxes array",
                code=ExitCode.SANDBOX,
                kind="invalid_sbx_output",
            )
        sandboxes: list[SandboxInfo] = []
        for value in cast("list[object]", values):
            if not isinstance(value, dict):
                continue
            item = cast("dict[str, object]", value)
            raw_name = item.get("name")
            if not isinstance(raw_name, str):
                continue
            raw_status = item.get("status")
            try:
                status = TaskPhase(raw_status) if isinstance(raw_status, str) else TaskPhase.UNKNOWN
            except ValueError:
                status = TaskPhase.UNKNOWN
            sandboxes.append(
                SandboxInfo(
                    name=raw_name,
                    status=status,
                )
            )
        return tuple(sandboxes)

    def list_templates(self) -> tuple[TemplateInfo, ...]:
        """Return all local sandbox templates."""

        result = self._require(
            self._run(("sbx", "template", "ls", "--json"), timeout_seconds=30),
            "template_list_failed",
        )
        decoded = _decode_object(result.stdout, "sbx template ls")
        values = decoded.get("images", [])
        if not isinstance(values, list):
            raise PiwError(
                "sbx template ls JSON is missing an images array",
                code=ExitCode.SANDBOX,
                kind="invalid_sbx_output",
            )
        templates: list[TemplateInfo] = []
        for value in cast("list[object]", values):
            if not isinstance(value, dict):
                continue
            item = cast("dict[str, object]", value)
            repository = item.get("repository")
            tag = item.get("tag")
            if all(isinstance(item, str) for item in (repository, tag)):
                templates.append(
                    TemplateInfo(
                        repository=cast("str", repository),
                        tag=cast("str", tag),
                    )
                )
        return tuple(templates)

    def has_template(self, reference: str) -> bool:
        """Return whether the requested template is installed."""

        return any(template.reference == reference for template in self.list_templates())

    def create(
        self,
        *,
        name: str,
        task_config: EffectiveTaskConfig,
        template: str,
        timeout_seconds: int,
    ) -> CommandResult:
        """Create a detached clone-mode task sandbox."""

        argv = ["sbx", "create", "--clone", "--name", name, "--template", template]
        if task_config.cpus:
            argv.extend(("--cpus", str(task_config.cpus)))
        if task_config.memory:
            argv.extend(("--memory", task_config.memory))
        if task_config.profile:
            argv.extend(("--profile", task_config.profile))
        for server in task_config.mcp_servers:
            argv.extend(("--static-mcp", server))
        argv.extend(("shell", str(task_config.repo)))
        exposure = read_only_exposure(
            task_config.repo,
            task_config.read_only_refs,
            task_config.skill_paths,
        )
        argv.extend(f"{path}:ro" for path in exposure.mounts)
        result = self._require(
            self._run(tuple(argv), timeout_seconds=timeout_seconds),
            "sandbox_create_failed",
        )
        for source in exposure.snapshots:
            self._require(
                self._run(
                    (
                        "sbx",
                        "cp",
                        "--follow-link",
                        str(source),
                        f"{name}:{source.parent}/",
                    ),
                    timeout_seconds=timeout_seconds,
                ),
                "reference_snapshot_failed",
            )
        return result

    def create_bootstrap(
        self,
        *,
        name: str,
        workspace: Path,
        profile: str | None,
        template: str | None = None,
        timeout_seconds: int,
    ) -> CommandResult:
        """Create the temporary sandbox used to build a template."""

        argv = ["sbx", "create", "--name", name]
        if template:
            argv.extend(("--template", template))
        if profile:
            argv.extend(("--profile", profile))
        argv.extend(("shell", str(workspace)))
        return self._require(
            self._run(tuple(argv), timeout_seconds=timeout_seconds),
            "template_bootstrap_create_failed",
        )

    def exec(
        self,
        name: str,
        command: tuple[str, ...],
        *,
        workdir: Path | None = None,
        input_text: str | None = None,
        interactive: bool = False,
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        """Execute a command inside a sandbox."""

        argv = ["sbx", "exec"]
        if interactive:
            argv.extend(("--interactive", "--tty"))
        elif input_text is not None:
            argv.append("--interactive")
        if workdir:
            argv.extend(("--workdir", str(workdir)))
        argv.append(name)
        argv.extend(command)
        return self._run(
            tuple(argv),
            input_text=input_text,
            interactive=interactive,
            timeout_seconds=timeout_seconds,
        )

    def stop(self, name: str, *, timeout_seconds: int = 60) -> CommandResult:
        """Stop a sandbox without removing it."""

        return self._require(
            self._run(("sbx", "stop", name), timeout_seconds=timeout_seconds),
            "sandbox_stop_failed",
        )

    def remove(self, name: str, *, timeout_seconds: int = 120) -> CommandResult:
        """Remove a sandbox without an interactive confirmation."""

        return self._require(
            self._run(("sbx", "rm", "--force", name), timeout_seconds=timeout_seconds),
            "sandbox_remove_failed",
        )

    def save_template(
        self,
        sandbox: str,
        template: str,
        *,
        timeout_seconds: int,
    ) -> CommandResult:
        """Save a stopped bootstrap sandbox as a reusable template."""

        return self._require(
            self._run(
                ("sbx", "template", "save", sandbox, template),
                timeout_seconds=timeout_seconds,
            ),
            "template_save_failed",
        )

    def remove_template(self, reference: str, *, timeout_seconds: int = 120) -> CommandResult:
        """Remove one local sandbox template."""

        return self._require(
            self._run(("sbx", "template", "rm", reference), timeout_seconds=timeout_seconds),
            "template_remove_failed",
        )

    def inspect_mcp(self, name: str) -> bool:
        """Return whether an MCP server alias is registered."""

        result = self._run(("sbx", "mcp", "inspect", name), timeout_seconds=30)
        return result.returncode == 0
