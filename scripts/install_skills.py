#!/usr/bin/env python3
"""Install and validate the curated skills.

AI_CONTEXT:
  Use --output json for machine-readable results.
  Use --dry-run before installation.
  Exit code 0 means success. Exit code 1 means validation or installation failed.
"""

from __future__ import annotations

import argparse
import copy
from collections import deque
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MANAGED_SKILLS = [
    "abstraction-quality-audit",
    "application-security-review",
    "audit-codebase",
    "audit-tests",
    "clean-stale-worktrees",
    "code-quality-audit",
    "correctness-reliability-audit",
    "dead-code-audit",
    "dependency-auditor",
    "debug-and-reproduce",
    "design-for-change",
    "docs-sync",
    "explain-technical-choices",
    "file-hygiene-audit",
    "figma-implement-design",
    "frontend-design",
    "frontend-design-review",
    "monitored-luna-plc-execution",
    "monitored-opus-plc-execution",
    "monitored-sol-plc-execution",
    "monitored-sonnet-plc-execution",
    "performance-audit",
    "plain-english",
    "plain-language-audit",
    "plc-alignment-audit",
    "plc-execution",
    "plc-planning",
    "review-and-fix-plc",
    "release-readiness",
    "repo-navigation",
    "resolve-review-comments",
    "resume-after-crash",
    "start-this-up",
    "test-quality-audit",
    "verify-before-claiming",
    "visual-code-audit",
    "work-visual-summary",
    "wrap-this-up",
]

NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
LEGACY_BACKUP_RE = re.compile(
    r"^(?P<skill>[a-z0-9-]+)\.backup-(?P<timestamp>\d{8}-\d{6})(?:-\d+)?$"
)
INTERFACE_FIELD_RE = re.compile(
    r"^  (?P<key>display_name|short_description|default_prompt): (?P<value>.+)$"
)
POLICY_FIELD_RE = re.compile(r"^  allow_implicit_invocation: (?P<value>true|false)$")
PLAIN_SCALAR_FORBIDDEN_PREFIXES = (
    "- ",
    "? ",
    ": ",
    "{",
    "}",
    "[",
    "]",
    ",",
    "&",
    "*",
    "#",
    "!",
    "|",
    ">",
    "%",
    "@",
    "`",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_source() -> Path:
    return repo_root() / "skills"


def display_path(path: Path) -> str:
    return str(path.expanduser().absolute())


def parse_frontmatter(skill_md: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    lines = skill_md.read_text(encoding="utf-8").splitlines()

    if not lines or lines[0].strip() != "---":
        return {}, ["SKILL.md must start with YAML frontmatter"]

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, ["SKILL.md frontmatter must end with ---"]

    data: dict[str, Any] = {}
    frontmatter_lines = deque(lines[1:end_index])
    while frontmatter_lines:
        raw_line = frontmatter_lines.popleft()
        if not raw_line.strip():
            continue
        if raw_line[:1].isspace() or ":" not in raw_line:
            errors.append(f"unsupported frontmatter line: {raw_line!r}")
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in data:
            errors.append(f"duplicate frontmatter key: {key}")
            continue
        if key == "disable-model-invocation":
            if value not in {"true", "false"}:
                errors.append("disable-model-invocation must be a YAML boolean")
            else:
                data[key] = value == "true"
            continue
        if value in {">", ">-"}:
            # Upstream Ponytail uses a folded description. Keep the supported
            # metadata format narrow instead of accepting arbitrary YAML.
            if key != "description":
                errors.append(
                    f"folded frontmatter is only supported for description: {key}"
                )
                continue
            folded: list[str] = []
            while frontmatter_lines and (
                not frontmatter_lines[0].strip()
                or frontmatter_lines[0].startswith("  ")
            ):
                folded.append(frontmatter_lines.popleft().strip())
            value = " ".join(folded).strip()
            data[key] = value
            continue
        if value.startswith(("'", '"')) or value.endswith(("'", '"')):
            parsed_value = parse_quoted_scalar(value)
            if parsed_value is None:
                errors.append(f"frontmatter {key} must be a valid quoted string")
                continue
            value = parsed_value
        elif (
            value.startswith(PLAIN_SCALAR_FORBIDDEN_PREFIXES)
            or ": " in value
            or value.endswith(":")
            or " #" in value
        ):
            errors.append(f"frontmatter {key} is not a valid plain string")
            continue
        data[key] = value

    return data, errors


def parse_quoted_scalar(raw_value: str) -> str | None:
    if raw_value.startswith('"'):
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, str) else None

    if not raw_value.startswith("'") or not raw_value.endswith("'"):
        return None

    inner = raw_value[1:-1]
    if "'" in inner.replace("''", ""):
        return None
    return inner.replace("''", "'")


def parse_openai_interface(openai_yaml: Path) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    lines = openai_yaml.read_text(encoding="utf-8").splitlines()

    required = {"display_name", "short_description", "default_prompt"}
    section = ""
    interface_seen = False
    policy_seen = False
    implicit_invocation_seen = False
    for line in lines:
        if not line.strip():
            continue
        if line == "interface:":
            if interface_seen:
                errors.append("agents/openai.yaml contains duplicate interface:")
            interface_seen = True
            section = "interface"
            continue
        if line == "policy:":
            if policy_seen:
                errors.append("agents/openai.yaml contains duplicate policy:")
            policy_seen = True
            section = "policy"
            continue

        match = INTERFACE_FIELD_RE.fullmatch(line)
        if match:
            key = match.group("key")
            if key in fields:
                errors.append(f"agents/openai.yaml contains duplicate {key}")
                continue
            value = parse_quoted_scalar(match.group("value"))
            if value is None:
                errors.append(f"agents/openai.yaml {key} must be a valid quoted string")
                continue
            if section != "interface":
                errors.append(
                    f"agents/openai.yaml {key} must be nested under interface:"
                )
                continue
            fields[key] = value
            continue

        if POLICY_FIELD_RE.fullmatch(line):
            if implicit_invocation_seen:
                errors.append(
                    "agents/openai.yaml contains duplicate allow_implicit_invocation"
                )
            elif section != "policy":
                errors.append(
                    "agents/openai.yaml allow_implicit_invocation must be nested under policy:"
                )
            else:
                implicit_invocation_seen = True
                fields["allow_implicit_invocation"] = POLICY_FIELD_RE.fullmatch(
                    line
                ).group("value")
            continue

        errors.append(f"unsupported agents/openai.yaml line: {line!r}")

    if not interface_seen:
        errors.append("agents/openai.yaml is missing interface:")

    for key in sorted(required - set(fields)):
        errors.append(f"agents/openai.yaml is missing {key}")

    return fields, errors


def validate_skill(
    source: Path, name: str, *, external: bool = False
) -> dict[str, Any]:
    skill_dir = source / name
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    errors: list[str] = []

    if not skill_dir.is_dir():
        return {"skill": name, "valid": False, "errors": ["skill directory is missing"]}

    if not skill_md.is_file():
        errors.append("SKILL.md is missing")
        frontmatter: dict[str, Any] = {}
    else:
        frontmatter, frontmatter_errors = parse_frontmatter(skill_md)
        errors.extend(frontmatter_errors)

    supported = {"name", "description", "disable-model-invocation", "model"}
    if external:
        supported.update({"license", "argument-hint"})
    unexpected = sorted(set(frontmatter) - supported)
    if unexpected:
        errors.append(f"unexpected frontmatter keys: {', '.join(unexpected)}")
    if "model" in frontmatter and not frontmatter["model"].strip():
        errors.append("frontmatter model must be a nonempty model alias or ID")

    actual_name = frontmatter.get("name", "")
    if actual_name != name:
        errors.append(f"frontmatter name must be {name!r}, got {actual_name!r}")
    if actual_name and not NAME_RE.match(actual_name):
        errors.append(
            "frontmatter name must contain only lowercase letters, digits, and hyphens"
        )
    if actual_name.startswith("-") or actual_name.endswith("-") or "--" in actual_name:
        errors.append(
            "frontmatter name cannot start/end with hyphen or contain consecutive hyphens"
        )

    description = frontmatter.get("description", "")
    if not description:
        errors.append("frontmatter description is required")
    if len(description) > 1024:
        errors.append("frontmatter description must be 1024 characters or fewer")
    if "<" in description or ">" in description:
        errors.append("frontmatter description cannot contain angle brackets")

    if not openai_yaml.is_file() and not external:
        errors.append("agents/openai.yaml is missing")
    elif openai_yaml.is_file():
        interface, interface_errors = parse_openai_interface(openai_yaml)
        errors.extend(interface_errors)
        short_description = interface.get("short_description", "")
        if short_description and not 25 <= len(short_description) <= 64:
            errors.append("short_description must contain 25 to 64 characters")
        default_prompt = interface.get("default_prompt", "")
        skill_token = re.compile(rf"\${re.escape(name)}(?![a-z0-9-])")
        if default_prompt and not skill_token.search(default_prompt):
            errors.append(
                f"default_prompt must mention ${name} as an exact skill token"
            )
        if not external:
            explicit_only = interface.get("allow_implicit_invocation") == "false"
            portable_explicit_only = frontmatter.get("disable-model-invocation", False)
            if explicit_only != portable_explicit_only:
                errors.append(
                    "explicit-only invocation must agree between agents/openai.yaml and disable-model-invocation"
                )

    return {"skill": name, "valid": not errors, "errors": errors}


def dependency_manifest(source: Path) -> dict[str, Any]:
    """Custom sources remain offline and independent of this repository."""
    if source.resolve() != default_source().resolve():
        return {}
    path = repo_root() / "agent-dependencies.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported agent dependency manifest schema")
    return data


def external_cache() -> Path:
    return repo_root() / ".tools" / "external-skills"


def external_specs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for spec in manifest.get("external_skills", []):
        name = spec.get("name", "")
        if (
            not NAME_RE.fullmatch(name)
            or name.startswith("-")
            or name.endswith("-")
            or "--" in name
        ):
            raise ValueError(f"invalid external skill name: {name!r}")
        if name in specs or name in MANAGED_SKILLS:
            raise ValueError(f"duplicate skill ownership: {name}")
        for field in (
            "url",
            "sha256",
            "commit",
            "license",
            "license_url",
            "license_sha256",
        ):
            if not isinstance(spec.get(field), str) or not spec[field]:
                raise ValueError(f"{name}: missing external skill {field}")
        for field in ("sha256", "license_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", spec[field]):
                raise ValueError(f"{name}: invalid {field}")
        if not re.fullmatch(r"[0-9a-f]{40}", spec["commit"]):
            raise ValueError(f"{name}: source must use a full pinned commit")
        for field in ("url", "license_url"):
            parsed = urllib.parse.urlparse(spec[field])
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or spec["commit"] not in parsed.path
            ):
                raise ValueError(
                    f"{name}: {field} must use HTTPS and the pinned commit"
                )
        specs[name] = spec
    return specs


def pinned_external_errors(path: Path, spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for filename, field in (("SKILL.md", "sha256"), ("LICENSE", "license_sha256")):
        file = path / filename
        if not file.is_file():
            errors.append(f"required external {filename} is missing")
        elif hashlib.sha256(file.read_bytes()).hexdigest() != spec[field]:
            errors.append(f"external {filename} checksum does not match pinned source")
    return errors


def download_pinned(url: str, expected_hash: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("external skill download exceeds 2 MB")
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError(f"external download checksum mismatch: {url}")
    return data


def refresh_external_specs(manifest: dict[str, Any]) -> dict[str, Any]:
    """Resolve each GitHub default branch once and record immutable payload hashes."""
    refreshed = copy.deepcopy(manifest)
    commits: dict[str, str] = {}
    for name, spec in external_specs(refreshed).items():
        repository = spec.get("repository", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError(f"{name}: refresh requires a GitHub owner/repository")
        if repository not in commits:
            result = subprocess.run(
                ["git", "ls-remote", f"https://github.com/{repository}.git", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )
            commit = result.stdout.split()[0] if result.stdout.split() else ""
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError(f"{repository}: could not resolve upstream HEAD")
            commits[repository] = commit
        old_prefix = f"https://raw.githubusercontent.com/{repository}/{spec['commit']}/"
        new_prefix = (
            f"https://raw.githubusercontent.com/{repository}/{commits[repository]}/"
        )
        for field, hash_field in (("url", "sha256"), ("license_url", "license_sha256")):
            if not spec[field].startswith(old_prefix):
                raise ValueError(f"{name}: {field} does not match its GitHub source")
            spec[field] = new_prefix + spec[field][len(old_prefix) :]
            with urllib.request.urlopen(spec[field], timeout=30) as response:
                payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError(f"{name}: upstream payload exceeds 2 MB")
            spec[hash_field] = hashlib.sha256(payload).hexdigest()
        spec["commit"] = commits[repository]
    return refreshed


def prepare_external_skills(manifest: dict[str, Any], destination: Path) -> Path:
    """Verify every upstream payload before publishing it into the local cache."""
    specs = external_specs(manifest)
    payloads: dict[str, tuple[bytes, bytes]] = {}
    for name, spec in specs.items():
        cached = external_cache() / name
        if not pinned_external_errors(cached, spec):
            payloads[name] = (
                (cached / "SKILL.md").read_bytes(),
                (cached / "LICENSE").read_bytes(),
            )
        else:
            payloads[name] = (
                download_pinned(spec["url"], spec["sha256"]),
                download_pinned(spec["license_url"], spec["license_sha256"]),
            )
    for name, (skill, license_bytes) in payloads.items():
        spec = specs[name]
        path = destination / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_bytes(skill)
        (path / "LICENSE").write_bytes(license_bytes)
        (path / "SOURCE.json").write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return destination


def markdown_reference_errors(skill_dir: Path, bundle: dict[str, Path]) -> list[str]:
    errors: list[str] = []
    link = re.compile(r"\[[^\]]+\]\((?:<([^>]+)>|([^\s)]+))[^)]*\)")
    for file in sorted(skill_dir.rglob("*.md")):
        fence: str | None = None
        for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            marker = re.match(r"^\s*(`{3,}|~{3,})", line)
            if marker:
                if fence is None:
                    fence = marker.group(1)[0]
                elif marker.group(1)[0] == fence:
                    fence = None
                continue
            if fence is not None:
                continue
            # Inline code can show Markdown syntax without creating a link.
            prose = re.sub(r"(`+).*?\1", "", line)
            for match in link.finditer(prose):
                target = match.group(1) or match.group(2)
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith(
                    ("#", "/", "~")
                ):
                    continue
                target = urllib.parse.unquote(target.split("#", 1)[0].split("?", 1)[0])
                if not target or re.search(r"[<>{}$]|\.\.\.|(?:^|/)path/to/", target):
                    continue
                # Every source root is installed under one shared skills
                # directory, including external roots cached elsewhere.
                parent = posixpath.join(
                    skill_dir.name, file.parent.relative_to(skill_dir).as_posix()
                )
                installed_reference = posixpath.normpath(
                    posixpath.join(parent, target.replace("\\", "/"))
                )
                parts = installed_reference.split("/")
                owner = parts[0]
                relative = file.relative_to(skill_dir).as_posix()
                if owner not in bundle:
                    errors.append(
                        f"{relative}:{number}: local Markdown reference is outside the installed skill bundle: {target!r}"
                    )
                elif not bundle[owner].joinpath(*parts[1:]).exists():
                    errors.append(
                        f"{relative}:{number}: missing local Markdown reference {target!r}"
                    )
    return errors


def validate_source(
    source: Path,
    *,
    manifest: dict[str, Any] | None = None,
    external_source: Path | None = None,
) -> dict[str, Any]:
    manifest = dependency_manifest(source) if manifest is None else manifest
    specs = external_specs(manifest)
    external_source = external_cache() if external_source is None else external_source
    bundle = {name: source / name for name in MANAGED_SKILLS}
    bundle.update({name: external_source / name for name in specs})
    skills = [validate_skill(source, name) for name in MANAGED_SKILLS]
    for skill in skills:
        skill["errors"].extend(
            markdown_reference_errors(source / skill["skill"], bundle)
        )
        skill["valid"] = not skill["errors"]
    for name, spec in specs.items():
        skill = validate_skill(external_source, name, external=True)
        skill["errors"].extend(pinned_external_errors(external_source / name, spec))
        skill["errors"].extend(
            markdown_reference_errors(external_source / name, bundle)
        )
        skill["valid"] = not skill["errors"]
        skills.append(skill)
    errors = [
        f"{skill['skill']}: {error}" for skill in skills for error in skill["errors"]
    ]
    available = {skill["skill"] for skill in skills if skill["valid"]}
    declared = set(MANAGED_SKILLS) | set(specs)
    for owner, dependencies in manifest.get("skill_dependencies", {}).items():
        if owner not in declared:
            errors.append(f"dependency owner is not managed: {owner}")
        if not isinstance(dependencies, list) or any(
            not isinstance(name, str) for name in dependencies
        ):
            errors.append(f"{owner}: skill dependencies must be a list of names")
            continue
        for name in dependencies:
            if name not in declared:
                errors.append(
                    f"{owner}: required skill dependency is not declared: {name}"
                )
            elif name not in available:
                errors.append(
                    f"{owner}: required skill dependency is missing or invalid: {name}"
                )
    return {
        "command": "validate",
        "source": display_path(source),
        "valid": not errors,
        "skills": skills,
        "dependencies": manifest.get("skill_dependencies", {}),
        "errors": errors,
    }


def resolve_targets(args: argparse.Namespace) -> dict[str, Path]:
    home = Path.home()
    codex_dir = (
        Path(args.codex_dir).expanduser()
        if args.codex_dir
        else Path(os.environ["CODEX_SKILLS_DIR"]).expanduser()
        if os.environ.get("CODEX_SKILLS_DIR")
        else Path(os.environ["CODEX_HOME"]).expanduser() / "skills"
        if os.environ.get("CODEX_HOME")
        else home / ".codex" / "skills"
        if (home / ".codex" / "skills").exists()
        else home / ".agents" / "skills"
    )
    claude_dir = (
        Path(args.claude_dir).expanduser()
        if args.claude_dir
        else Path(os.environ["CLAUDE_SKILLS_DIR"]).expanduser()
        if os.environ.get("CLAUDE_SKILLS_DIR")
        else home / ".claude" / "skills"
    )
    pi_dir = (
        Path(args.pi_dir).expanduser()
        if args.pi_dir
        else Path(os.environ["PI_SKILLS_DIR"]).expanduser()
        if os.environ.get("PI_SKILLS_DIR")
        else home / ".pi" / "agent" / "skills"
    )
    opencode_dir = (
        Path(args.opencode_dir).expanduser()
        if args.opencode_dir
        else Path(os.environ["OPENCODE_SKILLS_DIR"]).expanduser()
        if os.environ.get("OPENCODE_SKILLS_DIR")
        else home / ".config" / "opencode" / "skills"
    )
    return {
        "codex": codex_dir,
        "claude": claude_dir,
        "pi": pi_dir,
        "opencode": opencode_dir,
    }


def selected_targets(targets: dict[str, Path], selected: str) -> dict[str, Path]:
    if selected == "all":
        return targets
    return {selected: targets[selected]}


def digest_path(path: Path) -> str | None:
    if not path.exists():
        return None

    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()

    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path)
        if "__pycache__" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")

    return digest.hexdigest()


def backup_root(target_dir: Path) -> Path:
    return target_dir.parent / "skill-backups"


def staging_root(target_dir: Path) -> Path:
    return target_dir.parent / ".skill-staging"


def next_available_path(base: Path) -> Path:
    if not base.exists():
        return base
    for counter in range(2, 1000):
        candidate = base.with_name(f"{base.name}-{counter}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find a free path for {base}")


def remove_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        if current == stop:
            break
        current = current.parent


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def rollback_skill(result: dict[str, Any], timestamp: str, target_name: str) -> None:
    action = result["action"]
    if action not in {"created", "updated"}:
        return

    destination = Path(result["destination"])
    backup = Path(result["backup"]) if result["backup"] else None
    errors: list[str] = []

    if destination.exists():
        failed_path = next_available_path(
            backup_root(destination.parent)
            / timestamp
            / target_name
            / f"{destination.name}.failed"
        )
        try:
            failed_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(failed_path))
        except Exception as error:
            try:
                remove_path(destination)
            except Exception as cleanup_error:
                errors.append(f"could not quarantine failed installation: {error}")
                errors.append(f"could not clear failed installation: {cleanup_error}")

    if action == "updated" and backup:
        if destination.exists():
            errors.append(
                "could not restore backup because the destination still exists"
            )
        elif not backup.exists():
            errors.append(f"backup is missing: {backup}")
        else:
            try:
                shutil.move(str(backup), str(destination))
                if digest_path(destination) != result["destination_digest_before"]:
                    errors.append(
                        "restored backup digest does not match the prior installation"
                    )
            except Exception as error:
                errors.append(f"could not restore backup: {error}")

    if errors:
        raise RuntimeError("; ".join(errors))


def archive_legacy_backups(
    target_name: str,
    target_dir: Path,
    dry_run: bool,
    managed_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not target_dir.is_dir():
        return []

    results: list[dict[str, Any]] = []
    managed = set(MANAGED_SKILLS if managed_names is None else managed_names)
    for candidate in sorted(target_dir.iterdir()):
        if not candidate.is_dir():
            continue
        match = LEGACY_BACKUP_RE.fullmatch(candidate.name)
        if not match or match.group("skill") not in managed:
            continue

        skill_name = match.group("skill")
        timestamp = match.group("timestamp")
        destination = next_available_path(
            backup_root(target_dir) / timestamp / target_name / skill_name
        )
        source_digest = digest_path(candidate)
        action = "would_archive" if dry_run else "archived"
        archived_digest = None
        verified = False

        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate), str(destination))
            archived_digest = digest_path(destination)
            verified = source_digest == archived_digest
            if not verified:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(candidate))
                raise RuntimeError(f"legacy backup digest mismatch for {candidate}")

        results.append(
            {
                "skill": skill_name,
                "source": display_path(candidate),
                "destination": display_path(destination),
                "action": action,
                "source_digest": source_digest,
                "archived_digest": archived_digest,
                "verified": verified if not dry_run else None,
            }
        )

    return results


def install_skill(
    source_skill: Path,
    destination: Path,
    target_name: str,
    dry_run: bool,
    timestamp: str,
    run_id: str,
) -> dict[str, Any]:
    source_digest = digest_path(source_skill)
    destination_digest = digest_path(destination)
    backup_path: Path | None = None

    # A legacy symlinked install matches its source by digest; replace it with a
    # managed copy so every target holds the same kind of install.
    if destination_digest == source_digest and not destination.is_symlink():
        action = "would_skip" if dry_run else "skipped"
    elif destination.exists() or destination.is_symlink():
        backup_path = next_available_path(
            backup_root(destination.parent) / timestamp / target_name / destination.name
        )
        action = "would_update" if dry_run else "updated"
    else:
        action = "would_create" if dry_run else "created"

    if dry_run or action == "skipped":
        return {
            "skill": source_skill.name,
            "source": display_path(source_skill),
            "destination": display_path(destination),
            "action": action,
            "backup": display_path(backup_path) if backup_path else None,
            "source_digest": source_digest,
            "destination_digest_before": destination_digest,
            "installed_digest": destination_digest,
            "verified": None if dry_run else destination_digest == source_digest,
        }

    stage_base = (
        staging_root(destination.parent) / run_id / target_name / source_skill.name
    )
    stage_path = next_available_path(stage_base)
    previous_moved = False
    promotion_attempted = False

    try:
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_skill, stage_path)
        if digest_path(stage_path) != source_digest:
            raise RuntimeError(f"staged skill digest mismatch for {source_skill.name}")

        if destination.exists() or destination.is_symlink():
            if backup_path is None:
                raise RuntimeError(f"backup path is missing for {destination}")
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(backup_path))
            previous_moved = True

        destination.parent.mkdir(parents=True, exist_ok=True)
        promotion_attempted = True
        stage_path.rename(destination)
        installed_digest = digest_path(destination)
        if installed_digest != source_digest:
            raise RuntimeError(
                f"installed skill digest mismatch for {source_skill.name}"
            )
    except Exception as error:
        if previous_moved or promotion_attempted:
            rollback_result = {
                "action": "updated" if previous_moved else "created",
                "destination": display_path(destination),
                "backup": display_path(backup_path) if backup_path else None,
                "destination_digest_before": destination_digest,
            }
            try:
                rollback_skill(rollback_result, timestamp, target_name)
            except Exception as rollback_error:
                raise RuntimeError(
                    f"installation failed for {source_skill.name}: {error}; "
                    f"rollback failed: {rollback_error}"
                ) from error
        raise
    finally:
        if stage_path.exists():
            shutil.rmtree(stage_path)
        remove_empty_parents(stage_path.parent, staging_root(destination.parent))

    return {
        "skill": source_skill.name,
        "source": display_path(source_skill),
        "destination": display_path(destination),
        "action": action,
        "backup": display_path(backup_path) if backup_path else None,
        "source_digest": source_digest,
        "destination_digest_before": destination_digest,
        "installed_digest": installed_digest,
        "verified": installed_digest == source_digest,
    }


def install_skills(
    source: Path,
    targets: dict[str, Path],
    dry_run: bool,
    *,
    manifest: dict[str, Any] | None = None,
    external_source: Path | None = None,
) -> dict[str, Any]:
    manifest = dependency_manifest(source) if manifest is None else manifest
    external_source = external_cache() if external_source is None else external_source
    validation = validate_source(
        source, manifest=manifest, external_source=external_source
    )
    if not validation["valid"]:
        raise ValueError(
            "skill validation failed before installation: "
            + "; ".join(validation["errors"])
        )
    sources = {name: source / name for name in MANAGED_SKILLS}
    sources.update({name: external_source / name for name in external_specs(manifest)})
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"{timestamp}-{os.getpid()}-{time.time_ns()}"
    target_results: dict[str, Any] = {}

    completed: list[tuple[str, dict[str, Any]]] = []
    try:
        for target_name, target_dir in targets.items():
            legacy_backups = archive_legacy_backups(
                target_name, target_dir, dry_run, list(sources)
            )
            skills: list[dict[str, Any]] = []
            for skill_name, source_skill in sources.items():
                result = install_skill(
                    source_skill,
                    target_dir / skill_name,
                    target_name,
                    dry_run,
                    timestamp,
                    run_id,
                )
                skills.append(result)
                if not dry_run and result["action"] in {"created", "updated"}:
                    completed.append((target_name, result))

            target_results[target_name] = {
                "target_dir": display_path(target_dir),
                "backup_root": display_path(backup_root(target_dir)),
                "legacy_backups": legacy_backups,
                "skills": skills,
            }
    except Exception as error:
        rollback_errors: list[str] = []
        for completed_target, result in reversed(completed):
            try:
                rollback_skill(result, timestamp, completed_target)
            except Exception as rollback_error:
                rollback_errors.append(f"{result['skill']}: {rollback_error}")
        if rollback_errors:
            raise RuntimeError(
                f"installation failed: {error}; transaction rollback failed: "
                + "; ".join(rollback_errors)
            ) from error
        raise

    return {
        "command": "install",
        "dry_run": dry_run,
        "source": display_path(source),
        "timestamp": timestamp,
        "targets": target_results,
    }


def list_skills(source: Path, targets: dict[str, Path]) -> dict[str, Any]:
    return {
        "command": "list",
        "source": display_path(source),
        "managed_skills": MANAGED_SKILLS,
        "external_skills": list(external_specs(dependency_manifest(source))),
        "targets": {
            name: {
                "skills_dir": display_path(path),
                "backup_root": display_path(backup_root(path)),
            }
            for name, path in targets.items()
        },
    }


def emit(result: dict[str, Any], output: str) -> None:
    if output == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    command = result["command"]
    if command == "list":
        print(f"Source: {result['source']}")
        print("Targets:")
        for name, target in result["targets"].items():
            print(f"  {name}: {target['skills_dir']}")
            print(f"    backups: {target['backup_root']}")
        print("Skills:")
        for skill in result["managed_skills"]:
            print(f"  {skill}")
        for skill in result["external_skills"]:
            print(f"  {skill} (pinned external dependency)")
        return

    if command == "fetch":
        prefix = "Dry run: " if result["dry_run"] else ""
        print(
            f"{prefix}verified pinned external skill payloads: {', '.join(result['skills'])}"
        )
        return

    if command == "validate":
        if result["valid"]:
            print(f"Validated {len(result['skills'])} skills in {result['source']}")
        else:
            print("Validation failed:")
            for error in result["errors"]:
                print(f"  {error}")
        return

    if command == "install":
        prefix = "Dry run: " if result["dry_run"] else ""
        print(f"{prefix}source {result['source']}")
        for target_name, target in result["targets"].items():
            print(f"{target_name}: {target['target_dir']}")
            for legacy in target["legacy_backups"]:
                print(f"  {legacy['action']}: {Path(legacy['source']).name}")
            for skill in target["skills"]:
                line = f"  {skill['action']}: {skill['skill']}"
                if skill["backup"]:
                    line += f" (backup: {skill['backup']})"
                if skill["verified"] is not None:
                    line += f" verified={str(skill['verified']).lower()}"
                print(line)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install and validate the curated skills.",
        epilog=(
            "AI_CONTEXT: Use --output json for parsing. Use --dry-run before "
            "installation. Exit code 0 means success. Exit code 1 means failure."
        ),
    )
    parser.add_argument(
        "--command", choices=["list", "fetch", "validate", "install"], default="install"
    )
    parser.add_argument(
        "--target", choices=["all", "codex", "claude", "pi", "opencode"], default="all"
    )
    parser.add_argument("--source", default=str(default_source()))
    parser.add_argument("--codex-dir")
    parser.add_argument("--claude-dir")
    parser.add_argument("--pi-dir")
    parser.add_argument("--opencode-dir")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--locked",
        action="store_true",
        help="Install recorded external skill commits without checking upstream.",
    )
    parser.add_argument("--output", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    source = Path(args.source).expanduser()
    targets = selected_targets(resolve_targets(args), args.target)

    try:
        if args.command == "list":
            emit(list_skills(source, targets), args.output)
            return 0

        manifest = dependency_manifest(source)
        if (
            args.command == "install"
            and not args.locked
            and manifest.get("external_skills")
        ):
            manifest = refresh_external_specs(manifest)
        if args.command in {"fetch", "install"} and manifest.get("external_skills"):
            if args.dry_run:
                with tempfile.TemporaryDirectory(
                    prefix="llms-external-skills-"
                ) as workspace:
                    external_source = prepare_external_skills(manifest, Path(workspace))
                    validation = validate_source(
                        source, manifest=manifest, external_source=external_source
                    )
                    if not validation["valid"]:
                        emit(validation, args.output)
                        return 1
                    if args.command == "fetch":
                        emit(
                            {
                                "command": "fetch",
                                "dry_run": True,
                                "skills": list(external_specs(manifest)),
                            },
                            args.output,
                        )
                    else:
                        result = install_skills(
                            source,
                            targets,
                            True,
                            manifest=manifest,
                            external_source=external_source,
                        )
                        emit(result, args.output)
                    return 0
            prepare_external_skills(manifest, external_cache())

        validation = validate_source(source, manifest=manifest)
        if args.command == "fetch":
            if not validation["valid"]:
                emit(validation, args.output)
                return 1
            emit(
                {
                    "command": "fetch",
                    "dry_run": args.dry_run,
                    "skills": list(external_specs(manifest)),
                },
                args.output,
            )
            return 0
        if args.command == "validate":
            emit(validation, args.output)
            return 0 if validation["valid"] else 1

        if not validation["valid"]:
            emit(validation, args.output)
            return 1

        result = install_skills(source, targets, args.dry_run, manifest=manifest)
        if not args.dry_run and manifest and not args.locked:
            (repo_root() / "agent-dependencies.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
        emit(result, args.output)
        return 0
    except Exception as error:
        failure = {"command": args.command, "error": str(error)}
        if args.output == "json":
            print(json.dumps(failure, indent=2, sort_keys=True))
        else:
            print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
