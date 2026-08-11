"""Application services for sessions, templates, and diagnostics."""

import hashlib
import json
import os
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Final, cast

from piw.config import cache_home, state_home
from piw.errors import ExitCode, PiwError
from piw.git import GitClient, HostPatch, HostStatus
from piw.models import (
    AppConfig,
    DoctorCheck,
    EffectiveBranchConfig,
    EffectiveSessionConfig,
    HostChangesPolicy,
    SandboxPhase,
    SandboxSecretConfig,
    SecretRecord,
    SessionKind,
    SessionRecord,
    ThinkingLevel,
)
from piw.process import Runner, render_command
from piw.sandbox import (
    ReadOnlyExposure,
    SandboxInfo,
    SbxClient,
    desired_template,
    read_only_exposure,
)
from piw.state import SecretStateStore, StateStore

_SESSION_TOKEN_RE: Final = re.compile(r"[^a-z0-9]+")
_SENSITIVE_KEY_RE: Final = re.compile(
    r"(?:api[-_]?key|private[-_]?key|(?:^|[-_])(?:access|authorization|bearer|cookie|"
    r"credential|password|refresh|secret|token)(?:$|[-_]))",
    re.IGNORECASE,
)
_ENV_REFERENCE_RE: Final = re.compile(r"\$(?:[A-Z_][A-Z0-9_]*|\{[A-Z_][A-Z0-9_]*\})")
_PI_CONFIG_ERROR_RE: Final = re.compile(
    r"(?:errors? loading (?:models|settings|mcp)\.json|(?:models|settings|mcp)\.json[^\n]*error)",
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


def normalize_session_name(value: str) -> str:
    """Normalize a user-facing session label into a stable identifier."""

    normalized = _SESSION_TOKEN_RE.sub("-", value.strip().lower()).strip("-")
    normalized = normalized[:63].rstrip("-")
    if not normalized:
        raise PiwError(
            "session name must contain at least one letter or number",
            code=ExitCode.USAGE,
            kind="invalid_session_name",
        )
    return normalized


def branch_sandbox_name(name: str, repo: Path) -> str:
    """Return a readable, collision-resistant branch sandbox name."""

    repo_slug = normalize_session_name(repo.name)[:24]
    name_slug = normalize_session_name(name)[:24]
    digest = hashlib.sha256(str(repo).encode()).hexdigest()[:8]
    return f"piw-{repo_slug}-{name_slug}-{digest}"[:63].rstrip("-")


def chat_sandbox_name(name: str, *, temporary: bool) -> str:
    """Return a stable persistent or unique temporary chat sandbox name."""

    normalized = normalize_session_name(name)
    suffix = (
        token_urlsafe(6).lower().replace("_", "-")
        if temporary
        else hashlib.sha256(normalized.encode()).hexdigest()[:8]
    )
    return f"piw-chat-{normalized[:32]}-{suffix}"[:63].rstrip("-")


def _persistent_chat_workspace(name: str) -> Path:
    """Return the piw-owned state directory for one persistent chat."""

    return (state_home() / "chats" / normalize_session_name(name)).resolve(strict=False)


def utc_now() -> str:
    """Return an RFC 3339 UTC timestamp."""

    return datetime.now(tz=UTC).isoformat()


def _failure(result_stdout: str, result_stderr: str, fallback: str) -> str:
    """Choose the most useful available message from failed command output."""

    return result_stderr.strip() or result_stdout.strip() or fallback


def _pi_metadata_failure(returncode: int, stdout: str, stderr: str) -> str | None:
    """Extract a bounded error message when Pi rejects runtime metadata."""

    combined = "\n".join(part for part in (stderr, stdout) if part)
    if returncode == 0 and not _PI_CONFIG_ERROR_RE.search(combined):
        return None
    message = _failure(stdout, stderr, "Pi rejected the copied runtime metadata")
    limit = 4_000
    return message if len(message) <= limit else f"{message[: limit - 3]}..."


def _json_has_sensitive_key(value: object) -> str | None:
    """Find the first JSON key that appears to contain an inline secret."""

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


@dataclass(frozen=True, slots=True)
class _SecretPlan:
    """Internal plan that keeps secret values separate from public output."""

    declaration: SandboxSecretConfig
    record: SecretRecord | None
    environment_value: str | None
    fingerprint: str | None
    registered: bool
    action: str
    reason: str


@dataclass(frozen=True, slots=True)
class _BranchPlan:
    """Resolved host and sandbox inputs for one Git-backed session."""

    name: str
    sandbox: str
    base_commit: str
    template: str
    exposure: ReadOnlyExposure
    host_status: HostStatus
    host_patch: HostPatch | None


@dataclass(frozen=True, slots=True)
class _ChatPlan:
    """Resolved identity and resources for one persistent or temporary chat."""

    name: str
    sandbox: str
    workspace: Path
    template: str
    exposure: ReadOnlyExposure
    temporary: bool


@dataclass(frozen=True, slots=True)
class _PiLaunch:
    """Inputs needed to attach one interactive Pi process."""

    sandbox: str
    workdir: Path
    name: str
    model: str | None
    thinking: str
    skill_paths: tuple[str, ...]


class PiwService:
    """Coordinate host Git, Docker Sandboxes, Pi, and local state."""

    def __init__(
        self,
        config: AppConfig,
        runner: Runner,
        store: StateStore | None = None,
        secret_store: SecretStateStore | None = None,
    ) -> None:
        """Initialize the service and its external adapters."""

        self.config = config
        self.runner = runner
        self.store = store or StateStore()
        self.secret_store = secret_store or SecretStateStore()
        self.git = GitClient(runner)
        self.sbx = SbxClient(runner)

    def _require_tools(self, *commands: str) -> None:
        """Verify that the requested host executables are available."""

        missing = [command for command in commands if self.runner.which(command) is None]
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
    def _secret_fingerprint(value: str) -> str:
        """Return a domain-separated fingerprint for a high-entropy credential."""

        return hashlib.sha256(f"piw-secret-v1\0{value}".encode()).hexdigest()

    @staticmethod
    def _secret_record_matches(
        declaration: SandboxSecretConfig,
        record: SecretRecord,
    ) -> bool:
        """Check whether stored secret metadata matches its current declaration."""

        return (
            declaration.source_env == record.source_env
            and declaration.sandbox_env == record.sandbox_env
            and declaration.hosts == record.hosts
            and declaration.placeholder == record.placeholder_template
        )

    @classmethod
    def _secret_plan_action(
        cls,
        declaration: SandboxSecretConfig,
        record: SecretRecord | None,
        *,
        fingerprint: str | None,
        registered: bool,
        force: bool,
    ) -> tuple[str, str]:
        """Classify the next action for one declared sandbox secret."""

        configured = bool(record and registered and cls._secret_record_matches(declaration, record))
        if (
            configured
            and not force
            and (fingerprint is None or (record is not None and fingerprint == record.fingerprint))
        ):
            reason = (
                "registered; source environment is not needed until rotation"
                if fingerprint is None
                else "registered and fingerprint matches"
            )
            return "unchanged", reason

        if fingerprint is None:
            reason = (
                f"host environment variable {declaration.source_env} is unavailable"
                if record is None
                else "stored mapping cannot be reconciled without the source environment"
            )
            return ("missing" if declaration.required else "skip"), reason

        if record is None:
            return "create", "no piw-managed mapping is registered"
        if not registered and cls._secret_record_matches(declaration, record):
            return "restore", "stored mapping is absent from Docker Sandboxes"
        return "update", "value or declaration changed"

    def _secret_plans(self, *, force: bool) -> tuple[_SecretPlan, ...]:
        """Plan required secret-store changes without exposing secret values."""

        declarations = self.config.sandbox.secrets
        if not declarations:
            return ()

        if self.runner.which("sbx") is None:
            raise PiwError(
                "missing required executable: sbx",
                code=ExitCode.PREREQUISITE,
                kind="missing_executable",
            )

        inventory = self.sbx.list_global_secrets()
        records = {record.sandbox_env: record for record in self.secret_store.load()}
        plans: list[_SecretPlan] = []

        for declaration in declarations:
            record = records.get(declaration.sandbox_env)
            value = os.environ.get(declaration.source_env)
            if value == "":
                value = None

            fingerprint = self._secret_fingerprint(value) if value is not None else None
            registered = bool(record and record.placeholder in inventory)
            action, reason = self._secret_plan_action(
                declaration,
                record,
                fingerprint=fingerprint,
                registered=registered,
                force=force,
            )
            plans.append(
                _SecretPlan(
                    declaration=declaration,
                    record=record,
                    environment_value=value,
                    fingerprint=fingerprint,
                    registered=registered,
                    action=action,
                    reason=reason,
                )
            )

        return tuple(plans)

    @staticmethod
    def _secret_plan_object(
        plan: _SecretPlan,
        *,
        action: str | None = None,
    ) -> dict[str, object]:
        """Convert an internal secret plan into redacted command output."""

        status = {
            "unchanged": "synced",
            "skip": "optional_unavailable",
            "missing": "missing",
            "create": "pending",
            "restore": "pending",
            "update": "pending",
            "created": "synced",
            "restored": "synced",
            "updated": "synced",
            "would_create": "pending",
            "would_restore": "pending",
            "would_update": "pending",
        }.get(action or plan.action, "unknown")

        return {
            "source_env": plan.declaration.source_env,
            "sandbox_env": plan.declaration.sandbox_env,
            "hosts": list(plan.declaration.hosts),
            "required": plan.declaration.required,
            "source_available": plan.environment_value is not None,
            "registered": plan.registered,
            "status": status,
            "action": action or plan.action,
            "placeholder": plan.record.placeholder if plan.record else "<generated>",
            "reason": plan.reason,
        }

    def secret_status(self) -> list[dict[str, object]]:
        """Report declared secret mappings without exposing credential values."""

        return [self._secret_plan_object(plan) for plan in self._secret_plans(force=False)]

    def sync_secrets(self, *, dry_run: bool, force: bool) -> list[dict[str, object]]:
        """Synchronize declared host variables through Docker's scoped secret store."""

        plans = self._secret_plans(force=force)
        missing = [
            plan.declaration.source_env
            for plan in plans
            if plan.action == "missing" and plan.declaration.required
        ]
        if missing:
            variables = ", ".join(missing)
            raise PiwError(
                f"required secret source environment variable(s) unavailable: {variables}",
                code=ExitCode.PREREQUISITE,
                kind="missing_secret_source",
                hint=f"Export {variables}, then run 'piw secrets sync'.",
            )

        if dry_run:
            return [
                self._secret_plan_object(
                    plan,
                    action=f"would_{plan.action}"
                    if plan.action in {"create", "restore", "update"}
                    else plan.action,
                )
                for plan in plans
            ]

        records = {record.sandbox_env: record for record in self.secret_store.load()}
        output: list[dict[str, object]] = []
        for plan in plans:
            if plan.action not in {"create", "restore", "update"}:
                output.append(self._secret_plan_object(plan))
                continue

            if plan.environment_value is None or plan.fingerprint is None:
                raise AssertionError("secret plan requiring synchronization has no source value")

            placeholder = (
                plan.record.placeholder
                if plan.record
                else plan.declaration.placeholder.replace("{rand}", token_urlsafe(18))
            )
            self.sbx.set_custom_secret(
                plan.declaration,
                placeholder=placeholder,
                value=plan.environment_value,
            )

            record = SecretRecord(
                schema_version=1,
                source_env=plan.declaration.source_env,
                sandbox_env=plan.declaration.sandbox_env,
                hosts=plan.declaration.hosts,
                placeholder_template=plan.declaration.placeholder,
                placeholder=placeholder,
                fingerprint=plan.fingerprint,
                synced_at=utc_now(),
            )
            records[record.sandbox_env] = record
            self.secret_store.save(tuple(records.values()))

            applied = {"create": "created", "restore": "restored", "update": "updated"}[plan.action]
            output.append(
                {
                    **self._secret_plan_object(plan, action=applied),
                    "registered": True,
                    "placeholder": placeholder,
                }
            )

        return output

    @staticmethod
    def _require_paths(config: EffectiveSessionConfig) -> None:
        """Verify that configured reference directories and metadata files exist."""

        directories = (*config.read_only_refs, *config.skill_paths)
        missing_directories = [str(path) for path in directories if not path.is_dir()]
        if missing_directories:
            raise PiwError(
                f"configured read-only directories do not exist: {', '.join(missing_directories)}",
                code=ExitCode.CONFIG,
                kind="missing_configured_path",
            )
        files = tuple(
            path for path in (config.models_file, config.settings_file, config.mcp_file) if path
        )
        missing_files = [str(path) for path in files if not path.is_file()]
        if missing_files:
            raise PiwError(
                f"configured metadata files do not exist: {', '.join(missing_files)}",
                code=ExitCode.CONFIG,
                kind="missing_configured_path",
            )

    def effective_session_config(
        self,
        *,
        refs: tuple[Path, ...] = (),
        skills: tuple[Path, ...] = (),
        model: str | None = None,
        thinking: ThinkingLevel | None = None,
        profile: str | None = None,
        extensions: tuple[str, ...] = (),
        models_file: Path | None = None,
        settings_file: Path | None = None,
        mcp_file: Path | None = None,
        timeout_seconds: int | None = None,
    ) -> EffectiveSessionConfig:
        """Resolve configuration and CLI overrides shared by every Pi session."""

        clean_refs = tuple(dict.fromkeys((*self.config.sandbox.read_only_refs, *refs)))
        clean_skills = tuple(dict.fromkeys((*self.config.pi.skill_paths, *skills)))
        clean_extensions = tuple(dict.fromkeys((*self.config.pi.extensions, *extensions)))

        effective = EffectiveSessionConfig(
            read_only_refs=clean_refs,
            skill_paths=clean_skills,
            model=model if model is not None else self.config.pi.model,
            thinking=thinking or self.config.pi.thinking,
            profile=profile if profile is not None else self.config.sandbox.profile,
            extensions=clean_extensions,
            models_file=models_file or self.config.pi.models_file,
            settings_file=settings_file or self.config.pi.settings_file,
            mcp_file=mcp_file or self.config.pi.mcp_file,
            cpus=self.config.sandbox.cpus,
            memory=self.config.sandbox.memory,
            timeout_seconds=timeout_seconds or self.config.sandbox.timeout_seconds,
        )

        self._require_paths(effective)
        return effective

    def effective_branch_config(
        self,
        *,
        session_config: EffectiveSessionConfig,
        repo_candidate: Path,
        base_ref: str | None = None,
        branch: str | None = None,
        name: str,
    ) -> EffectiveBranchConfig:
        """Resolve configuration and CLI overrides for one branch session."""

        repo = self.git.root(repo_candidate)
        selected_branch = branch or f"piw/{normalize_session_name(name)}"
        if not self.git.is_valid_branch(repo, selected_branch):
            raise PiwError(
                f"Git does not accept branch name {selected_branch!r}",
                code=ExitCode.USAGE,
                kind="invalid_branch",
            )

        return EffectiveBranchConfig(
            read_only_refs=session_config.read_only_refs,
            skill_paths=session_config.skill_paths,
            model=session_config.model,
            thinking=session_config.thinking,
            profile=session_config.profile,
            extensions=session_config.extensions,
            models_file=session_config.models_file,
            settings_file=session_config.settings_file,
            mcp_file=session_config.mcp_file,
            cpus=session_config.cpus,
            memory=session_config.memory,
            timeout_seconds=session_config.timeout_seconds,
            repo=repo,
            base_ref=base_ref or "HEAD",
            branch=selected_branch,
        )

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

        self._require_tools("sbx")
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
        """Remove obsolete piw-owned templates not referenced by session state."""

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
        """Write one JSON value into a sandbox's private Pi config directory."""

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

    def _seed_pi_settings(self, sandbox: str, settings_file: Path) -> None:
        """Merge supplied Pi settings with packages installed in the template."""

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
            package_lists = (existing_mapping.get("packages", []), settings.get("packages", []))
            merged_packages: list[object] = []

            for packages in package_lists:
                if isinstance(packages, list):
                    merged_packages.extend(cast("list[object]", packages))

            unique_packages = {
                json.dumps(package, sort_keys=True): package for package in merged_packages
            }
            settings["packages"] = list(unique_packages.values())

        self._write_sandbox_file(sandbox, "settings.json", settings)

    def _seed_pi_config(
        self,
        sandbox: str,
        *,
        models_file: Path | None,
        settings_file: Path | None,
        mcp_file: Path | None,
    ) -> None:
        """Copy configured models, settings, and MCP metadata into a sandbox."""

        if models_file:
            models = read_non_secret_json(models_file, "models")
            self._write_sandbox_file(sandbox, "models.json", models)

        if settings_file:
            self._seed_pi_settings(sandbox, settings_file)

        if mcp_file:
            mcp = read_non_secret_json(mcp_file, "MCP")
            self._write_sandbox_file(sandbox, "mcp.json", mcp)

    def _validate_pi_config(
        self,
        sandbox: str,
        session_config: EffectiveSessionConfig,
        *,
        workdir: Path,
    ) -> None:
        """Ask the installed Pi version to validate copied runtime metadata."""

        if not any(
            (
                session_config.models_file,
                session_config.settings_file,
                session_config.mcp_file,
            )
        ):
            return
        result = self.sbx.exec(
            sandbox,
            ("pi", "--list-models"),
            workdir=workdir,
            timeout_seconds=60,
        )
        failure = _pi_metadata_failure(result.returncode, result.stdout, result.stderr)
        if failure:
            raise PiwError(
                failure,
                code=ExitCode.CONFIG,
                kind="invalid_pi_metadata",
                hint="Fix the configured models, settings, or MCP file, then retry the session.",
            )

    @staticmethod
    def _pi_command(launch: _PiLaunch, *, resume: bool) -> tuple[str, ...]:
        """Build the Pi command for a new or resumed session."""

        argv = ["pi"]
        if resume:
            argv.append("--continue")
        else:
            argv.extend(("--name", launch.name))
        if launch.model:
            argv.extend(("--model", launch.model))
        argv.extend(("--thinking", launch.thinking))
        for skill in launch.skill_paths:
            argv.extend(("--skill", skill))
        return tuple(argv)

    def _attach_pi(self, launch: _PiLaunch, *, resume: bool) -> None:
        """Run Pi interactively inside one sandbox."""

        result = self.sbx.exec(
            launch.sandbox,
            self._pi_command(launch, resume=resume),
            workdir=launch.workdir,
            interactive=True,
        )
        if result.returncode != 0:
            raise PiwError(
                f"Pi exited with status {result.returncode}",
                code=ExitCode.SANDBOX,
                kind="pi_failed",
            )

    @staticmethod
    def _session_launch(record: SessionRecord) -> _PiLaunch:
        """Convert persistent session state into Pi launch inputs."""

        return _PiLaunch(
            sandbox=record.sandbox,
            workdir=Path(record.workspace),
            name=record.name,
            model=record.model,
            thinking=record.thinking,
            skill_paths=record.skill_paths,
        )

    def _plan_branch(
        self,
        name: str,
        branch_config: EffectiveBranchConfig,
        host_changes: HostChangesPolicy,
    ) -> _BranchPlan:
        """Resolve and validate the inputs shared by branch preview and execution."""

        normalized = normalize_session_name(name)
        if self.store.exists(normalized):
            raise PiwError(
                f"session {normalized!r} already exists",
                code=ExitCode.SESSION,
                kind="session_exists",
                hint=f"Use 'piw resume {normalized}'.",
            )

        host_status = self.git.status(branch_config.repo)
        if host_status.conflicts:
            raise PiwError(
                f"host repository {branch_config.repo} has unresolved merge conflicts",
                code=ExitCode.UNSAFE,
                kind="unresolved_host_conflicts",
                hint="Resolve or abort the merge before creating a private clone.",
            )
        if host_status.dirty and host_changes is HostChangesPolicy.FAIL:
            raise PiwError(
                f"host repository {branch_config.repo} has uncommitted or untracked changes",
                code=ExitCode.UNSAFE,
                kind="dirty_host_repository",
                hint=(
                    "Commit or stash the changes, or choose '--ignore-host-changes' or "
                    "'--carry-host-changes'."
                ),
            )

        host_patch = (
            self.git.capture_worktree_patch(branch_config.repo)
            if host_status.dirty and host_changes is HostChangesPolicy.CARRY
            else None
        )
        base_commit = self.git.resolve_ref(branch_config.repo, branch_config.base_ref)
        template_config = self.config_for_extensions(branch_config.extensions)

        return _BranchPlan(
            name=normalized,
            sandbox=branch_sandbox_name(normalized, branch_config.repo),
            base_commit=base_commit,
            template=desired_template(template_config),
            exposure=read_only_exposure(
                branch_config.repo,
                branch_config.read_only_refs,
                branch_config.skill_paths,
            ),
            host_status=host_status,
            host_patch=host_patch,
        )

    @staticmethod
    def _branch_preview(
        plan: _BranchPlan,
        branch_config: EffectiveBranchConfig,
        *,
        batch: bool,
        host_changes: HostChangesPolicy,
    ) -> dict[str, object]:
        """Render the stable branch plan returned by preview and creation."""

        return {
            "name": plan.name,
            "type": SessionKind.BRANCH.value,
            "sandbox": plan.sandbox,
            "repo": str(branch_config.repo),
            "base_ref": branch_config.base_ref,
            "base_commit": plan.base_commit,
            "branch": branch_config.branch,
            "template": plan.template,
            "read_only_refs": [str(path) for path in branch_config.read_only_refs],
            "skill_paths": [str(path) for path in branch_config.skill_paths],
            "sandbox_mounts": [str(path) for path in plan.exposure.mounts],
            "sandbox_snapshots": [str(path) for path in plan.exposure.snapshots],
            "mcp_file": str(branch_config.mcp_file) if branch_config.mcp_file else None,
            "profile": branch_config.profile,
            "cpus": branch_config.cpus,
            "memory": branch_config.memory,
            "model": branch_config.model,
            "thinking": branch_config.thinking.value,
            "batch": batch,
            "host_changes": {
                "policy": host_changes.value,
                "dirty": plan.host_status.dirty,
                "paths": list(plan.host_status.paths),
                "included_paths": list(plan.host_patch.paths) if plan.host_patch else [],
                "action": host_changes.value if plan.host_status.dirty else "none",
            },
        }

    def _require_create_capabilities(self, profile: str | None, *, clone: bool) -> None:
        """Verify that sbx supports the flags needed for this session type."""

        required: set[str] = set()
        if clone:
            required.add("--clone")
        if profile:
            required.add("--profile")

        missing = sorted(required - self.sbx.capabilities())
        if missing:
            raise PiwError(
                f"installed sbx lacks required creation flag(s): {', '.join(missing)}",
                code=ExitCode.PREREQUISITE,
                kind="unsupported_sbx",
            )

    def _create_sandbox_branch(
        self,
        plan: _BranchPlan,
        branch_config: EffectiveBranchConfig,
    ) -> None:
        """Create the configured Git branch inside a new sandbox clone."""

        result = self.sbx.exec(
            plan.sandbox,
            ("git", "switch", "--create", branch_config.branch, plan.base_commit),
            workdir=branch_config.repo,
            timeout_seconds=60,
        )
        if result.returncode != 0:
            raise PiwError(
                _failure(result.stdout, result.stderr, "cannot create Git branch"),
                code=ExitCode.SANDBOX,
                kind="branch_create_failed",
            )

    def _apply_host_patch(
        self,
        plan: _BranchPlan,
        branch_config: EffectiveBranchConfig,
    ) -> None:
        """Apply captured host changes to the private clone when requested."""

        if not plan.host_patch or not plan.host_patch.text:
            return

        result = self.sbx.exec(
            plan.sandbox,
            ("git", "apply", "--binary", "--whitespace=nowarn", "-"),
            workdir=branch_config.repo,
            input_text=plan.host_patch.text,
            timeout_seconds=60,
        )
        if result.returncode != 0:
            raise PiwError(
                _failure(
                    result.stdout,
                    result.stderr,
                    "cannot carry host changes into the branch clone",
                ),
                code=ExitCode.SANDBOX,
                kind="host_changes_apply_failed",
                hint="Retry from HEAD, commit the host changes, or use '--ignore-host-changes'.",
            )

    def _initialize_branch_sandbox(
        self,
        plan: _BranchPlan,
        branch_config: EffectiveBranchConfig,
    ) -> None:
        """Create a sandbox clone, prepare its branch, and seed Pi metadata."""

        self.sbx.create(
            name=plan.sandbox,
            branch_config=branch_config,
            template=plan.template,
            timeout_seconds=branch_config.timeout_seconds,
        )
        self._create_sandbox_branch(plan, branch_config)
        self._apply_host_patch(plan, branch_config)
        self._seed_pi_config(
            plan.sandbox,
            models_file=branch_config.models_file,
            settings_file=branch_config.settings_file,
            mcp_file=branch_config.mcp_file,
        )
        self._validate_pi_config(plan.sandbox, branch_config, workdir=branch_config.repo)

    @staticmethod
    def _branch_record(plan: _BranchPlan, branch_config: EffectiveBranchConfig) -> SessionRecord:
        """Build persistent state after branch sandbox initialization succeeds."""

        timestamp = utc_now()
        return SessionRecord(
            schema_version=2,
            name=plan.name,
            kind=SessionKind.BRANCH,
            sandbox=plan.sandbox,
            workspace=str(branch_config.repo),
            branch=branch_config.branch,
            base_commit=plan.base_commit,
            template=plan.template,
            model=branch_config.model,
            thinking=branch_config.thinking.value,
            read_only_refs=tuple(str(path) for path in branch_config.read_only_refs),
            skill_paths=tuple(str(path) for path in branch_config.skill_paths),
            profile=branch_config.profile,
            created_at=timestamp,
            last_used_at=timestamp,
            session_started=False,
        )

    def create_branch(
        self,
        *,
        name: str,
        branch_config: EffectiveBranchConfig,
        batch: bool,
        dry_run: bool,
        host_changes: HostChangesPolicy = HostChangesPolicy.FAIL,
    ) -> dict[str, object]:
        """Create a persistent private Git branch and optionally attach Pi."""

        self._require_tools("git", "sbx")
        plan = self._plan_branch(name, branch_config, host_changes)
        preview = self._branch_preview(
            plan,
            branch_config,
            batch=batch,
            host_changes=host_changes,
        )

        if dry_run:
            preview["secrets"] = self.sync_secrets(dry_run=True, force=False)
            preview["template_action"] = self.ensure_template(
                extensions=branch_config.extensions,
                dry_run=True,
                timeout_seconds=branch_config.timeout_seconds,
            )["action"]
            preview["action"] = "create"
            return preview

        self._require_create_capabilities(branch_config.profile, clone=True)
        preview["secrets"] = self.sync_secrets(dry_run=False, force=False)
        self.ensure_template(
            extensions=branch_config.extensions,
            profile=branch_config.profile,
            timeout_seconds=branch_config.timeout_seconds,
        )
        if any(sandbox.name == plan.sandbox for sandbox in self.sbx.list_sandboxes()):
            raise PiwError(
                f"sandbox {plan.sandbox!r} already exists but is not owned by session state",
                code=ExitCode.SESSION,
                kind="sandbox_name_conflict",
            )

        saved = False
        try:
            self._initialize_branch_sandbox(plan, branch_config)
            record = self._branch_record(plan, branch_config)
            self.store.save(record)
            saved = True

            if not batch:
                started = replace(record, last_used_at=utc_now(), session_started=True)
                self.store.save(started)
                self._attach_pi(self._session_launch(started), resume=False)
        finally:
            if not saved:
                self._best_effort_remove(plan.sandbox)

        return {**preview, "action": "created"}

    def _plan_chat(
        self,
        name: str | None,
        session_config: EffectiveSessionConfig,
        *,
        temporary: bool,
    ) -> _ChatPlan:
        """Resolve a chat name and reject persistent-state collisions."""

        if name is None and not temporary:
            raise PiwError(
                "persistent chats require a name",
                code=ExitCode.USAGE,
                kind="missing_session_name",
                hint="Run 'piw chat NAME' or use 'piw chat --temporary'.",
            )

        selected_name = name or f"chat-{token_urlsafe(6)}"
        normalized = normalize_session_name(selected_name)
        if not temporary and self.store.exists(normalized):
            raise PiwError(
                f"session {normalized!r} already exists",
                code=ExitCode.SESSION,
                kind="session_exists",
                hint=f"Use 'piw resume {normalized}'.",
            )

        sandbox = chat_sandbox_name(normalized, temporary=temporary)
        workspace = (
            cache_home() / "chats" / sandbox
            if temporary
            else _persistent_chat_workspace(normalized)
        )
        template_config = self.config_for_extensions(session_config.extensions)
        return _ChatPlan(
            name=normalized,
            sandbox=sandbox,
            workspace=workspace,
            template=desired_template(template_config),
            exposure=read_only_exposure(
                workspace,
                session_config.read_only_refs,
                session_config.skill_paths,
            ),
            temporary=temporary,
        )

    @staticmethod
    def _chat_preview(
        plan: _ChatPlan,
        session_config: EffectiveSessionConfig,
        *,
        batch: bool,
    ) -> dict[str, object]:
        """Render the chat lifecycle and effective sandbox settings."""

        return {
            "name": plan.name,
            "type": SessionKind.CHAT.value,
            "sandbox": plan.sandbox,
            "workspace": str(plan.workspace),
            "template": plan.template,
            "read_only_refs": [str(path) for path in session_config.read_only_refs],
            "skill_paths": [str(path) for path in session_config.skill_paths],
            "sandbox_mounts": [str(path) for path in plan.exposure.mounts],
            "sandbox_snapshots": [str(path) for path in plan.exposure.snapshots],
            "mcp_file": str(session_config.mcp_file) if session_config.mcp_file else None,
            "profile": session_config.profile,
            "cpus": session_config.cpus,
            "memory": session_config.memory,
            "model": session_config.model,
            "thinking": session_config.thinking.value,
            "temporary": plan.temporary,
            "batch": batch,
        }

    def _initialize_chat_sandbox(
        self,
        plan: _ChatPlan,
        session_config: EffectiveSessionConfig,
    ) -> None:
        """Create an empty chat workspace and seed its Pi configuration."""

        plan.workspace.mkdir(mode=0o700, parents=True)
        self.sbx.create_workspace(
            name=plan.sandbox,
            workspace=plan.workspace,
            session_config=session_config,
            template=plan.template,
            timeout_seconds=session_config.timeout_seconds,
        )
        self._seed_pi_config(
            plan.sandbox,
            models_file=session_config.models_file,
            settings_file=session_config.settings_file,
            mcp_file=session_config.mcp_file,
        )
        self._validate_pi_config(plan.sandbox, session_config, workdir=plan.workspace)

    @staticmethod
    def _chat_record(
        plan: _ChatPlan,
        session_config: EffectiveSessionConfig,
    ) -> SessionRecord:
        """Build persistent state for a named chat sandbox."""

        timestamp = utc_now()
        return SessionRecord(
            schema_version=2,
            name=plan.name,
            kind=SessionKind.CHAT,
            sandbox=plan.sandbox,
            workspace=str(plan.workspace),
            branch=None,
            base_commit=None,
            template=plan.template,
            model=session_config.model,
            thinking=session_config.thinking.value,
            read_only_refs=tuple(str(path) for path in session_config.read_only_refs),
            skill_paths=tuple(str(path) for path in session_config.skill_paths),
            profile=session_config.profile,
            created_at=timestamp,
            last_used_at=timestamp,
            session_started=False,
        )

    def _create_persistent_chat(
        self,
        plan: _ChatPlan,
        session_config: EffectiveSessionConfig,
        preview: dict[str, object],
        *,
        batch: bool,
    ) -> dict[str, object]:
        """Create saved chat state and retain it after Pi exits or fails."""

        saved = False
        try:
            self._initialize_chat_sandbox(plan, session_config)
            record = self._chat_record(plan, session_config)
            self.store.save(record)
            saved = True

            if not batch:
                started = replace(record, last_used_at=utc_now(), session_started=True)
                self.store.save(started)
                self._attach_pi(self._session_launch(started), resume=False)
        finally:
            if not saved:
                self._best_effort_remove(plan.sandbox)
                shutil.rmtree(plan.workspace, ignore_errors=True)

        return {**preview, "action": "created"}

    def _run_temporary_chat(
        self,
        plan: _ChatPlan,
        session_config: EffectiveSessionConfig,
        preview: dict[str, object],
    ) -> dict[str, object]:
        """Attach Pi once and always remove the temporary chat resources."""

        removed = False
        try:
            self._initialize_chat_sandbox(plan, session_config)
            self._attach_pi(
                _PiLaunch(
                    sandbox=plan.sandbox,
                    workdir=plan.workspace,
                    name=plan.name,
                    model=session_config.model,
                    thinking=session_config.thinking.value,
                    skill_paths=tuple(str(path) for path in session_config.skill_paths),
                ),
                resume=False,
            )
            self.sbx.remove(plan.sandbox)
            removed = True
        finally:
            if not removed:
                self._best_effort_remove(plan.sandbox)
            shutil.rmtree(plan.workspace, ignore_errors=True)

        return {**preview, "action": "completed", "removed": True}

    def chat(
        self,
        name: str | None,
        session_config: EffectiveSessionConfig,
        *,
        temporary: bool,
        batch: bool,
        dry_run: bool,
    ) -> dict[str, object]:
        """Create a persistent named chat or run a disposable temporary chat."""

        if temporary and batch:
            raise PiwError(
                "--batch cannot be combined with --temporary",
                code=ExitCode.USAGE,
                kind="invalid_usage",
            )

        self._require_tools("sbx")
        plan = self._plan_chat(name, session_config, temporary=temporary)
        preview = self._chat_preview(plan, session_config, batch=batch)

        if dry_run:
            preview["secrets"] = self.sync_secrets(dry_run=True, force=False)
            preview["template_action"] = self.ensure_template(
                extensions=session_config.extensions,
                dry_run=True,
                timeout_seconds=session_config.timeout_seconds,
            )["action"]
            return {**preview, "action": "create"}

        self._require_create_capabilities(session_config.profile, clone=False)
        preview["secrets"] = self.sync_secrets(dry_run=False, force=False)
        self.ensure_template(
            extensions=session_config.extensions,
            profile=session_config.profile,
            timeout_seconds=session_config.timeout_seconds,
        )

        existing = {item.name for item in self.sbx.list_sandboxes()}
        if plan.sandbox in existing or plan.workspace.exists():
            raise PiwError(
                f"chat resources for {plan.name!r} already exist outside session state",
                code=ExitCode.SESSION,
                kind="sandbox_name_conflict",
                hint="Remove the orphaned sandbox or workspace, then retry.",
            )

        if plan.temporary:
            return self._run_temporary_chat(plan, session_config, preview)
        return self._create_persistent_chat(plan, session_config, preview, batch=batch)

    def resume(self, name: str, *, timeout_seconds: int = 120) -> dict[str, object]:
        """Resume the most recent Pi conversation in a persistent session."""

        secrets = self.sync_secrets(dry_run=False, force=False)
        record = self.store.load(normalize_session_name(name))
        sandbox = self._sandbox_for(record)

        if sandbox.status == SandboxPhase.STOPPED:
            wake = self.sbx.exec(
                record.sandbox,
                ("true",),
                workdir=Path(record.workspace),
                timeout_seconds=timeout_seconds,
            )
            if wake.returncode != 0:
                raise PiwError(
                    _failure(wake.stdout, wake.stderr, "cannot restart sandbox"),
                    code=ExitCode.SANDBOX,
                    kind="sandbox_start_failed",
                )

        updated = replace(record, last_used_at=utc_now(), session_started=True)
        self.store.save(updated)
        self._attach_pi(self._session_launch(updated), resume=record.session_started)

        return {
            "name": record.name,
            "type": record.kind.value,
            "sandbox": record.sandbox,
            "previous_status": sandbox.status.value,
            "secrets": secrets,
        }

    def _sandbox_for(self, record: SessionRecord) -> SandboxInfo:
        """Look up a session's live sandbox or report recoverable missing state."""

        sandboxes = {sandbox.name: sandbox for sandbox in self.sbx.list_sandboxes()}
        sandbox = sandboxes.get(record.sandbox)
        if not sandbox:
            hint = (
                f"The host recovery remote is 'sandbox-{record.sandbox}'."
                if record.kind is SessionKind.BRANCH
                else "The chat sandbox may have been removed outside piw."
            )
            raise PiwError(
                f"sandbox {record.sandbox!r} for session {record.name!r} is missing",
                code=ExitCode.STATE,
                kind="missing_sandbox",
                hint=hint,
            )
        return sandbox

    @staticmethod
    def _chat_workspace_for_cleanup(record: SessionRecord) -> Path:
        """Validate and return a piw-managed persistent chat workspace."""

        if record.kind is not SessionKind.CHAT:
            raise AssertionError("chat workspace cleanup requires a chat session")

        workspace = Path(record.workspace).resolve(strict=False)
        expected = _persistent_chat_workspace(record.name)
        if workspace != expected:
            raise PiwError(
                f"refusing to remove unexpected chat workspace {workspace}",
                code=ExitCode.STATE,
                kind="invalid_session_state",
                hint=f"Expected the managed workspace at {expected}.",
            )

        return workspace

    @classmethod
    def _remove_chat_workspace(cls, record: SessionRecord) -> None:
        """Remove a validated persistent chat workspace if it still exists."""

        workspace = cls._chat_workspace_for_cleanup(record)

        try:
            shutil.rmtree(workspace)
        except FileNotFoundError:
            return
        except OSError as error:
            raise PiwError(
                f"cannot remove chat workspace {workspace}: {error}",
                code=ExitCode.STATE,
                kind="workspace_cleanup_failed",
            ) from error

    def list_sessions(self) -> list[dict[str, object]]:
        """Return all persistent sessions reconciled with live sandbox state."""

        sandboxes = {sandbox.name: sandbox for sandbox in self.sbx.list_sandboxes()}
        output: list[dict[str, object]] = []
        for record in self.store.list():
            sandbox = sandboxes.get(record.sandbox)
            output.append(
                {
                    "name": record.name,
                    "type": record.kind.value,
                    "sandbox": record.sandbox,
                    "status": sandbox.status.value if sandbox else SandboxPhase.MISSING.value,
                    "repo": record.workspace if record.kind is SessionKind.BRANCH else None,
                    "branch": record.branch,
                    "model": record.model,
                    "created_at": record.created_at,
                    "last_used_at": record.last_used_at,
                }
            )
        return output

    def _git_safety(self, record: SessionRecord) -> dict[str, object]:
        """Inspect branch Git state before operations that may discard work."""

        if record.kind is not SessionKind.BRANCH or record.base_commit is None:
            raise AssertionError("Git safety inspection requires a branch session")

        status = self.sbx.exec(
            record.sandbox,
            ("git", "status", "--porcelain=v1", "--untracked-files=all"),
            workdir=Path(record.workspace),
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
            workdir=Path(record.workspace),
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
            workdir=Path(record.workspace),
            timeout_seconds=60,
        )
        ahead = 0

        if upstream.returncode == 0:
            count = self.sbx.exec(
                record.sandbox,
                ("git", "rev-list", "--count", "@{upstream}..HEAD"),
                workdir=Path(record.workspace),
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

    def status(self, name: str) -> dict[str, object]:
        """Return detailed persistent-session and cleanup status."""

        record = self.store.load(normalize_session_name(name))
        sandbox = self._sandbox_for(record)
        safety: dict[str, object] | None = None
        if record.kind is SessionKind.BRANCH and sandbox.status == SandboxPhase.RUNNING:
            safety = self._git_safety(record)
        return {
            **record.to_json_object(),
            "status": sandbox.status.value,
            "git": safety,
            "git_inspection_deferred": (record.kind is SessionKind.BRANCH and safety is None),
            "recovery_remote": (
                f"sandbox-{record.sandbox}" if record.kind is SessionKind.BRANCH else None
            ),
        }

    def shell(self, name: str, cwd: Path | None = None) -> None:
        """Open an interactive shell in a persistent session sandbox."""

        record = self.store.load(normalize_session_name(name))
        self._sandbox_for(record)
        result = self.sbx.exec(
            record.sandbox,
            ("bash",),
            workdir=cwd or Path(record.workspace),
            interactive=True,
        )
        if result.returncode != 0:
            raise PiwError(
                f"sandbox shell exited with status {result.returncode}",
                code=ExitCode.SANDBOX,
                kind="shell_failed",
            )

    def execute(
        self, name: str, command: tuple[str, ...], cwd: Path | None = None
    ) -> dict[str, object]:
        """Execute one captured command inside a persistent session sandbox."""

        if not command:
            raise PiwError(
                "piw exec requires a command after '--'",
                code=ExitCode.USAGE,
                kind="missing_command",
            )

        record = self.store.load(normalize_session_name(name))
        self._sandbox_for(record)
        result = self.sbx.exec(
            record.sandbox,
            command,
            workdir=cwd or Path(record.workspace),
        )

        return {
            "name": record.name,
            "type": record.kind.value,
            "command": render_command(command),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": result.duration_seconds,
        }

    def stop(self, name: str, *, dry_run: bool) -> dict[str, object]:
        """Stop one persistent session sandbox without removing it."""

        record = self.store.load(normalize_session_name(name))
        sandbox = self._sandbox_for(record)
        if not dry_run and sandbox.status == SandboxPhase.RUNNING:
            self.sbx.stop(record.sandbox)
        return {
            "name": record.name,
            "type": record.kind.value,
            "sandbox": record.sandbox,
            "previous_status": sandbox.status.value,
            "action": "would_stop" if dry_run else "stopped",
        }

    def clean(self, name: str, *, dry_run: bool, force: bool) -> dict[str, object]:
        """Remove a chat or safely remove a branch session."""

        record = self.store.load(normalize_session_name(name))
        sandboxes = {item.name: item for item in self.sbx.list_sandboxes()}
        sandbox = sandboxes.get(record.sandbox)
        if sandbox is None and record.kind is SessionKind.BRANCH:
            sandbox = self._sandbox_for(record)

        previous_status = sandbox.status if sandbox else SandboxPhase.MISSING
        if record.kind is SessionKind.CHAT:
            self._chat_workspace_for_cleanup(record)
        if (
            record.kind is SessionKind.BRANCH
            and dry_run
            and previous_status == SandboxPhase.STOPPED
        ):
            return {
                "name": record.name,
                "type": record.kind.value,
                "sandbox": record.sandbox,
                "previous_status": previous_status.value,
                "safety": None,
                "safety_inspection_deferred": True,
                "action": "would_inspect_then_remove",
            }

        safety = self._git_safety(record) if record.kind is SessionKind.BRANCH else None
        if safety is not None and not bool(safety["safe_to_clean"]) and not force:
            raise PiwError(
                f"branch session {record.name!r} has dirty or unpushed work",
                code=ExitCode.UNSAFE,
                kind="unsafe_cleanup",
                hint=f"Inspect it with 'piw status {record.name}' or use --force to discard it.",
            )

        if not dry_run:
            if sandbox:
                self.sbx.remove(record.sandbox)
            if record.kind is SessionKind.CHAT:
                self._remove_chat_workspace(record)
            self.store.delete(record.name)

        return {
            "name": record.name,
            "type": record.kind.value,
            "sandbox": record.sandbox,
            "previous_status": previous_status.value,
            "safety": safety,
            "action": "would_remove" if dry_run else "removed",
        }

    def _tool_doctor_checks(self) -> list[DoctorCheck]:
        """Check required host tools and the installed sbx capabilities."""

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

        if not self.runner.which("sbx"):
            return checks

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
            missing = {"--clone", "--profile"} - capabilities
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

        return checks

    def _host_config_doctor_checks(self) -> list[DoctorCheck]:
        """Check host authentication, reference paths, and Pi metadata files."""

        socket = os.environ.get("SSH_AUTH_SOCK")
        socket_ok = bool(socket and Path(socket).exists())
        checks = [
            DoctorCheck(
                name="ssh-agent",
                status="pass" if socket_ok else "warn",
                message=socket if socket_ok and socket else "SSH_AUTH_SOCK is unavailable",
                hint="Load an SSH key on the host before publishing from a sandbox."
                if not socket_ok
                else None,
            )
        ]

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
            ("mcp-file", self.config.pi.mcp_file),
        ):
            if not path:
                continue
            if not path.is_file():
                checks.append(DoctorCheck(label, "fail", str(path)))
                continue

            try:
                read_non_secret_json(path, label.removesuffix("-file"))
                checks.append(DoctorCheck(label, "pass", str(path)))
            except PiwError as error:
                checks.append(DoctorCheck(label, "fail", str(error)))

        return checks

    @staticmethod
    def _secret_doctor_check(secret: dict[str, object]) -> DoctorCheck:
        """Convert redacted secret status into one doctor result."""

        status = str(secret["status"])
        required = bool(secret["required"])
        if status == "synced":
            check_status = "pass"
            hint = None
        elif status == "missing" and required:
            check_status = "fail"
            hint = "Export the source variable, then run 'piw secrets sync'."
        else:
            check_status = "warn"
            hint = (
                "Run 'piw secrets sync'."
                if bool(secret["source_available"])
                else "Export the optional source variable when this provider is needed."
            )

        return DoctorCheck(
            name=f"secret:{secret['sandbox_env']}",
            status=check_status,
            message=str(secret["reason"]),
            hint=hint,
        )

    def _sandbox_config_doctor_checks(self) -> list[DoctorCheck]:
        """Check Docker Sandbox secrets and the reusable Pi template."""

        checks: list[DoctorCheck] = []
        if self.config.sandbox.secrets:
            try:
                checks.extend(self._secret_doctor_check(secret) for secret in self.secret_status())
            except PiwError as error:
                checks.append(DoctorCheck("sandbox-secrets", "fail", str(error)))

        try:
            status = self.template_status()
            installed = bool(status["installed"])
            checks.append(
                DoctorCheck(
                    name="pi-template",
                    status="pass" if installed else "warn",
                    message=str(status["desired"]),
                    hint=None if installed else "Run 'piw template ensure'.",
                )
            )
        except PiwError as error:
            checks.append(DoctorCheck("pi-template", "fail", str(error)))

        return checks

    def doctor(self, *, live: bool, timeout_seconds: int) -> list[DoctorCheck]:
        """Run prerequisite checks and an optional disposable sandbox probe."""

        checks = self._tool_doctor_checks()
        checks.extend(self._host_config_doctor_checks())

        if self.runner.which("sbx"):
            checks.extend(self._sandbox_config_doctor_checks())

        if live:
            checks.append(self._live_doctor_probe(timeout_seconds))

        return checks

    def _probe_pi_metadata(
        self,
        probe: str,
        workspace: Path,
        timeout_seconds: int,
    ) -> str | None:
        """Seed and validate optional Pi runtime metadata in a live probe."""

        self._seed_pi_config(
            probe,
            models_file=self.config.pi.models_file,
            settings_file=self.config.pi.settings_file,
            mcp_file=self.config.pi.mcp_file,
        )
        if not any(
            (
                self.config.pi.models_file,
                self.config.pi.settings_file,
                self.config.pi.mcp_file,
            )
        ):
            return None

        metadata = self.sbx.exec(
            probe,
            ("pi", "--list-models"),
            workdir=workspace,
            timeout_seconds=timeout_seconds,
        )
        return _pi_metadata_failure(
            metadata.returncode,
            metadata.stdout,
            metadata.stderr,
        )

    def _live_doctor_probe(self, timeout_seconds: int) -> DoctorCheck:
        """Create a disposable sandbox to test writes, networking, and Pi config."""

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
            if result.returncode != 0:
                return DoctorCheck(
                    "live-sandbox",
                    "fail",
                    _failure(result.stdout, result.stderr, "live probe failed"),
                )

            if failure := self._probe_pi_metadata(probe, workspace, timeout_seconds):
                return DoctorCheck("live-sandbox", "fail", failure)

            return DoctorCheck(
                "live-sandbox",
                "pass",
                "create, write, network, and Pi metadata probes passed",
            )
        except PiwError as error:
            return DoctorCheck("live-sandbox", "fail", str(error))
        finally:
            self._best_effort_remove(probe)
