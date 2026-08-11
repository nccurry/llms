"""Command-line interface for piw."""

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, NoReturn, Protocol

from piw import __version__
from piw.config import (
    config_as_object,
    default_config_path,
    default_config_text,
    load_config,
    state_home,
)
from piw.errors import ErrorDetail, ExitCode, PiwError
from piw.models import (
    AppConfig,
    EffectiveSessionConfig,
    HostChangesPolicy,
    OutputEnvelope,
    OutputFormat,
    ThinkingLevel,
)
from piw.presentation import dump_yaml, render_text
from piw.process import SubprocessRunner
from piw.service import PiwService, normalize_session_name
from piw.state import StateStore

_AI_CONTEXT = """
AI_CONTEXT:
  Use --output json or --output yaml for stable machine-readable output.
  Use --dry-run before mutating or destructive operations.
  Use --batch or --yes to avoid interactive prompts.
  Use --timeout to bound sandbox and template operations.
  Run piw secrets status/sync for declared environment-to-sandbox credentials.
  Exit 0 is success; 10-16 are piw failures; 20 is a failed piw exec command.
"""

_BRANCH_AI_CONTEXT = """
AI_CONTEXT:
  Use --dry-run with --output json or --output yaml to inspect the creation plan.
  Use --existing BRANCH to adopt an exact local or REMOTE/BRANCH ref.
  Use --batch to create the branch session without attaching an interactive Pi process.
  Use --timeout to bound sandbox and template creation.
  Exit 0 is success; 10-16 are piw failures.
"""

_CHAT_AI_CONTEXT = """
AI_CONTEXT:
  Use --dry-run with --output json or --output yaml to inspect session creation.
  Named chats persist; use --temporary for a disposable chat with an optional name.
  Use --batch to create a persistent chat without attaching Pi.
  Use --timeout to bound sandbox and template creation.
  Exit 0 is success; 10-16 are piw failures.
"""


class PiwArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports usage failures through piw's error model."""

    def error(self, message: str) -> NoReturn:
        """Raise a typed usage error instead of exiting immediately."""

        raise PiwError(message, code=ExitCode.USAGE, kind="invalid_usage", hint=self.format_usage())


class _CommandParsers(Protocol):
    """Public shape used to register argparse subcommands."""

    def add_parser(self, name: str, **kwargs: Any) -> argparse.ArgumentParser:
        """Register one named subparser and return it."""

        ...


def _common_parser(*, suppress_defaults: bool = False) -> PiwArgumentParser:
    """Build a parser for options shared by the top level and subcommands."""

    parser = PiwArgumentParser(add_help=False)
    default: object = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument(
        "--config",
        type=Path,
        default=default,
        help="Use a specific piw TOML configuration.",
    )

    parser.add_argument(
        "--output",
        choices=tuple(OutputFormat),
        default=argparse.SUPPRESS if suppress_defaults else OutputFormat.TEXT,
        type=OutputFormat,
        help="Select human-readable text, JSON, or YAML output.",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS if suppress_defaults else False,
        help="Disable terminal color output.",
    )
    return parser


def _positive_int(value: str) -> int:
    """Parse a positive integer supplied on the command line."""

    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _add_session_overrides(parser: argparse.ArgumentParser) -> None:
    """Register Pi and sandbox overrides shared by branch and chat sessions."""

    parser.add_argument(
        "--ref", action="append", type=Path, default=[], help="Read-only reference path."
    )
    parser.add_argument(
        "--skill", action="append", type=Path, default=[], help="Read-only Pi skill path."
    )
    parser.add_argument("--model", help="Pi model in provider/model form.")
    parser.add_argument("--thinking", choices=tuple(ThinkingLevel), type=ThinkingLevel)
    parser.add_argument("--profile", help="Docker Sandbox governance profile.")
    parser.add_argument(
        "--extension", action="append", default=[], help="Pinned Pi extension package."
    )
    parser.add_argument("--models-file", type=Path, help="Non-secret Pi models metadata.")
    parser.add_argument("--settings-file", type=Path, help="Non-secret Pi settings metadata.")
    parser.add_argument("--mcp-file", type=Path, help="Non-secret Pi MCP client configuration.")
    parser.add_argument("--timeout", type=_positive_int, help="Creation timeout in seconds.")


def _add_branch_command(
    commands: _CommandParsers,
    common: PiwArgumentParser,
) -> None:
    """Register the persistent Git-backed session command."""

    branch = commands.add_parser(
        "branch",
        parents=[common],
        help="Create a private branch clone and start Pi.",
        epilog=_BRANCH_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    branch.add_argument("name", help="Persistent session name.")
    branch.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository path.")
    source = branch.add_mutually_exclusive_group()
    source.add_argument("--base", help="Base revision; defaults to the current HEAD.")
    source.add_argument(
        "--existing",
        metavar="BRANCH",
        help="Adopt an exact local branch or explicit REMOTE/BRANCH.",
    )
    branch.add_argument("--branch", help="Git branch; defaults to piw/<name>.")
    _add_session_overrides(branch)
    branch.add_argument(
        "--batch", action="store_true", help="Create the session without attaching Pi."
    )
    host_changes = branch.add_mutually_exclusive_group()
    host_changes.add_argument(
        "--ignore-host-changes",
        action="store_const",
        const=HostChangesPolicy.IGNORE,
        dest="host_changes",
        help="Clone the selected commit without host working-tree changes.",
    )
    host_changes.add_argument(
        "--carry-host-changes",
        action="store_const",
        const=HostChangesPolicy.CARRY,
        dest="host_changes",
        help="Copy host working-tree changes into the private branch clone.",
    )
    branch.set_defaults(host_changes=HostChangesPolicy.FAIL)

    branch.add_argument("--dry-run", action="store_true", help="Preview without creating anything.")


def _add_chat_command(
    commands: _CommandParsers,
    common: PiwArgumentParser,
) -> None:
    """Register persistent and temporary repository-free Pi sessions."""

    chat = commands.add_parser(
        "chat",
        parents=[common],
        help="Create a persistent repository-free Pi session.",
        epilog=_CHAT_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    chat.add_argument("name", nargs="?", help="Session name; required unless --temporary.")
    _add_session_overrides(chat)
    chat.add_argument(
        "--temporary",
        action="store_true",
        help="Remove the sandbox, workspace, and conversation when Pi exits.",
    )
    chat.add_argument(
        "--batch",
        action="store_true",
        help="Create a persistent chat without attaching Pi.",
    )
    chat.add_argument("--dry-run", action="store_true", help="Preview without creating anything.")


def _add_session_lifecycle_commands(
    commands: _CommandParsers,
    common: PiwArgumentParser,
) -> None:
    """Register commands that manage existing persistent sessions."""

    resume = commands.add_parser(
        "resume",
        parents=[common],
        help="Continue the latest Pi conversation for a persistent session.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    resume.add_argument("name")
    resume.add_argument(
        "--timeout", type=_positive_int, default=120, help="Sandbox startup timeout in seconds."
    )

    commands.add_parser("list", parents=[common], help="List persistent sessions and sandboxes.")

    status = commands.add_parser("status", parents=[common], help="Show detailed session status.")
    status.add_argument("name")

    shell = commands.add_parser("shell", parents=[common], help="Open a session sandbox shell.")
    shell.add_argument("name")
    shell.add_argument("--cwd", type=Path, help="Sandbox working directory.")

    execute = commands.add_parser(
        "exec",
        parents=[common],
        help="Run a captured command in a persistent session sandbox.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    execute.add_argument("name")
    execute.add_argument("--cwd", type=Path, help="Sandbox working directory.")
    execute.add_argument("exec_command", nargs=argparse.REMAINDER, metavar="COMMAND")

    stop = commands.add_parser("stop", parents=[common], help="Stop a session without deleting it.")
    stop.add_argument("name")
    stop.add_argument("--dry-run", action="store_true")
    stop.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")

    clean = commands.add_parser(
        "clean",
        parents=[common],
        help="Remove a persistent session and its sandbox.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    clean.add_argument("name")
    clean.add_argument("--dry-run", action="store_true")
    clean.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    clean.add_argument(
        "--force",
        action="store_true",
        help="Discard dirty or unpushed branch work.",
    )


def _add_secret_commands(
    commands: _CommandParsers,
    common: PiwArgumentParser,
) -> None:
    """Register commands that inspect and synchronize sandbox secrets."""

    secrets = commands.add_parser(
        "secrets",
        help="Manage declared host-to-sandbox secret mappings.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    secret_commands = secrets.add_subparsers(dest="secrets_command", required=True)
    secret_commands.add_parser(
        "status", parents=[common], help="Show redacted synchronization status."
    )

    sync = secret_commands.add_parser(
        "sync",
        parents=[common],
        help="Synchronize source environment variables into Docker Sandboxes.",
    )
    sync.add_argument("--dry-run", action="store_true", help="Preview without changing secrets.")
    sync.add_argument("--force", action="store_true", help="Rewrite every available mapping.")


def _add_config_commands(
    commands: _CommandParsers,
    common: PiwArgumentParser,
) -> None:
    """Register commands that inspect, validate, and edit piw configuration."""

    config = commands.add_parser("config", help="Inspect or edit user configuration.")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("path", parents=[common], help="Print the active config path.")

    show = config_commands.add_parser(
        "show", parents=[common], help="Show stored or effective config."
    )
    show.add_argument("--effective", action="store_true")

    config_commands.add_parser("validate", parents=[common], help="Validate the active config.")
    config_commands.add_parser("edit", parents=[common], help="Edit the active config.")


def _add_template_commands(
    commands: _CommandParsers,
    common: PiwArgumentParser,
) -> None:
    """Register commands that inspect and maintain reusable Pi templates."""

    template = commands.add_parser("template", help="Manage reusable Pi templates.")
    template_commands = template.add_subparsers(dest="template_command", required=True)
    template_commands.add_parser("status", parents=[common], help="Show desired template state.")

    ensure = template_commands.add_parser(
        "ensure", parents=[common], help="Build a missing template."
    )
    ensure.add_argument("--dry-run", action="store_true")
    ensure.add_argument("--timeout", type=_positive_int)

    rebuild = template_commands.add_parser(
        "rebuild", parents=[common], help="Rebuild the template."
    )
    rebuild.add_argument("--dry-run", action="store_true")
    rebuild.add_argument("--yes", action="store_true")
    rebuild.add_argument("--timeout", type=_positive_int)

    prune = template_commands.add_parser(
        "prune", parents=[common], help="Remove obsolete piw templates."
    )
    prune.add_argument("--dry-run", action="store_true")
    prune.add_argument("--yes", action="store_true")


def build_parser() -> PiwArgumentParser:
    """Build the complete public command tree."""

    common = _common_parser(suppress_defaults=True)
    parser = PiwArgumentParser(
        prog="piw",
        description="Run persistent branch or chat sessions in Docker Sandboxes.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_common_parser()],
    )
    parser.add_argument("--version", action="store_true", help="Show version information and exit.")
    commands = parser.add_subparsers(dest="command")

    init = commands.add_parser(
        "init",
        parents=[common],
        help="Create a neutral user configuration.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init.add_argument("--force", action="store_true", help="Replace an existing config file.")
    init.add_argument("--dry-run", action="store_true", help="Preview without writing files.")

    doctor = commands.add_parser(
        "doctor",
        parents=[common],
        help="Check host, sandbox, model, skill, and runtime-config readiness.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor.add_argument(
        "--live", action="store_true", help="Create and remove a live probe sandbox."
    )
    doctor.add_argument(
        "--timeout", type=_positive_int, default=120, help="Live-probe timeout in seconds."
    )

    _add_branch_command(commands, common)
    _add_chat_command(commands, common)
    _add_session_lifecycle_commands(commands, common)
    _add_secret_commands(commands, common)
    _add_config_commands(commands, common)
    _add_template_commands(commands, common)

    return parser


def _confirm(prompt: str, *, approved: bool, dry_run: bool) -> None:
    """Require approval unless the caller already approved or is doing a dry run."""

    if approved or dry_run:
        return
    if not sys.stdin.isatty():
        raise PiwError(
            "confirmation is required in a non-interactive session",
            code=ExitCode.UNSAFE,
            kind="confirmation_required",
            hint="Review with --dry-run, then repeat with --yes.",
        )

    answer = input(f"{prompt} [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise PiwError(
            "operation cancelled",
            code=ExitCode.UNSAFE,
            kind="cancelled",
        )


def _error_object(detail: ErrorDetail) -> dict[str, object]:
    """Convert an error detail into the public JSON error shape."""

    return {"kind": detail.kind, "message": detail.message, "hint": detail.hint}


def _output_object(
    command: str,
    data: object,
    *,
    ok: bool,
    error: ErrorDetail | None = None,
) -> dict[str, object]:
    """Build the stable envelope shared by JSON and YAML output."""

    envelope = OutputEnvelope(
        schema_version=1,
        command=command,
        ok=ok,
        data=data,
        error=_error_object(error) if error else None,
    )
    return envelope.to_json_object()


def _emit_json(command: str, data: object, *, ok: bool, error: ErrorDetail | None = None) -> None:
    """Print one command result using piw's stable JSON envelope."""

    print(json.dumps(_output_object(command, data, ok=ok, error=error), indent=2, sort_keys=True))


def _emit_yaml(command: str, data: object, *, ok: bool, error: ErrorDetail | None = None) -> None:
    """Print one command result using piw's stable YAML envelope."""

    sys.stdout.write(dump_yaml(_output_object(command, data, ok=ok, error=error)))


def emit(command: str, data: object, output: OutputFormat, *, ok: bool = True) -> None:
    """Emit command output with an explicit success status."""

    if output == OutputFormat.JSON:
        _emit_json(command, data, ok=ok)
    elif output == OutputFormat.YAML:
        _emit_yaml(command, data, ok=ok)
    else:
        print(render_text(command, data))


def _active_config_path(args: argparse.Namespace) -> Path:
    """Resolve the CLI config override or the default user config path."""

    value: Path | None = getattr(args, "config", None)
    return (value or default_config_path()).expanduser()


def _resolved_path(value: Path | None) -> Path | None:
    """Resolve an optional path supplied by a CLI flag."""

    return value.expanduser().resolve(strict=False) if value else None


def _init(args: argparse.Namespace) -> dict[str, object]:
    """Create the initial config and state directories for ``piw init``."""

    path = _active_config_path(args)
    action = "replace" if path.exists() else "create"

    if path.exists() and not args.force and not args.dry_run:
        raise PiwError(
            f"configuration already exists: {path}",
            code=ExitCode.UNSAFE,
            kind="config_exists",
            hint="Use 'piw config edit' or repeat 'piw init --force'.",
        )

    if not args.dry_run:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text(default_config_text(), encoding="utf-8")
        path.chmod(0o600)
        (state_home() / "sessions").mkdir(mode=0o700, parents=True, exist_ok=True)

    return {"path": str(path), "action": f"would_{action}" if args.dry_run else action}


def _edit_config(args: argparse.Namespace, runner: SubprocessRunner) -> dict[str, object]:
    """Open the active config in the user's editor, then validate the saved file."""

    path = _active_config_path(args)
    if not path.exists():
        raise PiwError(
            f"configuration does not exist: {path}",
            code=ExitCode.CONFIG,
            kind="missing_config",
            hint="Run 'piw init' first.",
        )

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        raise PiwError(
            "$VISUAL and $EDITOR are both unset",
            code=ExitCode.PREREQUISITE,
            kind="missing_editor",
        )

    try:
        editor_command = shlex.split(editor)
    except ValueError as error:
        raise PiwError(
            f"cannot parse editor command: {error}",
            code=ExitCode.CONFIG,
            kind="invalid_editor",
        ) from error

    result = runner.run((*editor_command, str(path)), interactive=True)
    if result.returncode != 0:
        raise PiwError(
            f"editor exited with status {result.returncode}",
            code=ExitCode.PREREQUISITE,
            kind="editor_failed",
        )

    load_config(path)
    return {"path": str(path), "valid": True}


def _session_config(args: argparse.Namespace, service: PiwService) -> EffectiveSessionConfig:
    """Resolve the CLI overrides shared by branch and chat commands."""

    return service.effective_session_config(
        refs=tuple(path.expanduser().resolve(strict=False) for path in args.ref),
        skills=tuple(path.expanduser().resolve(strict=False) for path in args.skill),
        model=args.model,
        thinking=args.thinking,
        profile=args.profile,
        extensions=tuple(args.extension),
        models_file=_resolved_path(args.models_file),
        settings_file=_resolved_path(args.settings_file),
        mcp_file=_resolved_path(args.mcp_file),
        timeout_seconds=args.timeout,
    )


def _create_branch(args: argparse.Namespace, service: PiwService) -> dict[str, object]:
    """Translate ``piw branch`` arguments and create the requested session."""

    branch_config = service.effective_branch_config(
        session_config=_session_config(args, service),
        repo_candidate=args.repo,
        base_ref=args.base,
        branch=args.branch,
        existing=args.existing,
        name=args.name,
    )

    return service.create_branch(
        name=args.name,
        branch_config=branch_config,
        batch=args.batch,
        dry_run=args.dry_run,
        host_changes=args.host_changes,
    )


def _chat(args: argparse.Namespace, service: PiwService) -> dict[str, object]:
    """Translate ``piw chat`` arguments into one session creation request."""

    return service.chat(
        args.name,
        _session_config(args, service),
        temporary=args.temporary,
        batch=args.batch,
        dry_run=args.dry_run,
    )


def _dispatch_secrets(args: argparse.Namespace, service: PiwService) -> object:
    """Run a command from the ``piw secrets`` family."""

    if args.secrets_command == "status":
        return service.secret_status()
    if args.secrets_command == "sync":
        return service.sync_secrets(dry_run=args.dry_run, force=args.force)

    raise AssertionError(f"unsupported secrets command: {args.secrets_command}")


def _dispatch_config(
    args: argparse.Namespace,
    service: PiwService,
    runner: SubprocessRunner,
) -> object:
    """Run a command from the ``piw config`` family."""

    path = _active_config_path(args)
    if args.config_command == "path":
        return str(path)

    if args.config_command == "show":
        if args.effective:
            return config_as_object(load_config(path))
        if not path.exists():
            return {"path": str(path), "exists": False, "content": ""}
        return {
            "path": str(path),
            "exists": True,
            "content": path.read_text(encoding="utf-8"),
        }

    if args.config_command == "validate":
        parsed = load_config(path)
        return {
            "path": str(path),
            "valid": True,
            "config_version": parsed.config_version,
        }

    if args.config_command == "edit":
        return _edit_config(args, runner)

    raise AssertionError(f"unsupported config command: {args.config_command}")


def _dispatch_template(args: argparse.Namespace, service: PiwService) -> object:
    """Run a command from the ``piw template`` family."""

    if args.template_command == "status":
        return service.template_status()

    if args.template_command == "ensure":
        return service.ensure_template(dry_run=args.dry_run, timeout_seconds=args.timeout)

    if args.template_command == "rebuild":
        _confirm("Rebuild the reusable Pi template?", approved=args.yes, dry_run=args.dry_run)
        return service.ensure_template(
            force=True,
            dry_run=args.dry_run,
            timeout_seconds=args.timeout,
        )

    if args.template_command == "prune":
        _confirm("Remove obsolete piw templates?", approved=args.yes, dry_run=args.dry_run)
        return service.prune_templates(dry_run=args.dry_run)

    raise AssertionError(f"unsupported template command: {args.template_command}")


def _dispatch(
    args: argparse.Namespace, service: PiwService, runner: SubprocessRunner
) -> tuple[object, int]:
    """Run the parsed subcommand and return its output and process exit code."""

    command = args.command
    if command == "init":
        return _init(args), ExitCode.SUCCESS

    if command == "doctor":
        checks = service.doctor(live=args.live, timeout_seconds=args.timeout)
        data = [asdict(check) for check in checks]
        failed = any(check.status == "fail" for check in checks)
        return data, ExitCode.PREREQUISITE if failed else ExitCode.SUCCESS

    if command == "branch":
        return _create_branch(args, service), ExitCode.SUCCESS

    if command == "chat":
        return _chat(args, service), ExitCode.SUCCESS

    if command == "resume":
        return service.resume(args.name, timeout_seconds=args.timeout), ExitCode.SUCCESS

    if command == "list":
        return service.list_sessions(), ExitCode.SUCCESS

    if command == "status":
        return service.status(args.name), ExitCode.SUCCESS

    if command == "shell":
        service.shell(args.name, cwd=args.cwd)
        return {
            "name": normalize_session_name(args.name),
            "action": "shell_closed",
        }, ExitCode.SUCCESS

    if command == "exec":
        exec_command = tuple(args.exec_command)
        if exec_command and exec_command[0] == "--":
            exec_command = exec_command[1:]

        data = service.execute(args.name, exec_command, cwd=args.cwd)
        code = ExitCode.SUCCESS if data["returncode"] == 0 else ExitCode.COMMAND
        return data, code

    if command == "stop":
        _confirm(f"Stop session {args.name!r}?", approved=args.yes, dry_run=args.dry_run)
        return service.stop(args.name, dry_run=args.dry_run), ExitCode.SUCCESS

    if command == "clean":
        _confirm(
            f"Remove session {args.name!r}, its sandbox, and any chat workspace?",
            approved=args.yes,
            dry_run=args.dry_run,
        )
        return service.clean(args.name, dry_run=args.dry_run, force=args.force), ExitCode.SUCCESS

    if command == "secrets":
        return _dispatch_secrets(args, service), ExitCode.SUCCESS

    if command == "config":
        return _dispatch_config(args, service, runner), ExitCode.SUCCESS

    if command == "template":
        return _dispatch_template(args, service), ExitCode.SUCCESS

    raise PiwError(
        "a command is required",
        code=ExitCode.USAGE,
        kind="missing_command",
        hint="Run 'piw --help'.",
    )


def _version_data(runner: SubprocessRunner) -> dict[str, object]:
    """Collect piw and available dependency versions for ``piw --version``."""

    data: dict[str, object] = {"piw": __version__, "python": sys.version.split()[0]}
    version_commands = {
        "uv": ("uv", "--version"),
        "sbx": ("sbx", "version"),
        "pi": ("pi", "--version"),
    }
    for command, argv in version_commands.items():
        if runner.which(command):
            result = runner.run(argv, timeout_seconds=30)
            data[command] = (
                (result.stdout or result.stderr).strip() if result.returncode == 0 else None
            )
        else:
            data[command] = None
    return data


def _requested_output(argv: list[str]) -> OutputFormat:
    """Detect structured output early enough to format parser failures."""

    for index, argument in enumerate(argv[:-1]):
        if argument == "--output":
            try:
                return OutputFormat(argv[index + 1])
            except ValueError:
                return OutputFormat.TEXT

    for argument in argv:
        if not argument.startswith("--output="):
            continue
        try:
            return OutputFormat(argument.partition("=")[2])
        except ValueError:
            return OutputFormat.TEXT

    return OutputFormat.TEXT


def _command_label(args: argparse.Namespace) -> str:
    """Return the stable command label used in JSON envelopes."""

    command: str | None = args.command
    if command == "config":
        return f"config {args.config_command}"
    if command == "template":
        return f"template {args.template_command}"
    if command == "secrets":
        return f"secrets {args.secrets_command}"
    return command or "piw"


def _needs_loaded_config(args: argparse.Namespace) -> bool:
    """Return whether dispatch needs a valid configuration beforehand."""

    if args.command in {None, "init"}:
        return False
    if args.command != "config":
        return True
    if args.config_command == "validate":
        return True
    return args.config_command == "show" and bool(args.effective)


def _emit_error(command: str, output: OutputFormat, detail: ErrorDetail) -> None:
    """Render one command failure in the selected output format."""

    if output == OutputFormat.JSON:
        _emit_json(command, {}, ok=False, error=detail)
        return
    if output == OutputFormat.YAML:
        _emit_yaml(command, {}, ok=False, error=detail)
        return

    print(f"piw: {detail.message}", file=sys.stderr)
    if detail.hint:
        print(f"hint: {detail.hint}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Run piw and return a stable process exit code."""

    parser = build_parser()
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    output = _requested_output(actual_argv)
    command = "piw"

    try:
        args = parser.parse_args(actual_argv)
        output = args.output
        command = "version" if args.version else _command_label(args)
        runner = SubprocessRunner()

        if args.version:
            emit("version", _version_data(runner), output)
            return int(ExitCode.SUCCESS)

        config = (
            load_config(_active_config_path(args)) if _needs_loaded_config(args) else AppConfig()
        )
        service = PiwService(config, runner, StateStore())
        data, code = _dispatch(args, service, runner)

        emit(command, data, output, ok=code == ExitCode.SUCCESS)
        return int(code)
    except KeyboardInterrupt:
        detail = ErrorDetail("interrupted", "operation interrupted")
        _emit_error(command, output, detail)
        return int(ExitCode.INTERRUPTED)
    except PiwError as error:
        _emit_error(command, output, error.detail)
        return int(error.code)
    except subprocess.TimeoutExpired as error:
        detail = ErrorDetail("timeout", f"command timed out after {error.timeout} seconds")
        _emit_error(command, output, detail)
        return int(ExitCode.TIMEOUT)
    except OSError as error:
        detail = ErrorDetail("os_error", str(error))
        _emit_error(command, output, detail)
        return int(ExitCode.PREREQUISITE)


if __name__ == "__main__":
    raise SystemExit(main())
