"""Typed adapter around the Docker Sandboxes CLI."""

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from piw.errors import ExitCode, PiwError
from piw.models import (
    AppConfig,
    CommandResult,
    EffectiveBranchConfig,
    EffectiveSessionConfig,
    SandboxPhase,
    SandboxSecretConfig,
)
from piw.process import Runner


@dataclass(frozen=True, slots=True)
class SandboxInfo:
    """Relevant fields returned by ``sbx ls --json``."""

    name: str
    status: SandboxPhase


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
    writable_root: Path,
    references: tuple[Path, ...],
    skills: tuple[Path, ...],
) -> ReadOnlyExposure:
    """Expose references without mounting over the writable workspace."""

    mounts: set[Path] = set()
    snapshots: set[Path] = set()
    for reference in (*references, *skills):
        if reference == writable_root or reference.is_relative_to(writable_root):
            continue
        try:
            relative_root = writable_root.relative_to(reference)
        except ValueError:
            mounts.add(reference)
            continue

        current = reference
        try:
            for segment in relative_root.parts:
                if not current.is_dir():
                    break
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
    """Decode an sbx JSON response and require a top-level object."""

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
        """Run an sbx command and translate timeouts into piw errors."""

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
        """Return a successful sbx result or raise the requested error kind."""

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
        flags = {flag for flag in ("--clone", "--profile") if flag in result.stdout}
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
                status = (
                    SandboxPhase(raw_status)
                    if isinstance(raw_status, str)
                    else SandboxPhase.UNKNOWN
                )
            except ValueError:
                status = SandboxPhase.UNKNOWN

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
        branch_config: EffectiveBranchConfig,
        template: str,
        timeout_seconds: int,
    ) -> CommandResult:
        """Create a detached clone-mode branch sandbox."""

        argv = self._create_argv(name, branch_config, template=template, clone=True)
        argv.extend(("shell", str(branch_config.repo)))

        exposure = read_only_exposure(
            branch_config.repo,
            branch_config.read_only_refs,
            branch_config.skill_paths,
        )

        result = self._create_with_exposure(
            tuple(argv),
            name=name,
            exposure=exposure,
            timeout_seconds=timeout_seconds,
        )
        return result

    @staticmethod
    def _create_argv(
        name: str,
        session_config: EffectiveSessionConfig,
        *,
        template: str,
        clone: bool,
    ) -> list[str]:
        """Build common resource and governance flags for a sandbox."""

        argv = ["sbx", "create"]
        if clone:
            argv.append("--clone")
        argv.extend(("--name", name, "--template", template))
        if session_config.cpus:
            argv.extend(("--cpus", str(session_config.cpus)))
        if session_config.memory:
            argv.extend(("--memory", session_config.memory))
        if session_config.profile:
            argv.extend(("--profile", session_config.profile))
        return argv

    def _create_with_exposure(
        self,
        argv: tuple[str, ...],
        *,
        name: str,
        exposure: ReadOnlyExposure,
        timeout_seconds: int,
    ) -> CommandResult:
        """Create a sandbox and copy reference files that cannot be mounted."""

        command = (*argv, *(f"{path}:ro" for path in exposure.mounts))
        result = self._require(
            self._run(command, timeout_seconds=timeout_seconds),
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

    def create_workspace(
        self,
        *,
        name: str,
        workspace: Path,
        session_config: EffectiveSessionConfig,
        template: str,
        timeout_seconds: int,
    ) -> CommandResult:
        """Create a non-clone sandbox around an empty writable workspace."""

        argv = self._create_argv(name, session_config, template=template, clone=False)
        argv.extend(("shell", str(workspace)))
        exposure = read_only_exposure(
            workspace,
            session_config.read_only_refs,
            session_config.skill_paths,
        )
        return self._create_with_exposure(
            tuple(argv),
            name=name,
            exposure=exposure,
            timeout_seconds=timeout_seconds,
        )

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

    def list_global_secrets(self) -> str:
        """Return the global Docker Sandbox secret inventory for reconciliation."""

        result = self._require(
            self._run(("sbx", "secret", "ls", "--global"), timeout_seconds=30),
            "secret_list_failed",
        )
        return result.stdout

    def set_custom_secret(
        self,
        declaration: SandboxSecretConfig,
        *,
        placeholder: str,
        value: str,
    ) -> CommandResult:
        """Set one custom secret while keeping its value out of process arguments."""

        argv = ["sbx", "secret", "set-custom"]
        for host in declaration.hosts:
            argv.extend(("--host", host))
        argv.extend(("--env", declaration.sandbox_env, "--placeholder", placeholder))
        return self._require(
            self._run(tuple(argv), input_text=f"{value}\n", timeout_seconds=60),
            "secret_sync_failed",
        )
