"""Find the pinned PowerShell for the tests that need it, and parse scripts with it.

Imported by tests/test_windows_branches.py and tests/test_powershell_runners.py. It is not a test
module itself.
"""

import base64
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The PowerShell that `task deps:dev-tools` installs, in its own mise data directory.
INSTALLS = ROOT / ".tools/lint-mise/data/installs/powershell"

# Parses a script without running it and prints the value of each word on its command line.
# Windows writes console output in the OEM code page unless told otherwise; the caller reads UTF-8.
PARSE_COMMAND_WORDS = """
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$errors = $null
$tree = [System.Management.Automation.Language.Parser]::ParseInput(
    $env:LLMS_TEST_SCRIPT, [ref] $null, [ref] $errors)
if ($errors.Count -gt 0) { [Console]::Error.WriteLine($errors[0].Message); exit 1 }
$isCommand = { param($node) $node -is [System.Management.Automation.Language.CommandAst] }
$command = $tree.Find($isCommand, $true)
ConvertTo-Json -Compress @($command.CommandElements | ForEach-Object { $_.Value })
"""


def runs(pwsh):
    """Say whether this PowerShell starts and exits 0."""
    try:
        result = subprocess.run(
            [str(pwsh), "-NoProfile", "-NonInteractive", "-Command", "exit 0"],
            check=False,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def find_pwsh():
    """Return the pinned PowerShell, else a `pwsh` on PATH, if it runs; otherwise None."""
    candidates = [*sorted(INSTALLS.glob("*/pwsh")), *sorted(INSTALLS.glob("*/pwsh.exe"))]
    on_path = shutil.which("pwsh")
    if on_path:
        candidates.append(Path(on_path))
    return next((str(path) for path in candidates if runs(path)), None)


def require_pwsh(test):
    """Return PowerShell for a test, skipping it when missing; `check` sets the variable to fail."""
    pwsh = find_pwsh()
    if pwsh is None:
        if os.environ.get("LLMS_REQUIRE_PINNED_TOOLS"):
            test.fail("PowerShell is missing; run `task deps:dev-tools`.")
        raise unittest.SkipTest(
            "PowerShell is not installed; run `task deps:dev-tools` to check this."
        )
    return pwsh


def parse_command_words(pwsh, script):
    """Return the words of the command in `script`, as PowerShell's own parser reads them."""
    encoded = base64.b64encode(PARSE_COMMAND_WORDS.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        check=False,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "LLMS_TEST_SCRIPT": script},
        timeout=60,
    )
    if result.returncode:
        message = f"PowerShell could not parse {script!r}: {result.stderr}"
        raise AssertionError(message)
    return json.loads(result.stdout)
