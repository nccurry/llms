"""Application services for task, template, and diagnostic workflows."""

import hashlib
import json
import os
import re
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

from piw.config import cache_home
from piw.errors import ExitCode, PiwError
from piw.git import GitClient
from piw.models import (
    AppConfig,
    DoctorCheck,
    EffectiveTaskConfig,
    TaskPhase,
    TaskRecord,
    ThinkingLevel,
)
from piw.process import Runner, render_command
from piw.sandbox import SandboxInfo, SbxClient, desired_template, read_only_exposure
from piw.state import StateStore

_TASK_TOKEN_RE: Final = re.compile(r"[^a-z0-9]+")
_SENSITIVE_KEY_RE: Final = re.compile(
    r"(?:api[-_]?key|private[-_]?key|(?:^|[-_])(?:access|authorization|bearer|cookie|"
    r"credential|password|refresh|secret|token)(?:$|[-_]))",
    re.IGNORECASE,
)
_ENV_REFERENCE_RE: Final = re.compile(r"\$(?:[A-Z_][A-Z0-9_]*|\{[A-Z_][A-Z0-9_]*\})")
_PI_CONFIG_ERROR_RE: Final = re.compile(
    r"(?:errors? loading (?:models|settings)\.json|(?:models|settings)\.json[^\n]*error)",
    re.IGNORECASE,
)

_BOOTSTRAP_SCRIPT: Final = r"""set -eu
node_version="$1"
pi_package="$2"
shift 2

node_score="$(
  node -e 'const p=process.versions.node.split(".");
    process.stdout.write(String(Number(p[0])*1000+Number(p[1])))' \
    2>/dev/null || printf '0'
)"
required_score="$(printf '%s' "$node_version" | sed 's/^v//' | awk -F. '{print ($1 * 1000) + $2}')"
if [ "$node_score" -lt "$required_score" ]; then
  case "$(uname -m)" in
    x86_64|amd64) node_arch=x64 ;;
    aarch64|arm64) node_arch=arm64 ;;
    *) printf 'unsupported sandbox architecture: %s\n' "$(uname -m)" >&2; exit 1 ;;
  esac
  archive="node-${node_version}-linux-${node_arch}.tar.gz"
  curl -fsSL "https://nodejs.org/dist/${node_version}/${archive}" -o "/tmp/${archive}"
  sudo mkdir -p /usr/local/lib/nodejs
  sudo tar -xzf "/tmp/${archive}" -C /usr/local/lib/nodejs --strip-components=1
  sudo ln -sf /usr/local/lib/nodejs/bin/node /usr/local/bin/node
  sudo ln -sf /usr/local/lib/nodejs/bin/npm /usr/local/bin/npm
  sudo ln -sf /usr/local/lib/nodejs/bin/npx /usr/local/bin/npx
  rm -f "/tmp/${archive}"
fi

if command -v apt-get >/dev/null; then
  attempt=0
  while sudo fuser \
    /var/lib/apt/lists/lock \
    /var/lib/dpkg/lock-frontend \
    /var/lib/dpkg/lock >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    [ "$attempt" -ge 60 ] && break
    sleep 3
  done
  sudo apt-get update -qq || true
  sudo apt-get install -y -qq fd-find ripgrep >/dev/null 2>&1 || true
  if command -v fdfind >/dev/null && ! command -v fd >/dev/null; then
    sudo ln -sf "$(command -v fdfind)" /usr/local/bin/fd
  fi
fi

npm install -g --ignore-scripts "$pi_package"
pi_bin="$(npm prefix -g)/bin/pi"
[ -x "$pi_bin" ] && sudo ln -sf "$pi_bin" /usr/local/bin/pi
pi --version

for extension in "$@"; do
  pi install "$extension"
done
"""


def normalize_task_name(value: str) -> str:
    """Normalize a user-facing task label into a stable identifier."""

    normalized = _TASK_TOKEN_RE.sub("-", value.strip().lower()).strip("-")
    normalized = normalized[:63].rstrip("-")
    if not normalized:
        raise PiwError(
            "task name must contain at least one letter or number",
            code=ExitCode.USAGE,
            kind="invalid_task_name",
        )
    return normalized


def sandbox_name(task: str, repo: Path) -> str:
    """Return a readable, collision-resistant sandbox name."""

    repo_slug = normalize_task_name(repo.name)[:24]
    task_slug = normalize_task_name(task)[:24]
    digest = hashlib.sha256(str(repo).encode()).hexdigest()[:8]
    return f"piw-{repo_slug}-{task_slug}-{digest}"[:63].rstrip("-")


def utc_now() -> str:
    """Return an RFC 3339 UTC timestamp."""

    return datetime.now(tz=UTC).isoformat()


def _failure(result_stdout: str, result_stderr: str, fallback: str) -> str:
    return result_stderr.strip() or result_stdout.strip() or fallback


def _pi_metadata_failure(returncode: int, stdout: str, stderr: str) -> str | None:
    combined = "\n".join(part for part in (stderr, stdout) if part)
    if returncode == 0 and not _PI_CONFIG_ERROR_RE.search(combined):
        return None
    message = _failure(stdout, stderr, "Pi rejected the copied runtime metadata")
    limit = 4_000
    return message if len(message) <= limit else f"{message[: limit - 3]}..."


def _json_has_sensitive_key(value: object) -> str | None:
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        for key, item in mapping.items():
            key_text = str(key)
            if _SENSITIVE_KEY_RE.search(key_text) and not (
                isinstance(item, str) and _ENV_REFERENCE_RE.fullmatch(item)
            ):
                return key_text
            nested = _json_has_sensitive_key(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in cast("list[object]", value):
            nested = _json_has_sensitive_key(item)
            if nested:
                return nested
    return None


def read_non_secret_json(path: Path, label: str) -> dict[str, object]:
    """Read JSON metadata while refusing fields that commonly contain secrets."""

    try:
        decoded = cast("object", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise PiwError(
            f"cannot read {label} file {path}: {error}",
            code=ExitCode.CONFIG,
            kind="invalid_metadata_file",
        ) from error
    if not isinstance(decoded, dict):
        raise PiwError(
            f"{label} file {path} must contain a JSON object",
            code=ExitCode.CONFIG,
            kind="invalid_metadata_file",
        )
    mapping = cast("dict[str, object]", decoded)
    sensitive_key = _json_has_sensitive_key(mapping)
    if sensitive_key:
        raise PiwError(
            f"refusing to copy {label} file {path}: field {sensitive_key!r} may contain a secret",
            code=ExitCode.CONFIG,
            kind="sensitive_metadata",
            hint="Move credentials to Pi authentication or the Docker Sandbox secret store.",
        )
    return mapping


class PiwService:
    """Coordinate host Git, Docker Sandboxes, Pi, and local state."""

    def __init__(
        self,
        config: AppConfig,
        runner: Runner,
        store: StateStore | None = None,
    ) -> None:
        """Initialize the service and its external adapters."""

        self.config = config
        self.runner = runner
        self.store = store or StateStore()
        self.git = GitClient(runner)
        self.sbx = SbxClient(runner)

    def _require_tools(self) -> None:
        missing = [command for command in ("git", "sbx") if self.runner.which(command) is None]
        if missing:
            raise PiwError(
                f"missing required executable(s): {', '.join(missing)}",
                code=ExitCode.PREREQUISITE,
                kind="missing_executable",
            )

    def _best_effort_remove(self, sandbox: str) -> None:
        """Remove a disposable sandbox without masking the primary failure."""

        with suppress(PiwError):
            self.sbx.remove(sandbox)

    @staticmethod
    def _require_paths(config: EffectiveTaskConfig) -> None:
        directories = (*config.read_only_refs, *config.skill_paths)
        missing_directories = [str(path) for path in directories if not path.is_dir()]
        if missing_directories:
            raise PiwError(
                f"configured read-only directories do not exist: {', '.join(missing_directories)}",
                code=ExitCode.CONFIG,
                kind="missing_configured_path",
            )
        files = tuple(path for path in (config.models_file, config.settings_file) if path)
        missing_files = [str(path) for path in files if not path.is_file()]
        if missing_files:
            raise PiwError(
                f"configured metadata files do not exist: {', '.join(missing_files)}",
                code=ExitCode.CONFIG,
                kind="missing_configured_path",
            )

    def effective_task_config(
        self,
        *,
        repo_candidate: Path,
        base_ref: str | None = None,
        branch: str | None = None,
        refs: tuple[Path, ...] = (),
        skills: tuple[Path, ...] = (),
        model: str | None = None,
        thinking: ThinkingLevel | None = None,
        mcp_servers: tuple[str, ...] = (),
        profile: str | None = None,
        extensions: tuple[str, ...] = (),
        models_file: Path | None = None,
        settings_file: Path | None = None,
        timeout_seconds: int | None = None,
        task: str,
    ) -> EffectiveTaskConfig:
        """Resolve configuration and CLI overrides for one task."""

        repo = self.git.root(repo_candidate)
        clean_refs = tuple(dict.fromkeys((*self.config.sandbox.read_only_refs, *refs)))
        clean_skills = tuple(dict.fromkeys((*self.config.pi.skill_paths, *skills)))
        clean_mcp = tuple(dict.fromkeys((*self.config.sandbox.mcp_servers, *mcp_servers)))
        clean_extensions = tuple(dict.fromkeys((*self.config.pi.extensions, *extensions)))
        selected_base = base_ref or "HEAD"
        selected_branch = branch or f"piw/{normalize_task_name(task)}"
        if not self.git.is_valid_branch(repo, selected_branch):
            raise PiwError(
                f"Git does not accept branch name {selected_branch!r}",
                code=ExitCode.USAGE,
                kind="invalid_branch",
            )
        effective = EffectiveTaskConfig(
            repo=repo,
            base_ref=selected_base,
            branch=selected_branch,
            read_only_refs=clean_refs,
            skill_paths=clean_skills,
            model=model if model is not None else self.config.pi.model,
            thinking=thinking or self.config.pi.thinking,
            mcp_servers=clean_mcp,
            profile=profile if profile is not None else self.config.sandbox.profile,
            extensions=clean_extensions,
            models_file=models_file or self.config.pi.models_file,
            settings_file=settings_file or self.config.pi.settings_file,
            cpus=self.config.sandbox.cpus,
            memory=self.config.sandbox.memory,
            timeout_seconds=timeout_seconds or self.config.sandbox.timeout_seconds,
        )
        self._require_paths(effective)
        return effective

    def config_for_extensions(self, extensions: tuple[str, ...]) -> AppConfig:
        """Return a config whose template inputs include CLI extensions."""

        return replace(self.config, pi=replace(self.config.pi, extensions=extensions))

    def template_status(self, extensions: tuple[str, ...] | None = None) -> dict[str, object]:
        """Report whether the desired reusable template is installed."""

        template_config = self.config_for_extensions(extensions or self.config.pi.extensions)
        desired = desired_template(template_config)
        installed = self.sbx.has_template(desired)
        return {
            "desired": desired,
            "installed": installed,
            "pi_package": template_config.pi.package,
            "node_version": template_config.template.node_version,
            "extensions": list(template_config.pi.extensions),
        }

    def ensure_template(
        self,
        *,
        extensions: tuple[str, ...] | None = None,
        profile: str | None = None,
        force: bool = False,
        dry_run: bool = False,
        timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        """Build the desired reusable template when necessary."""

        self._require_tools()
        template_config = self.config_for_extensions(extensions or self.config.pi.extensions)
        desired = desired_template(template_config)
        installed = self.sbx.has_template(desired)
        if installed and not force:
            unchanged: dict[str, object] = {
                "template": desired,
                "action": "unchanged",
                "installed": True,
            }
            return unchanged
        timeout = timeout_seconds or self.config.sandbox.timeout_seconds
        bootstrap = f"piw-template-{hashlib.sha256(desired.encode()).hexdigest()[:10]}"
        workspace = cache_home() / "bootstrap-workspace"
        preview: dict[str, object] = {
            "template": desired,
            "bootstrap_sandbox": bootstrap,
            "workspace": str(workspace),
            "action": "rebuild" if installed else "build",
            "installed": installed,
        }
        if dry_run:
            return preview

        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        existing_names = {sandbox.name for sandbox in self.sbx.list_sandboxes()}
        if bootstrap in existing_names:
            self.sbx.remove(bootstrap)
        try:
            self.sbx.create_bootstrap(
                name=bootstrap,
                workspace=workspace,
                profile=profile if profile is not None else self.config.sandbox.profile,
                timeout_seconds=timeout,
            )
            command = (
                "bash",
                "-s",
                "--",
                template_config.template.node_version,
                template_config.pi.package,
                *template_config.pi.extensions,
            )
            result = self.sbx.exec(
                bootstrap,
                command,
                input_text=_BOOTSTRAP_SCRIPT,
                timeout_seconds=timeout,
            )
            if result.returncode != 0:
                raise PiwError(
                    _failure(result.stdout, result.stderr, "template bootstrap failed"),
                    code=ExitCode.SANDBOX,
                    kind="template_bootstrap_failed",
                )
            self.sbx.stop(bootstrap)
            if installed:
                self.sbx.remove_template(desired)
            self.sbx.save_template(bootstrap, desired, timeout_seconds=timeout)
        finally:
            self._best_effort_remove(bootstrap)
        return {**preview, "installed": True}

    def prune_templates(self, *, dry_run: bool) -> dict[str, object]:
        """Remove obsolete piw-owned templates not referenced by task state."""

        prefix = f"{self.config.template.prefix}-"
        referenced = {record.template for record in self.store.list()}
        referenced.add(desired_template(self.config))
        obsolete = tuple(
            template.reference
            for template in self.sbx.list_templates()
            if template.reference.startswith(prefix) and template.reference not in referenced
        )
        if not dry_run:
            for reference in obsolete:
                self.sbx.remove_template(reference)
        return {"removed": [] if dry_run else list(obsolete), "would_remove": list(obsolete)}

    def _write_sandbox_file(self, sandbox: str, filename: str, value: object) -> None:
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        script = f'umask 077; mkdir -p "$HOME/.pi/agent"; cat > "$HOME/.pi/agent/{filename}"'
        result = self.sbx.exec(
            sandbox,
            ("sh", "-lc", script),
            input_text=payload,
            timeout_seconds=60,
        )
        if result.returncode != 0:
            raise PiwError(
                _failure(result.stdout, result.stderr, f"failed to seed {filename}"),
                code=ExitCode.SANDBOX,
                kind="config_seed_failed",
            )

    def _seed_pi_config(
        self,
        sandbox: str,
        *,
        models_file: Path | None,
        settings_file: Path | None,
        mcp_servers: tuple[str, ...],
    ) -> None:
        if models_file:
            models = read_non_secret_json(models_file, "models")
            self._write_sandbox_file(sandbox, "models.json", models)
        if settings_file:
            settings = read_non_secret_json(settings_file, "settings")
            existing_result = self.sbx.exec(
                sandbox,
                ("sh", "-lc", 'cat "$HOME/.pi/agent/settings.json" 2>/dev/null || printf "{}"'),
                timeout_seconds=30,
            )
            try:
                existing = cast(
                    "object",
                    json.loads(existing_result.stdout) if existing_result.returncode == 0 else {},
                )
            except json.JSONDecodeError:
                existing = {}
            if isinstance(existing, dict):
                existing_mapping = cast("dict[str, object]", existing)
                existing_packages = existing_mapping.get("packages", [])
                supplied_packages = settings.get("packages", [])
                merged_packages: list[object] = []
                for packages in (existing_packages, supplied_packages):
                    if isinstance(packages, list):
                        merged_packages.extend(cast("list[object]", packages))
                unique_packages: dict[str, object] = {}
                for package in merged_packages:
                    unique_packages[json.dumps(package, sort_keys=True)] = package
                settings["packages"] = list(unique_packages.values())
            self._write_sandbox_file(sandbox, "settings.json", settings)
        if mcp_servers:
            gateway = {
                "mcpServers": {
                    "sandbox-gateway": {
                        "transport": "streamable-http",
                        "url": self.config.sandbox.mcp_gateway_url,
                        "lifecycle": "eager",
                    }
                }
            }
            self._write_sandbox_file(sandbox, "mcp.json", gateway)

    def _validate_pi_config(self, sandbox: str, task_config: EffectiveTaskConfig) -> None:
        """Ask the installed Pi version to validate copied runtime metadata."""

        if not task_config.models_file and not task_config.settings_file:
            return
        result = self.sbx.exec(
            sandbox,
            ("pi", "--list-models"),
            workdir=task_config.repo,
            timeout_seconds=60,
        )
        failure = _pi_metadata_failure(result.returncode, result.stdout, result.stderr)
        if failure:
            raise PiwError(
                failure,
                code=ExitCode.CONFIG,
                kind="invalid_pi_metadata",
                hint="Fix the configured models/settings file, then retry the task.",
            )

    def _pi_command(self, record: TaskRecord, *, resume: bool) -> tuple[str, ...]:
        argv = ["pi"]
        if resume:
            argv.append("--continue")
        else:
            argv.extend(("--name", record.task))
        if record.model:
            argv.extend(("--model", record.model))
        argv.extend(("--thinking", record.thinking))
        for skill in record.skill_paths:
            argv.extend(("--skill", skill))
        return tuple(argv)

    def _attach_pi(self, record: TaskRecord, *, resume: bool) -> None:
        result = self.sbx.exec(
            record.sandbox,
            self._pi_command(record, resume=resume),
            workdir=Path(record.repo),
            interactive=True,
        )
        if result.returncode != 0:
            raise PiwError(
                f"Pi exited with status {result.returncode}",
                code=ExitCode.SANDBOX,
                kind="pi_failed",
            )

    def start(
        self,
        *,
        task: str,
        task_config: EffectiveTaskConfig,
        batch: bool,
        dry_run: bool,
    ) -> dict[str, object]:
        """Create a private task clone and optionally attach Pi."""

        self._require_tools()
        normalized = normalize_task_name(task)
        if self.store.exists(normalized):
            raise PiwError(
                f"task {normalized!r} already exists",
                code=ExitCode.TASK,
                kind="task_exists",
                hint=f"Use 'piw resume {normalized}'.",
            )
        if not self.git.is_clean(task_config.repo):
            raise PiwError(
                f"host repository {task_config.repo} has uncommitted or untracked changes",
                code=ExitCode.UNSAFE,
                kind="dirty_host_repository",
                hint="Commit, stash, or remove the changes before creating a private clone.",
            )
        base_commit = self.git.resolve_ref(task_config.repo, task_config.base_ref)
        name = sandbox_name(normalized, task_config.repo)
        template_config = self.config_for_extensions(task_config.extensions)
        template = desired_template(template_config)
        exposure = read_only_exposure(
            task_config.repo,
            task_config.read_only_refs,
            task_config.skill_paths,
        )
        preview: dict[str, object] = {
            "task": normalized,
            "sandbox": name,
            "repo": str(task_config.repo),
            "base_ref": task_config.base_ref,
            "base_commit": base_commit,
            "branch": task_config.branch,
            "template": template,
            "read_only_refs": [str(path) for path in task_config.read_only_refs],
            "skill_paths": [str(path) for path in task_config.skill_paths],
            "sandbox_mounts": [str(path) for path in exposure.mounts],
            "sandbox_snapshots": [str(path) for path in exposure.snapshots],
            "mcp_servers": list(task_config.mcp_servers),
            "profile": task_config.profile,
            "cpus": task_config.cpus,
            "memory": task_config.memory,
            "model": task_config.model,
            "thinking": task_config.thinking.value,
            "batch": batch,
        }
        if dry_run:
            preview["template_action"] = self.ensure_template(
                extensions=task_config.extensions,
                dry_run=True,
                timeout_seconds=task_config.timeout_seconds,
            )["action"]
            preview["action"] = "create"
            return preview

        capabilities = self.sbx.capabilities()
        required = {"--clone"}
        if task_config.profile:
            required.add("--profile")
        if task_config.mcp_servers:
            required.add("--static-mcp")
        missing = sorted(required - capabilities)
        if missing:
            raise PiwError(
                f"installed sbx lacks required creation flag(s): {', '.join(missing)}",
                code=ExitCode.PREREQUISITE,
                kind="unsupported_sbx",
            )
        registered = [
            server for server in task_config.mcp_servers if not self.sbx.inspect_mcp(server)
        ]
        if registered:
            raise PiwError(
                f"Docker Sandbox MCP server(s) are not registered: {', '.join(registered)}",
                code=ExitCode.PREREQUISITE,
                kind="missing_mcp_registration",
                hint="Register and authorize them with 'sbx mcp add' and 'sbx mcp auth'.",
            )
        self.ensure_template(
            extensions=task_config.extensions,
            profile=task_config.profile,
            timeout_seconds=task_config.timeout_seconds,
        )
        if any(sandbox.name == name for sandbox in self.sbx.list_sandboxes()):
            raise PiwError(
                f"sandbox {name!r} already exists but is not owned by task state",
                code=ExitCode.TASK,
                kind="sandbox_name_conflict",
            )

        saved = False
        try:
            self.sbx.create(
                name=name,
                task_config=task_config,
                template=template,
                timeout_seconds=task_config.timeout_seconds,
            )
            switch = self.sbx.exec(
                name,
                ("git", "switch", "--create", task_config.branch, base_commit),
                workdir=task_config.repo,
                timeout_seconds=60,
            )
            if switch.returncode != 0:
                raise PiwError(
                    _failure(switch.stdout, switch.stderr, "cannot create task branch"),
                    code=ExitCode.SANDBOX,
                    kind="branch_create_failed",
                )
            self._seed_pi_config(
                name,
                models_file=task_config.models_file,
                settings_file=task_config.settings_file,
                mcp_servers=task_config.mcp_servers,
            )
            self._validate_pi_config(name, task_config)
            timestamp = utc_now()
            record = TaskRecord(
                schema_version=1,
                task=normalized,
                sandbox=name,
                repo=str(task_config.repo),
                branch=task_config.branch,
                base_commit=base_commit,
                template=template,
                model=task_config.model,
                thinking=task_config.thinking.value,
                mcp_servers=task_config.mcp_servers,
                read_only_refs=tuple(str(path) for path in task_config.read_only_refs),
                skill_paths=tuple(str(path) for path in task_config.skill_paths),
                profile=task_config.profile,
                created_at=timestamp,
                last_used_at=timestamp,
                session_started=False,
            )
            self.store.save(record)
            saved = True
            if not batch:
                self._attach_pi(record, resume=False)
                self.store.save(replace(record, last_used_at=utc_now(), session_started=True))
        finally:
            if not saved:
                self._best_effort_remove(name)
        return {**preview, "action": "created"}

    def resume(self, task: str, *, timeout_seconds: int = 120) -> dict[str, object]:
        """Resume the most recent Pi session in a task sandbox."""

        record = self.store.load(normalize_task_name(task))
        sandbox = self._sandbox_for(record)
        if sandbox.status == TaskPhase.STOPPED:
            wake = self.sbx.exec(
                record.sandbox,
                ("true",),
                workdir=Path(record.repo),
                timeout_seconds=timeout_seconds,
            )
            if wake.returncode != 0:
                raise PiwError(
                    _failure(wake.stdout, wake.stderr, "cannot restart sandbox"),
                    code=ExitCode.SANDBOX,
                    kind="sandbox_start_failed",
                )
        self._attach_pi(record, resume=record.session_started)
        updated = replace(record, last_used_at=utc_now(), session_started=True)
        self.store.save(updated)
        return {
            "task": record.task,
            "sandbox": record.sandbox,
            "previous_status": sandbox.status.value,
        }

    def _sandbox_for(self, record: TaskRecord) -> SandboxInfo:
        sandboxes = {sandbox.name: sandbox for sandbox in self.sbx.list_sandboxes()}
        sandbox = sandboxes.get(record.sandbox)
        if not sandbox:
            raise PiwError(
                f"sandbox {record.sandbox!r} for task {record.task!r} is missing",
                code=ExitCode.STATE,
                kind="missing_sandbox",
                hint=f"The host recovery remote is 'sandbox-{record.sandbox}'.",
            )
        return sandbox

    def list_tasks(self) -> list[dict[str, object]]:
        """Return all task records reconciled with live sandbox state."""

        sandboxes = {sandbox.name: sandbox for sandbox in self.sbx.list_sandboxes()}
        output: list[dict[str, object]] = []
        for record in self.store.list():
            sandbox = sandboxes.get(record.sandbox)
            output.append(
                {
                    "task": record.task,
                    "sandbox": record.sandbox,
                    "status": sandbox.status.value if sandbox else TaskPhase.MISSING.value,
                    "repo": record.repo,
                    "branch": record.branch,
                    "model": record.model,
                    "created_at": record.created_at,
                    "last_used_at": record.last_used_at,
                }
            )
        return output

    def _git_safety(self, record: TaskRecord) -> dict[str, object]:
        status = self.sbx.exec(
            record.sandbox,
            ("git", "status", "--porcelain=v1", "--untracked-files=all"),
            workdir=Path(record.repo),
            timeout_seconds=60,
        )
        if status.returncode != 0:
            raise PiwError(
                _failure(status.stdout, status.stderr, "cannot inspect sandbox Git status"),
                code=ExitCode.SANDBOX,
                kind="sandbox_git_failed",
            )
        dirty = bool(status.stdout.strip())
        head = self.sbx.exec(
            record.sandbox,
            ("git", "rev-parse", "HEAD"),
            workdir=Path(record.repo),
            timeout_seconds=60,
        )
        head_commit = head.stdout.strip()
        if head.returncode != 0 or not head_commit:
            raise PiwError(
                _failure(head.stdout, head.stderr, "cannot inspect sandbox Git HEAD"),
                code=ExitCode.SANDBOX,
                kind="sandbox_git_failed",
            )
        upstream = self.sbx.exec(
            record.sandbox,
            ("git", "rev-parse", "--verify", "@{upstream}"),
            workdir=Path(record.repo),
            timeout_seconds=60,
        )
        ahead = 0
        if upstream.returncode == 0:
            count = self.sbx.exec(
                record.sandbox,
                ("git", "rev-list", "--count", "@{upstream}..HEAD"),
                workdir=Path(record.repo),
                timeout_seconds=60,
            )
            count_text = count.stdout.strip()
            if count.returncode != 0 or not count_text.isdigit():
                raise PiwError(
                    _failure(
                        count.stdout,
                        count.stderr,
                        "cannot count commits not present on the upstream branch",
                    ),
                    code=ExitCode.SANDBOX,
                    kind="sandbox_git_failed",
                )
            ahead = int(count_text)
        unchanged = head_commit == record.base_commit
        safe = not dirty and (unchanged or (upstream.returncode == 0 and ahead == 0))
        return {
            "dirty": dirty,
            "head": head_commit,
            "unchanged": unchanged,
            "has_upstream": upstream.returncode == 0,
            "unpushed_commits": ahead,
            "safe_to_clean": safe,
        }

    def status(self, task: str) -> dict[str, object]:
        """Return detailed task and safe-cleanup status."""

        record = self.store.load(normalize_task_name(task))
        sandbox = self._sandbox_for(record)
        safety: dict[str, object] | None = None
        if sandbox.status == TaskPhase.RUNNING:
            safety = self._git_safety(record)
        return {
            **record.to_json_object(),
            "status": sandbox.status.value,
            "git": safety,
            "git_inspection_deferred": safety is None,
            "recovery_remote": f"sandbox-{record.sandbox}",
        }

    def shell(self, task: str, cwd: Path | None = None) -> None:
        """Open an interactive shell in a task sandbox."""

        record = self.store.load(normalize_task_name(task))
        self._sandbox_for(record)
        result = self.sbx.exec(
            record.sandbox,
            ("bash",),
            workdir=cwd or Path(record.repo),
            interactive=True,
        )
        if result.returncode != 0:
            raise PiwError(
                f"sandbox shell exited with status {result.returncode}",
                code=ExitCode.SANDBOX,
                kind="shell_failed",
            )

    def execute(
        self, task: str, command: tuple[str, ...], cwd: Path | None = None
    ) -> dict[str, object]:
        """Execute one captured command inside a task sandbox."""

        if not command:
            raise PiwError(
                "piw exec requires a command after '--'",
                code=ExitCode.USAGE,
                kind="missing_command",
            )
        record = self.store.load(normalize_task_name(task))
        self._sandbox_for(record)
        result = self.sbx.exec(
            record.sandbox,
            command,
            workdir=cwd or Path(record.repo),
        )
        return {
            "task": record.task,
            "command": render_command(command),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": result.duration_seconds,
        }

    def stop(self, task: str, *, dry_run: bool) -> dict[str, object]:
        """Stop one task sandbox without removing it."""

        record = self.store.load(normalize_task_name(task))
        sandbox = self._sandbox_for(record)
        if not dry_run and sandbox.status == TaskPhase.RUNNING:
            self.sbx.stop(record.sandbox)
        return {
            "task": record.task,
            "sandbox": record.sandbox,
            "previous_status": sandbox.status.value,
            "action": "would_stop" if dry_run else "stopped",
        }

    def clean(self, task: str, *, dry_run: bool, force: bool) -> dict[str, object]:
        """Safely remove a task sandbox and its local record."""

        record = self.store.load(normalize_task_name(task))
        sandbox = self._sandbox_for(record)
        if dry_run and sandbox.status == TaskPhase.STOPPED:
            return {
                "task": record.task,
                "sandbox": record.sandbox,
                "previous_status": sandbox.status.value,
                "safety": None,
                "safety_inspection_deferred": True,
                "action": "would_inspect_then_remove",
            }
        safety = self._git_safety(record)
        if not bool(safety["safe_to_clean"]) and not force:
            raise PiwError(
                f"task {record.task!r} has dirty or unpushed work",
                code=ExitCode.UNSAFE,
                kind="unsafe_cleanup",
                hint=f"Inspect it with 'piw status {record.task}' or use --force to discard it.",
            )
        if not dry_run:
            self.sbx.remove(record.sandbox)
            self.store.delete(record.task)
        return {
            "task": record.task,
            "sandbox": record.sandbox,
            "previous_status": sandbox.status.value,
            "safety": safety,
            "action": "would_remove" if dry_run else "removed",
        }

    def doctor(self, *, live: bool, timeout_seconds: int) -> list[DoctorCheck]:
        """Run prerequisite checks and an optional disposable sandbox probe."""

        checks: list[DoctorCheck] = []
        for command in ("git", "sbx", "uv"):
            executable = self.runner.which(command)
            checks.append(
                DoctorCheck(
                    name=command,
                    status="pass" if executable else "fail",
                    message=executable or f"{command} is not on PATH",
                )
            )
        if self.runner.which("sbx"):
            version = self.sbx.version()
            checks.append(
                DoctorCheck(
                    name="sbx-version",
                    status="pass" if version.returncode == 0 else "fail",
                    message=(version.stdout or version.stderr).strip(),
                )
            )
            try:
                capabilities = self.sbx.capabilities()
                missing = {"--clone", "--profile", "--static-mcp"} - capabilities
                checks.append(
                    DoctorCheck(
                        name="sbx-capabilities",
                        status="warn" if missing else "pass",
                        message=f"available: {', '.join(sorted(capabilities))}",
                        hint=f"missing optional flags: {', '.join(sorted(missing))}"
                        if missing
                        else None,
                    )
                )
                self.sbx.list_sandboxes()
                checks.append(DoctorCheck("sbx-daemon", "pass", "sandbox daemon responded"))
            except PiwError as error:
                checks.append(DoctorCheck("sbx-daemon", "fail", str(error)))

        socket = os.environ.get("SSH_AUTH_SOCK")
        socket_ok = bool(socket and Path(socket).exists())
        checks.append(
            DoctorCheck(
                name="ssh-agent",
                status="pass" if socket_ok else "warn",
                message=socket if socket_ok and socket else "SSH_AUTH_SOCK is unavailable",
                hint="Load an SSH key on the host before publishing from a sandbox."
                if not socket_ok
                else None,
            )
        )
        for label, paths in (
            ("reference", self.config.sandbox.read_only_refs),
            ("skill", self.config.pi.skill_paths),
        ):
            checks.extend(
                DoctorCheck(
                    name=f"{label}-path",
                    status="pass" if path.is_dir() else "fail",
                    message=str(path),
                )
                for path in paths
            )
        for label, path in (
            ("models-file", self.config.pi.models_file),
            ("settings-file", self.config.pi.settings_file),
        ):
            if path:
                if not path.is_file():
                    checks.append(DoctorCheck(label, "fail", str(path)))
                    continue
                try:
                    read_non_secret_json(path, label.removesuffix("-file"))
                    checks.append(DoctorCheck(label, "pass", str(path)))
                except PiwError as error:
                    checks.append(DoctorCheck(label, "fail", str(error)))
        if self.runner.which("sbx"):
            for server in self.config.sandbox.mcp_servers:
                registered = self.sbx.inspect_mcp(server)
                checks.append(
                    DoctorCheck(
                        name=f"mcp:{server}",
                        status="pass" if registered else "fail",
                        message="registered" if registered else "not registered",
                        hint=f"Run 'sbx mcp add {server} ...' then authorize it."
                        if not registered
                        else None,
                    )
                )
            try:
                status = self.template_status()
                checks.append(
                    DoctorCheck(
                        name="pi-template",
                        status="pass" if bool(status["installed"]) else "warn",
                        message=str(status["desired"]),
                        hint="Run 'piw template ensure'."
                        if not bool(status["installed"])
                        else None,
                    )
                )
            except PiwError as error:
                checks.append(DoctorCheck("pi-template", "fail", str(error)))
        if live:
            checks.append(self._live_doctor_probe(timeout_seconds))
        return checks

    def _live_doctor_probe(self, timeout_seconds: int) -> DoctorCheck:
        probe = f"piw-doctor-{os.getpid()}"
        workspace = cache_home() / "doctor-workspace"
        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            template = desired_template(self.config)
            if not self.sbx.has_template(template):
                return DoctorCheck(
                    "live-sandbox",
                    "fail",
                    f"required template is not installed: {template}",
                    "Run 'piw template ensure' before the live probe.",
                )
            self.sbx.create_bootstrap(
                name=probe,
                workspace=workspace,
                profile=self.config.sandbox.profile,
                template=template,
                timeout_seconds=timeout_seconds,
            )
            result = self.sbx.exec(
                probe,
                ("sh", "-lc", "test -w . && curl -fsSI https://registry.npmjs.org >/dev/null"),
                workdir=workspace,
                timeout_seconds=timeout_seconds,
            )
            if result.returncode == 0:
                self._seed_pi_config(
                    probe,
                    models_file=self.config.pi.models_file,
                    settings_file=self.config.pi.settings_file,
                    mcp_servers=(),
                )
                if self.config.pi.models_file or self.config.pi.settings_file:
                    metadata = self.sbx.exec(
                        probe,
                        ("pi", "--list-models"),
                        workdir=workspace,
                        timeout_seconds=timeout_seconds,
                    )
                    failure = _pi_metadata_failure(
                        metadata.returncode,
                        metadata.stdout,
                        metadata.stderr,
                    )
                    if failure:
                        return DoctorCheck(
                            "live-sandbox",
                            "fail",
                            failure,
                        )
                return DoctorCheck(
                    "live-sandbox",
                    "pass",
                    "create, write, network, and Pi metadata probes passed",
                )
            return DoctorCheck(
                "live-sandbox",
                "fail",
                _failure(result.stdout, result.stderr, "live probe failed"),
            )
        except PiwError as error:
            return DoctorCheck("live-sandbox", "fail", str(error))
        finally:
            self._best_effort_remove(probe)
