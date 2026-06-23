#!/usr/bin/env python3
"""Install and validate the curated audit skills.

AI_CONTEXT:
  Use --output json for machine-readable results.
  Use --dry-run before installing to preview target changes.
  Exit code 0 means success; 1 means validation or installation failed.
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
    "audit-tests",
    "code-quality-audit",
    "dead-code-audit",
    "dependency-auditor",
    "test-quality-audit",
    "visual-code-audit",
]

NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_source() -> Path:
    return repo_root() / "skills"


def display_path(path: Path) -> str:
    return str(path.resolve())


def parse_frontmatter(skill_md: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()

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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        data[key] = value

    return data, errors


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
        openai_text = openai_yaml.read_text(encoding="utf-8")
        for required in ["interface:", "display_name:", "short_description:", "default_prompt:"]:
            if required not in openai_text:
                errors.append(f"agents/openai.yaml is missing {required}")
        if f"${name}" not in openai_text:
            errors.append(f"agents/openai.yaml default_prompt must mention ${name}")

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
    return {"codex": codex_dir, "claude": claude_dir}


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


def next_backup_path(destination: Path, timestamp: str) -> Path:
    base = destination.with_name(f"{destination.name}.backup-{timestamp}")
    if not base.exists():
        return base
    for counter in range(2, 1000):
        candidate = destination.with_name(f"{destination.name}.backup-{timestamp}-{counter}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find free backup path for {destination}")


def copy_skill(source_skill: Path, destination: Path, dry_run: bool, timestamp: str) -> dict[str, Any]:
    source_digest = digest_path(source_skill)
    destination_digest = digest_path(destination)
    backup_path: Path | None = None

    if destination_digest == source_digest:
        action = "would_skip" if dry_run else "skipped"
    elif destination.exists():
        backup_path = next_backup_path(destination, timestamp)
        action = "would_update" if dry_run else "updated"
    else:
        action = "would_create" if dry_run else "created"

    if not dry_run and action in {"created", "updated"}:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if backup_path is None:
                raise RuntimeError(f"backup path was not computed for {destination}")
            shutil.move(str(destination), str(backup_path))
        shutil.copytree(source_skill, destination)

    return {
        "skill": source_skill.name,
        "source": display_path(source_skill),
        "destination": display_path(destination),
        "action": action,
        "backup": display_path(backup_path) if backup_path else None,
    }


def install_skills(source: Path, targets: dict[str, Path], dry_run: bool) -> dict[str, Any]:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    target_results: dict[str, Any] = {}

    for target_name, target_dir in targets.items():
        skills = []
        for skill_name in MANAGED_SKILLS:
            skills.append(copy_skill(source / skill_name, target_dir / skill_name, dry_run, timestamp))
        target_results[target_name] = {
            "target_dir": display_path(target_dir),
            "skills": skills,
        }

    return {
        "command": "install",
        "dry_run": dry_run,
        "source": display_path(source),
        "targets": target_results,
    }


def list_skills(source: Path, targets: dict[str, Path]) -> dict[str, Any]:
    return {
        "command": "list",
        "source": display_path(source),
        "managed_skills": MANAGED_SKILLS,
        "targets": {name: display_path(path) for name, path in targets.items()},
    }


def emit(result: dict[str, Any], output: str) -> None:
    if output == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    command = result["command"]
    if command == "list":
        print(f"Source: {result['source']}")
        print("Targets:")
        for name, path in result["targets"].items():
            print(f"  {name}: {path}")
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
            for skill in target["skills"]:
                line = f"  {skill['action']}: {skill['skill']}"
                if skill["backup"]:
                    line += f" (backup: {skill['backup']})"
                print(line)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install and validate curated audit skills.",
        epilog=(
            "AI_CONTEXT: Use --output json for parsing. Use --dry-run before "
            "installation. Exit code 0 means success; 1 means validation or "
            "installation failed."
        ),
    )
    parser.add_argument("--command", choices=["list", "validate", "install"], default="install")
    parser.add_argument("--target", choices=["all", "codex", "claude"], default="all")
    parser.add_argument("--source", default=str(default_source()))
    parser.add_argument("--codex-dir")
    parser.add_argument("--claude-dir")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    source = Path(args.source).expanduser()
    targets = selected_targets(resolve_targets(args), args.target)

    try:
        if args.command == "list":
            result = list_skills(source, targets)
            emit(result, args.output)
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
    except Exception as exc:
        error = {"command": args.command, "error": str(exc)}
        if args.output == "json":
            print(json.dumps(error, indent=2, sort_keys=True))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
