"""Command-line interface for piw."""

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn, cast

from piw import __version__
from piw.config import (
    config_as_object,
    default_config_path,
    default_config_text,
    load_config,
    state_home,
)
from piw.errors import ErrorDetail, ExitCode, PiwError
from piw.models import AppConfig, OutputEnvelope, OutputFormat, ThinkingLevel
from piw.process import SubprocessRunner
from piw.service import PiwService, normalize_task_name
from piw.state import StateStore

_AI_CONTEXT = """
AI_CONTEXT:
  Use --output json for stable machine-readable output.
  Use --dry-run before mutating or destructive operations.
  Use --batch or --yes to avoid interactive prompts.
  Use --timeout to bound sandbox and template operations.
  Exit 0 is success; 10-16 are piw failures; 20 is a failed piw exec command.
"""


class PiwArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports usage failures through piw's error model."""

    def error(self, message: str) -> NoReturn:
        """Raise a typed usage error instead of exiting immediately."""

        raise PiwError(message, code=ExitCode.USAGE, kind="invalid_usage", hint=self.format_usage())


def _common_parser(*, suppress_defaults: bool = False) -> PiwArgumentParser:
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
        help="Select human-readable text or stable JSON output.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS if suppress_defaults else False,
        help="Disable terminal color output.",
    )
    return parser


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_parser() -> PiwArgumentParser:
    """Build the complete public command tree."""

    common = _common_parser(suppress_defaults=True)
    parser = PiwArgumentParser(
        prog="piw",
        description="Run persistent Pi coding-agent tasks in isolated Docker Sandboxes.",
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
        help="Check host, sandbox, model, skill, and MCP readiness.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor.add_argument(
        "--live", action="store_true", help="Create and remove a live probe sandbox."
    )
    doctor.add_argument(
        "--timeout", type=_positive_int, default=120, help="Live-probe timeout in seconds."
    )

    start = commands.add_parser(
        "start",
        parents=[common],
        help="Create a private task clone and start Pi.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    start.add_argument("task", help="Human-readable task name.")
    start.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository path.")
    start.add_argument("--base", help="Base revision; defaults to the current HEAD.")
    start.add_argument("--branch", help="Task branch; defaults to piw/<task>.")
    start.add_argument(
        "--ref", action="append", type=Path, default=[], help="Read-only reference path."
    )
    start.add_argument(
        "--skill", action="append", type=Path, default=[], help="Read-only Pi skill path."
    )
    start.add_argument("--model", help="Pi model in provider/model form.")
    start.add_argument("--thinking", choices=tuple(ThinkingLevel), type=ThinkingLevel)
    start.add_argument(
        "--mcp", action="append", default=[], help="Registered sbx MCP server alias."
    )
    start.add_argument("--profile", help="Docker Sandbox governance profile.")
    start.add_argument(
        "--extension", action="append", default=[], help="Pinned Pi extension package."
    )
    start.add_argument("--models-file", type=Path, help="Non-secret Pi models metadata.")
    start.add_argument("--settings-file", type=Path, help="Non-secret Pi settings metadata.")
    start.add_argument("--batch", action="store_true", help="Create the task without attaching Pi.")
    start.add_argument("--dry-run", action="store_true", help="Preview without creating anything.")
    start.add_argument("--timeout", type=_positive_int, help="Creation timeout in seconds.")

    resume = commands.add_parser(
        "resume",
        parents=[common],
        help="Continue the latest Pi session for a task.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    resume.add_argument("task")
    resume.add_argument(
        "--timeout", type=_positive_int, default=120, help="Sandbox startup timeout in seconds."
    )

    commands.add_parser("list", parents=[common], help="List tracked tasks and sandbox state.")

    status = commands.add_parser("status", parents=[common], help="Show detailed task status.")
    status.add_argument("task")

    shell = commands.add_parser("shell", parents=[common], help="Open a task sandbox shell.")
    shell.add_argument("task")
    shell.add_argument("--cwd", type=Path, help="Sandbox working directory.")

    execute = commands.add_parser(
        "exec",
        parents=[common],
        help="Run a captured command in a task sandbox.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    execute.add_argument("task")
    execute.add_argument("--cwd", type=Path, help="Sandbox working directory.")
    execute.add_argument("exec_command", nargs=argparse.REMAINDER, metavar="COMMAND")

    stop = commands.add_parser("stop", parents=[common], help="Stop a task without deleting it.")
    stop.add_argument("task")
    stop.add_argument("--dry-run", action="store_true")
    stop.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")

    clean = commands.add_parser(
        "clean",
        parents=[common],
        help="Safely remove a task sandbox.",
        epilog=_AI_CONTEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    clean.add_argument("task")
    clean.add_argument("--dry-run", action="store_true")
    clean.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    clean.add_argument("--force", action="store_true", help="Discard dirty or unpushed work.")

    config = commands.add_parser("config", help="Inspect or edit user configuration.")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("path", parents=[common], help="Print the active config path.")
    show = config_commands.add_parser(
        "show", parents=[common], help="Show stored or effective config."
    )
    show.add_argument("--effective", action="store_true")
    config_commands.add_parser("validate", parents=[common], help="Validate the active config.")
    config_commands.add_parser("edit", parents=[common], help="Edit the active config.")

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

    return parser


def _confirm(prompt: str, *, approved: bool, dry_run: bool) -> None:
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
    return {"kind": detail.kind, "message": detail.message, "hint": detail.hint}


def _emit_json(command: str, data: object, *, ok: bool, error: ErrorDetail | None = None) -> None:
    envelope = OutputEnvelope(
        schema_version=1,
        command=command,
        ok=ok,
        data=data,
        error=_error_object(error) if error else None,
    )
    print(json.dumps(envelope.to_json_object(), indent=2, sort_keys=True))


def _text_scalar(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, sort_keys=True, default=str)


def _emit_text(data: object) -> None:
    if isinstance(data, str):
        print(data)
    elif isinstance(data, list):
        items = cast("list[object]", data)
        if not items:
            print("No results.")
        elif all(isinstance(item, dict) for item in items):
            for item in items:
                mapping = cast("dict[object, object]", item)
                print("  ".join(f"{key}={_text_scalar(value)}" for key, value in mapping.items()))
        else:
            for item in items:
                print(_text_scalar(item))
    elif isinstance(data, dict):
        for key, value in cast("dict[object, object]", data).items():
            print(f"{key}: {_text_scalar(value)}")
    else:
        print(_text_scalar(data))


def emit(command: str, data: object, output: OutputFormat, *, ok: bool = True) -> None:
    """Emit command output with an explicit success status."""

    if output == OutputFormat.JSON:
        _emit_json(command, data, ok=ok)
    else:
        _emit_text(data)


def _active_config_path(args: argparse.Namespace) -> Path:
    value: Path | None = getattr(args, "config", None)
    return (value or default_config_path()).expanduser()


def _init(args: argparse.Namespace) -> dict[str, object]:
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
        (state_home() / "tasks").mkdir(mode=0o700, parents=True, exist_ok=True)
    return {"path": str(path), "action": f"would_{action}" if args.dry_run else action}


def _edit_config(args: argparse.Namespace, runner: SubprocessRunner) -> dict[str, object]:
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


def _dispatch(
    args: argparse.Namespace, service: PiwService, runner: SubprocessRunner
) -> tuple[object, int]:
    command = args.command
    if command == "init":
        return _init(args), ExitCode.SUCCESS
    if command == "doctor":
        checks = service.doctor(live=args.live, timeout_seconds=args.timeout)
        data = [asdict(check) for check in checks]
        failed = any(check.status == "fail" for check in checks)
        return data, ExitCode.PREREQUISITE if failed else ExitCode.SUCCESS
    if command == "start":
        task_config = service.effective_task_config(
            repo_candidate=args.repo,
            base_ref=args.base,
            branch=args.branch,
            refs=tuple(path.expanduser().resolve(strict=False) for path in args.ref),
            skills=tuple(path.expanduser().resolve(strict=False) for path in args.skill),
            model=args.model,
            thinking=args.thinking,
            mcp_servers=tuple(args.mcp),
            profile=args.profile,
            extensions=tuple(args.extension),
            models_file=args.models_file.expanduser().resolve(strict=False)
            if args.models_file
            else None,
            settings_file=args.settings_file.expanduser().resolve(strict=False)
            if args.settings_file
            else None,
            timeout_seconds=args.timeout,
            task=args.task,
        )
        return (
            service.start(
                task=args.task, task_config=task_config, batch=args.batch, dry_run=args.dry_run
            ),
            ExitCode.SUCCESS,
        )
    if command == "resume":
        return service.resume(args.task, timeout_seconds=args.timeout), ExitCode.SUCCESS
    if command == "list":
        return service.list_tasks(), ExitCode.SUCCESS
    if command == "status":
        return service.status(args.task), ExitCode.SUCCESS
    if command == "shell":
        service.shell(args.task, cwd=args.cwd)
        return {"task": normalize_task_name(args.task), "action": "shell_closed"}, ExitCode.SUCCESS
    if command == "exec":
        exec_command = tuple(args.exec_command)
        if exec_command and exec_command[0] == "--":
            exec_command = exec_command[1:]
        data = service.execute(args.task, exec_command, cwd=args.cwd)
        code = ExitCode.SUCCESS if data["returncode"] == 0 else ExitCode.COMMAND
        return data, code
    if command == "stop":
        _confirm(f"Stop task {args.task!r}?", approved=args.yes, dry_run=args.dry_run)
        return service.stop(args.task, dry_run=args.dry_run), ExitCode.SUCCESS
    if command == "clean":
        _confirm(
            f"Remove task {args.task!r} and its sandbox?",
            approved=args.yes,
            dry_run=args.dry_run,
        )
        return service.clean(args.task, dry_run=args.dry_run, force=args.force), ExitCode.SUCCESS
    if command == "config":
        path = _active_config_path(args)
        if args.config_command == "path":
            return str(path), ExitCode.SUCCESS
        if args.config_command == "show":
            if args.effective:
                return config_as_object(load_config(path)), ExitCode.SUCCESS
            if not path.exists():
                return {"path": str(path), "exists": False, "content": ""}, ExitCode.SUCCESS
            return {
                "path": str(path),
                "exists": True,
                "content": path.read_text(encoding="utf-8"),
            }, ExitCode.SUCCESS
        if args.config_command == "validate":
            parsed = load_config(path)
            return {
                "path": str(path),
                "valid": True,
                "config_version": parsed.config_version,
            }, ExitCode.SUCCESS
        if args.config_command == "edit":
            return _edit_config(args, runner), ExitCode.SUCCESS
    if command == "template":
        if args.template_command == "status":
            return service.template_status(), ExitCode.SUCCESS
        if args.template_command == "ensure":
            return service.ensure_template(
                dry_run=args.dry_run, timeout_seconds=args.timeout
            ), ExitCode.SUCCESS
        if args.template_command == "rebuild":
            _confirm("Rebuild the reusable Pi template?", approved=args.yes, dry_run=args.dry_run)
            return service.ensure_template(
                force=True,
                dry_run=args.dry_run,
                timeout_seconds=args.timeout,
            ), ExitCode.SUCCESS
        if args.template_command == "prune":
            _confirm("Remove obsolete piw templates?", approved=args.yes, dry_run=args.dry_run)
            return service.prune_templates(dry_run=args.dry_run), ExitCode.SUCCESS
    raise PiwError(
        "a command is required",
        code=ExitCode.USAGE,
        kind="missing_command",
        hint="Run 'piw --help'.",
    )


def _version_data(runner: SubprocessRunner) -> dict[str, object]:
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
    """Detect JSON output early enough to format parser failures."""

    for index, argument in enumerate(argv[:-1]):
        if argument == "--output" and argv[index + 1] == OutputFormat.JSON:
            return OutputFormat.JSON
    if any(argument == "--output=json" for argument in argv):
        return OutputFormat.JSON
    return OutputFormat.TEXT


def _command_label(args: argparse.Namespace) -> str:
    """Return the stable command label used in JSON envelopes."""

    command: str | None = args.command
    if command == "config":
        return f"config {args.config_command}"
    if command == "template":
        return f"template {args.template_command}"
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
        if output == OutputFormat.JSON:
            _emit_json(command, {}, ok=False, error=detail)
        else:
            print(f"piw: {detail.message}", file=sys.stderr)
        return int(ExitCode.INTERRUPTED)
    except PiwError as error:
        if output == OutputFormat.JSON:
            _emit_json(command, {}, ok=False, error=error.detail)
        else:
            print(f"piw: {error.detail.message}", file=sys.stderr)
            if error.detail.hint:
                print(f"hint: {error.detail.hint}", file=sys.stderr)
        return int(error.code)
    except subprocess.TimeoutExpired as error:
        detail = ErrorDetail("timeout", f"command timed out after {error.timeout} seconds")
        if output == OutputFormat.JSON:
            _emit_json(command, {}, ok=False, error=detail)
        else:
            print(f"piw: {detail.message}", file=sys.stderr)
        return int(ExitCode.TIMEOUT)
    except OSError as error:
        detail = ErrorDetail("os_error", str(error))
        if output == OutputFormat.JSON:
            _emit_json(command, {}, ok=False, error=detail)
        else:
            print(f"piw: {detail.message}", file=sys.stderr)
        return int(ExitCode.PREREQUISITE)


if __name__ == "__main__":
    raise SystemExit(main())
