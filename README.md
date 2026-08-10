# LLM Skills

This repository is the source for the managed Codex, Claude, and Pi skills in `skills/`.

## Commands

List the managed skills and install targets:

```powershell
task skills:list
```

Run the installer tests and skill validation:

```powershell
task skills:test
task skills:validate
```

Preview a Codex installation before you change live skills:

```powershell
task skills:dry-run:codex
```

Install the managed skills for Codex:

```powershell
task skills:install:codex
```

Preview or install the managed skills for Pi:

```powershell
task skills:dry-run:pi
task skills:install:pi
```

Use `task skills:dry-run` or `task skills:install` only when you want every target.

## Installation Behavior

The installer validates the complete managed source before it changes a target. It stages each skill and compares its source digest with the staged digest.

When a live skill changes, the installer moves the old copy to an external backup directory. Codex backups use `~/.codex/skill-backups/<timestamp>/codex/`. Claude backups use `~/.claude/skill-backups/<timestamp>/claude/`. Pi backups use `~/.pi/agent/skill-backups/<timestamp>/pi/`.

The installer also moves managed legacy `*.backup-*` directories out of each skill discovery directory. This migration prevents an agent from discovering duplicate skill names.

If promotion fails, the installer restores the prior live skill. Use `--output json` to record actions, backup paths, digests, and verification results.

## Direct Usage

The PowerShell wrapper selects an available Python runtime:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_install_skills.ps1 --command install --target pi --dry-run --output json
```

Pi installs to `~/.pi/agent/skills` by default. Set `CODEX_SKILLS_DIR`, `CLAUDE_SKILLS_DIR`, or `PI_SKILLS_DIR` to override a default target. You can also use `--codex-dir`, `--claude-dir`, or `--pi-dir`.
