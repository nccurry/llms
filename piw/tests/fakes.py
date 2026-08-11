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


def _strings() -> list[str]:
    return []


def _custom_secrets() -> dict[str, tuple[str, tuple[str, ...]]]:
    return {}


@dataclass(slots=True)
class ScenarioRunner:
    """Small in-memory model of the Git and sbx commands piw invokes."""

    repo: Path
    calls: list[tuple[str, ...]] = field(default_factory=_calls)
    sandboxes: dict[str, str] = field(default_factory=_string_dict)
    templates: set[str] = field(default_factory=_string_set)
    host_clean: bool = True
    host_conflicts: tuple[str, ...] = ()
    host_patch: str = ""
    host_patch_paths: tuple[str, ...] = ()
    applied_host_patches: list[str] = field(default_factory=_strings)
    host_patch_apply_error: bool = False
    local_branches: dict[str, str] = field(default_factory=_string_dict)
    remote_branches: dict[str, str] = field(default_factory=_string_dict)
    branch_upstreams: dict[str, str] = field(default_factory=_string_dict)
    remotes: tuple[str, ...] = ("origin",)
    sandbox_upstreams: dict[str, str] = field(default_factory=_string_dict)
    upstream_copy_error: bool = False
    upstream_config_error: bool = False
    sandbox_dirty: bool = False
    head_commit: str = "a" * 40
    upstream_exists: bool = True
    ahead: int = 0
    rev_list_error: bool = False
    snapshot_error: bool = False
    create_error: bool = False
    secret_error: bool = False
    pi_config_error: str | None = None
    pi_exit_code: int = 0
    seeded_files: dict[str, str] = field(default_factory=_string_dict)
    custom_secrets: dict[str, tuple[str, tuple[str, ...]]] = field(default_factory=_custom_secrets)
    secret_inputs: list[str] = field(default_factory=_strings)
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
            return self._result(argv, stdout="--clone --profile")
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
        if argv[:4] == ("sbx", "secret", "ls", "--global"):
            lines = [
                f"global {' '.join(hosts)} {sandbox_env} {placeholder} ********"
                for sandbox_env, (placeholder, hosts) in sorted(self.custom_secrets.items())
            ]
            return self._result(argv, stdout="\n".join(lines))
        if argv[:3] == ("sbx", "secret", "set-custom"):
            if self.secret_error:
                return self._result(argv, code=1, stderr="secret write failed")
            sandbox_env = argv[argv.index("--env") + 1]
            placeholder = argv[argv.index("--placeholder") + 1]
            hosts = tuple(argv[index + 1] for index, part in enumerate(argv) if part == "--host")
            self.custom_secrets[sandbox_env] = (placeholder, hosts)
            self.secret_inputs.append((input_text or "").rstrip("\n"))
            return self._result(argv, stdout="secret configured\n")
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
            if self.host_conflicts:
                status = "".join(f"UU {path}\0" for path in self.host_conflicts)
                return self._result(argv, stdout=status)
            if not self.host_clean:
                return self._result(argv, stdout="?? host-change.txt\0")
            return self._result(argv)
        if "check-ref-format" in argv:
            valid = (
                bool(argv[-1])
                and ".." not in argv[-1]
                and not argv[-1].endswith("/")
                and not any(part.isspace() for part in argv[-1])
            )
            return self._result(argv, code=0 if valid else 1)
        if "show-ref" in argv:
            full_ref = argv[-1]
            exists = (
                full_ref.removeprefix("refs/heads/") in self.local_branches
                if full_ref.startswith("refs/heads/")
                else full_ref.removeprefix("refs/remotes/") in self.remote_branches
            )
            return self._result(argv, code=0 if exists else 1)
        if argv[-1] == "remote":
            return self._result(argv, stdout="".join(f"{remote}\n" for remote in self.remotes))
        if "for-each-ref" in argv:
            branch = argv[-1].removeprefix("refs/heads/")
            upstream = self.branch_upstreams.get(branch, "")
            if "--format=%(upstream)" in argv:
                if not upstream:
                    return self._result(argv)
                prefix = "refs/remotes" if "/" in upstream else "refs/heads"
                return self._result(argv, stdout=f"{prefix}/{upstream}\n")
            return self._result(argv, stdout=f"{upstream}\n" if upstream else "")
        if "rev-parse" in argv:
            if argv[-2:] == ("--git-path", "objects"):
                return self._result(argv, stdout=f"{self.repo / '.git' / 'objects'}\n")
            ref = argv[-1].removesuffix("^{commit}")
            commit = self.head_commit
            if ref.startswith("refs/heads/"):
                commit = self.local_branches.get(ref.removeprefix("refs/heads/"), commit)
            elif ref.startswith("refs/remotes/"):
                commit = self.remote_branches.get(ref.removeprefix("refs/remotes/"), commit)
            return self._result(argv, stdout=f"{commit}\n")
        if "diff" in argv and "--name-only" in argv:
            return self._result(
                argv,
                stdout="".join(f"{path}\0" for path in self.host_patch_paths),
            )
        if "diff" in argv and "--binary" in argv:
            return self._result(argv, stdout=self.host_patch)
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
        if command[:2] == ("git", "fetch"):
            return self._result(
                argv,
                code=1 if self.upstream_copy_error else 0,
                stderr="upstream copy failed" if self.upstream_copy_error else "",
            )
        if command[:2] == ("git", "branch"):
            self.sandbox_upstreams[command[-1]] = command[-2]
            return self._result(
                argv,
                code=1 if self.upstream_config_error else 0,
                stderr="upstream failed" if self.upstream_config_error else "",
            )
        if command[:2] == ("git", "apply"):
            self.applied_host_patches.append(input_text or "")
            return self._result(
                argv,
                code=1 if self.host_patch_apply_error else 0,
                stderr="patch does not apply" if self.host_patch_apply_error else "",
            )
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
        if command and command[0] == "pi":
            return self._result(
                argv,
                code=self.pi_exit_code,
                stderr="Pi failed" if self.pi_exit_code else "",
            )
        if command[:2] == ("sh", "-lc") and "cat >" in command[2]:
            filename = command[2].split("/")[-1].rstrip('"')
            self.seeded_files[filename] = input_text or ""
            return self._result(argv)
        if command[:2] == ("sh", "-lc") and "settings.json" in command[2]:
            return self._result(argv, stdout='{"packages":["existing"]}')
        if command and command[0] in {"bash", "true", "sh", "printf"}:
            return self._result(argv, stdout="ok\n")
        return self._result(argv, stdout="command output\n")
