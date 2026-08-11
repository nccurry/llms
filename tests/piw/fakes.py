"""Deterministic command runner used by piw service tests."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from piw.models import CommandResult


def _calls() -> list[tuple[str, ...]]:
    return []


def _string_dict() -> dict[str, str]:
    return {}


def _string_set() -> set[str]:
    return set()


@dataclass(slots=True)
class ScenarioRunner:
    """Small in-memory model of the Git and sbx commands piw invokes."""

    repo: Path
    calls: list[tuple[str, ...]] = field(default_factory=_calls)
    sandboxes: dict[str, str] = field(default_factory=_string_dict)
    templates: set[str] = field(default_factory=_string_set)
    registered_mcp: set[str] = field(default_factory=_string_set)
    host_clean: bool = True
    sandbox_dirty: bool = False
    head_commit: str = "a" * 40
    upstream_exists: bool = True
    ahead: int = 0
    rev_list_error: bool = False
    snapshot_error: bool = False
    create_error: bool = False
    pi_config_error: str | None = None
    seeded_files: dict[str, str] = field(default_factory=_string_dict)
    executables: set[str] = field(default_factory=lambda: {"git", "sbx", "uv"})
    sandbox_list_output: str | None = None

    def which(self, command: str) -> str | None:
        """Return a stable fake executable path."""

        return f"/usr/bin/{command}" if command in self.executables else None

    @staticmethod
    def _result(
        argv: tuple[str, ...],
        *,
        code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> CommandResult:
        return CommandResult(argv, code, stdout, stderr, 0.01)

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
        interactive: bool = False,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Interpret the subset of Git and sbx used by piw."""

        del cwd, interactive, timeout_seconds, env
        self.calls.append(argv)
        if argv[0] == "git":
            return self._host_git(argv)
        if argv[:2] == ("sbx", "version"):
            return self._result(argv, stdout="sbx version: v0.test\n")
        if argv[:4] == ("sbx", "create", "shell", "--help"):
            return self._result(argv, stdout="--clone --profile --static-mcp")
        if argv[:3] == ("sbx", "ls", "--json"):
            if self.sandbox_list_output is not None:
                return self._result(argv, stdout=self.sandbox_list_output)
            values = [
                {
                    "name": name,
                    "status": status,
                    "profile": "developer",
                    "workspaces": [str(self.repo)],
                }
                for name, status in sorted(self.sandboxes.items())
            ]
            return self._result(argv, stdout=json.dumps({"sandboxes": values}))
        if argv[:4] == ("sbx", "template", "ls", "--json"):
            images: list[dict[str, str]] = []
            for index, reference in enumerate(sorted(self.templates)):
                repository, tag = reference.rsplit(":", 1)
                images.append(
                    {
                        "id": f"image-{index}",
                        "repository": f"docker.io/library/{repository}",
                        "tag": tag,
                    }
                )
            return self._result(argv, stdout=json.dumps({"images": images}))
        if argv[:3] == ("sbx", "mcp", "inspect"):
            return self._result(argv, code=0 if argv[3] in self.registered_mcp else 1)
        if argv[:2] == ("sbx", "create"):
            name = argv[argv.index("--name") + 1]
            self.sandboxes[name] = "running"
            return self._result(
                argv,
                code=1 if self.create_error else 0,
                stdout=name,
                stderr="create failed" if self.create_error else "",
            )
        if argv[:2] == ("sbx", "exec"):
            return self._sandbox_exec(argv, input_text)
        if argv[:2] == ("sbx", "cp"):
            return self._result(
                argv,
                code=1 if self.snapshot_error else 0,
                stderr="snapshot failed" if self.snapshot_error else "",
            )
        if argv[:2] == ("sbx", "stop"):
            self.sandboxes[argv[2]] = "stopped"
            return self._result(argv)
        if argv[:3] == ("sbx", "rm", "--force"):
            self.sandboxes.pop(argv[3], None)
            return self._result(argv)
        if argv[:3] == ("sbx", "template", "save"):
            self.templates.add(argv[4])
            return self._result(argv)
        if argv[:3] == ("sbx", "template", "rm"):
            self.templates.discard(argv[3])
            return self._result(argv)
        return self._result(argv, code=1, stderr=f"unexpected command: {argv}")

    def _host_git(self, argv: tuple[str, ...]) -> CommandResult:
        if argv[-2:] == ("rev-parse", "--show-toplevel"):
            return self._result(argv, stdout=f"{self.repo}\n")
        if "status" in argv:
            return self._result(argv, stdout="dirty\n" if not self.host_clean else "")
        if "check-ref-format" in argv:
            valid = ".." not in argv[-1] and not any(part.isspace() for part in argv[-1])
            return self._result(argv, code=0 if valid else 1)
        if "rev-parse" in argv:
            return self._result(argv, stdout=f"{self.head_commit}\n")
        return self._result(argv)

    @staticmethod
    def _exec_parts(argv: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
        index = 2
        flags_with_values = {"--workdir", "--user", "--env", "--env-file"}
        while index < len(argv) and argv[index].startswith("-"):
            flag = argv[index]
            index += 2 if flag in flags_with_values else 1
        return argv[index], argv[index + 1 :]

    def _sandbox_exec(self, argv: tuple[str, ...], input_text: str | None) -> CommandResult:
        sandbox, command = self._exec_parts(argv)
        if sandbox not in self.sandboxes:
            return self._result(argv, code=1, stderr="sandbox missing")
        self.sandboxes[sandbox] = "running"
        if command[:2] == ("git", "switch"):
            return self._result(argv)
        if command[:2] == ("git", "status"):
            return self._result(argv, stdout="dirty\n" if self.sandbox_dirty else "")
        if command[:3] == ("git", "rev-parse", "HEAD"):
            return self._result(argv, stdout=f"{self.head_commit}\n")
        if command[:3] == ("git", "rev-parse", "--verify"):
            return self._result(
                argv,
                code=0 if self.upstream_exists else 1,
                stdout=f"{'b' * 40}\n" if self.upstream_exists else "",
            )
        if command[:2] == ("git", "rev-list"):
            return self._result(
                argv,
                code=1 if self.rev_list_error else 0,
                stdout="" if self.rev_list_error else f"{self.ahead}\n",
                stderr="count failed" if self.rev_list_error else "",
            )
        if command[:2] == ("pi", "--list-models"):
            return self._result(argv, stderr=self.pi_config_error or "")
        if command[:2] == ("sh", "-lc") and "cat >" in command[2]:
            filename = command[2].split("/")[-1].rstrip('"')
            self.seeded_files[filename] = input_text or ""
            return self._result(argv)
        if command[:2] == ("sh", "-lc") and "settings.json" in command[2]:
            return self._result(argv, stdout='{"packages":["existing"]}')
        if command and command[0] in {"bash", "pi", "true", "sh", "printf"}:
            return self._result(argv, stdout="ok\n")
        return self._result(argv, stdout="command output\n")
