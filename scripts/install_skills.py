#!/usr/bin/env python3
"""Install and validate the curated skills.

AI_CONTEXT:
  Use --output json for machine-readable results.
  Use --dry-run before installation.
  Exit code 0 means success. Exit code 1 means validation or installation failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any


MANAGED_SKILLS = [
    "abstraction-quality-audit",
    "audit-codebase",
    "audit-tests",
    "code-quality-audit",
    "correctness-reliability-audit",
    "dead-code-audit",
    "dependency-auditor",
    "docs-sync",
    "figma-implement-design",
    "frontend-design",
    "frontend-design-review",
    "performance-audit",
    "plain-language-audit",
    "plc-planning",
    "release-readiness",
    "test-quality-audit",
    "visual-code-audit",
]

NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
LEGACY_BACKUP_RE = re.compile(
    r"^(?P<skill>[a-z0-9-]+)\.backup-(?P<timestamp>\d{8}-\d{6})(?:-\d+)?$"
)
INTERFACE_FIELD_RE = re.compile(
    r"^  (?P<key>display_name|short_description|default_prompt): (?P<value>.+)$"
)
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


def parse_frontmatter(skill_md: Path) -> tuple[dict[str, str], list[str]]:
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

    data: dict[str, str] = {}
    for raw_line in lines[1:end_index]:
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
    interface_seen = False
    for line in lines:
        if not line.strip():
            continue
        if line == "interface:":
            if interface_seen:
                errors.append("agents/openai.yaml contains duplicate interface:")
            interface_seen = True
            continue

        match = INTERFACE_FIELD_RE.fullmatch(line)
        if not match:
            errors.append(f"unsupported agents/openai.yaml line: {line!r}")
            continue
        key = match.group("key")
        if key in fields:
            errors.append(f"agents/openai.yaml contains duplicate {key}")
            continue
        value = parse_quoted_scalar(match.group("value"))
        if value is None:
            errors.append(f"agents/openai.yaml {key} must be a valid quoted string")
            continue
        if not interface_seen:
            errors.append(f"agents/openai.yaml {key} must be nested under interface:")
            continue
        fields[key] = value

    if not interface_seen:
        errors.append("agents/openai.yaml is missing interface:")

    for key in sorted(required - set(fields)):
        errors.append(f"agents/openai.yaml is missing {key}")

    return fields, errors


def validate_skill(source: Path, name: str) -> dict[str, Any]:
    skill_dir = source / name
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    errors: list[str] = []

    if not skill_dir.is_dir():
        return {"skill": name, "valid": False, "errors": ["skill directory is missing"]}

    if not skill_md.is_file():
        errors.append("SKILL.md is missing")
        frontmatter: dict[str, str] = {}
    else:
        frontmatter, frontmatter_errors = parse_frontmatter(skill_md)
        errors.extend(frontmatter_errors)

    unexpected = sorted(set(frontmatter) - {"name", "description"})
    if unexpected:
        errors.append(f"unexpected frontmatter keys: {', '.join(unexpected)}")

    actual_name = frontmatter.get("name", "")
    if actual_name != name:
        errors.append(f"frontmatter name must be {name!r}, got {actual_name!r}")
    if actual_name and not NAME_RE.match(actual_name):
        errors.append("frontmatter name must contain only lowercase letters, digits, and hyphens")
    if actual_name.startswith("-") or actual_name.endswith("-") or "--" in actual_name:
        errors.append("frontmatter name cannot start/end with hyphen or contain consecutive hyphens")

    description = frontmatter.get("description", "")
    if not description:
        errors.append("frontmatter description is required")
    if len(description) > 1024:
        errors.append("frontmatter description must be 1024 characters or fewer")
    if "<" in description or ">" in description:
        errors.append("frontmatter description cannot contain angle brackets")

    if not openai_yaml.is_file():
        errors.append("agents/openai.yaml is missing")
    else:
        interface, interface_errors = parse_openai_interface(openai_yaml)
        errors.extend(interface_errors)
        short_description = interface.get("short_description", "")
        if short_description and not 25 <= len(short_description) <= 64:
            errors.append("short_description must contain 25 to 64 characters")
        default_prompt = interface.get("default_prompt", "")
        skill_token = re.compile(rf"\${re.escape(name)}(?![a-z0-9-])")
        if default_prompt and not skill_token.search(default_prompt):
            errors.append(f"default_prompt must mention ${name} as an exact skill token")

    return {"skill": name, "valid": not errors, "errors": errors}


def validate_source(source: Path) -> dict[str, Any]:
    skills = [validate_skill(source, name) for name in MANAGED_SKILLS]
    errors = [
        f"{skill['skill']}: {error}"
        for skill in skills
        for error in skill["errors"]
    ]
    return {
        "command": "validate",
        "source": display_path(source),
        "valid": not errors,
        "skills": skills,
        "errors": errors,
    }


def resolve_targets(args: argparse.Namespace) -> dict[str, Path]:
    home = Path.home()
    codex_dir = (
        Path(args.codex_dir).expanduser()
        if args.codex_dir
        else Path(os.environ["CODEX_SKILLS_DIR"]).expanduser()
        if os.environ.get("CODEX_SKILLS_DIR")
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
    return {"codex": codex_dir, "claude": claude_dir, "pi": pi_dir}


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
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
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
            errors.append("could not restore backup because the destination still exists")
        elif not backup.exists():
            errors.append(f"backup is missing: {backup}")
        else:
            try:
                shutil.move(str(backup), str(destination))
                if digest_path(destination) != result["destination_digest_before"]:
                    errors.append("restored backup digest does not match the prior installation")
            except Exception as error:
                errors.append(f"could not restore backup: {error}")

    if errors:
        raise RuntimeError("; ".join(errors))


def archive_legacy_backups(
    target_name: str,
    target_dir: Path,
    dry_run: bool,
) -> list[dict[str, Any]]:
    if not target_dir.is_dir():
        return []

    results: list[dict[str, Any]] = []
    managed = set(MANAGED_SKILLS)
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

    if destination_digest == source_digest:
        action = "would_skip" if dry_run else "skipped"
    elif destination.exists():
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

        if destination.exists():
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
            raise RuntimeError(f"installed skill digest mismatch for {source_skill.name}")
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
) -> dict[str, Any]:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"{timestamp}-{os.getpid()}-{time.time_ns()}"
    target_results: dict[str, Any] = {}

    completed: list[tuple[str, dict[str, Any]]] = []
    try:
        for target_name, target_dir in targets.items():
            legacy_backups = archive_legacy_backups(target_name, target_dir, dry_run)
            skills: list[dict[str, Any]] = []
            for skill_name in MANAGED_SKILLS:
                result = install_skill(
                    source / skill_name,
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
    parser.add_argument("--command", choices=["list", "validate", "install"], default="install")
    parser.add_argument("--target", choices=["all", "codex", "claude", "pi"], default="all")
    parser.add_argument("--source", default=str(default_source()))
    parser.add_argument("--codex-dir")
    parser.add_argument("--claude-dir")
    parser.add_argument("--pi-dir")
    parser.add_argument("--dry-run", action="store_true")
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

        validation = validate_source(source)
        if args.command == "validate":
            emit(validation, args.output)
            return 0 if validation["valid"] else 1

        if not validation["valid"]:
            emit(validation, args.output)
            return 1

        result = install_skills(source, targets, args.dry_run)
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
