"""The Windows-only branches of the setup script, checked on any host.

The setup script chooses its Windows commands by testing `os.name == "nt"`. Patching
`os.name` itself would break pathlib, so these tests give the script a stand-in for its `os`
module that says "nt" and passes every other attribute to the real one.
"""

import base64
import importlib.util
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "manage_agent_tools_windows", ROOT / "scripts/manage_agent_tools.py"
)
assert spec is not None and spec.loader is not None
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

# The quoting examples from the plan (FIX-007): spaces, a typographic apostrophe (U+2019) and
# ASCII single quotes.
NODE = "C:/Program Files/Tools/node.exe"
REPOSITORY = "C:/Users/O\u2019Brien/My 'Repos'/llms"
HOME = "C:/Users/O\u2019Brien"
SYSTEM_ROOT = "C:/Windows"
POWERSHELL_5 = f"{SYSTEM_ROOT}/System32/WindowsPowerShell/v1.0/powershell.exe"

# Parses a script without running it and prints the value of each word on its command line.
PARSE_SCRIPT = """
$errors = $null
$tree = [System.Management.Automation.Language.Parser]::ParseInput(
    $env:LLMS_TEST_SCRIPT, [ref] $null, [ref] $errors)
if ($errors.Count -gt 0) { [Console]::Error.WriteLine($errors[0].Message); exit 1 }
$isCommand = { param($node) $node -is [System.Management.Automation.Language.CommandAst] }
$command = $tree.Find($isCommand, $true)
ConvertTo-Json -Compress @($command.CommandElements | ForEach-Object { $_.Value })
"""


class WindowsOs:
    """The `os` module, except that `name` is "nt"."""

    name = "nt"

    def __getattr__(self, attribute):
        return getattr(os, attribute)


def find_pwsh():
    """Return the pinned PowerShell from `deps:dev-tools`, or any pwsh on PATH, or None."""
    installed = sorted((ROOT / ".tools/mise/data/installs/powershell").glob("*/pwsh*"))
    candidates = [str(path) for path in installed if path.name in {"pwsh", "pwsh.exe"}]
    on_path = shutil.which("pwsh")
    return (candidates or [on_path])[0] if candidates or on_path else None


def parse_words(pwsh, script):
    """Return the words of the command in `script`, as PowerShell parses them."""
    encoded = base64.b64encode(PARSE_SCRIPT.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        check=False,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "LLMS_TEST_SCRIPT": script},
        timeout=60,
    )
    if result.returncode:
        raise AssertionError(f"PowerShell could not parse {script!r}: {result.stderr}")
    return json.loads(result.stdout)


class WindowsBranchTests(unittest.TestCase):
    def setUp(self):
        patches = [
            patch.object(setup, "os", WindowsOs()),
            patch.dict(os.environ, {"SystemRoot": SYSTEM_ROOT}),
            patch.object(setup, "ROOT", Path(REPOSITORY)),
            patch.object(setup, "TOOLS", Path(REPOSITORY) / ".tools/agent-tools"),
            patch.object(Path, "home", return_value=Path(HOME)),
            patch.object(setup, "node_command", return_value=NODE),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)

    def test_codex_serena_hook_is_one_cmd_command_line_with_quoted_spaces(self):
        with patch.object(setup, "TOOLS", Path("C:/Program Files/Tools")):
            hook = setup.serena_hook("codex", "activate")
        self.assertEqual(
            hook["command"],
            '"C:/Program Files/Tools/bin/serena-hooks.exe" activate --client=codex',
        )
        self.assertEqual(hook["type"], "command")
        self.assertNotIn("args", hook)

    def test_claude_serena_hook_keeps_the_command_and_arguments_apart(self):
        with patch.object(setup, "TOOLS", Path("C:/Program Files/Tools")):
            hook = setup.serena_hook("claude", "remind")
        self.assertEqual(hook["command"], "C:/Program Files/Tools/bin/serena-hooks.exe")
        self.assertEqual(hook["args"], ["remind", "--client=claude-code"])

    def gitnexus_codex_launch(self):
        entry = f"{REPOSITORY}/.tools/agent-tools/npm/node_modules/gitnexus/dist/cli/index.js"
        with patch.object(setup, "tool_command", return_value=[NODE, entry]):
            return setup.gitnexus_hook_launch("codex"), entry

    def expected_words(self, entry):
        return [
            NODE,
            f"{REPOSITORY}/scripts/run_gitnexus_hook.mjs",
            f"{REPOSITORY}/.tools/agent-tools/gitnexus-indexes",
            f"{HOME}/.codex/hooks/gitnexus/gitnexus-hook.cjs",
            entry,
        ]

    def encoded_script(self, launch):
        prefix = f"{POWERSHELL_5} -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand "
        self.assertTrue(launch["commandWindows"].startswith(prefix), launch["commandWindows"])
        encoded = launch["commandWindows"][len(prefix) :]
        return base64.b64decode(encoded, validate=True).decode("utf-16-le")

    def test_gitnexus_command_windows_doubles_every_quote_character(self):
        launch, entry = self.gitnexus_codex_launch()
        words = self.expected_words(entry)
        script = self.encoded_script(launch)
        # U+2019 and the ASCII quotes are each doubled, and every word is quoted.
        self.assertEqual(
            script,
            "& "
            + " ".join(
                "'" + word.replace("'", "''").replace("\u2019", "\u2019\u2019") + "'"
                for word in words
            ),
        )
        self.assertIn("O\u2019\u2019Brien/My ''Repos''/llms", script)

    def test_gitnexus_command_windows_parses_back_to_the_exact_paths(self):
        pwsh = find_pwsh()
        if pwsh is None:
            if os.environ.get("LLMS_REQUIRE_PINNED_TOOLS"):
                self.fail("PowerShell is missing; run `task deps:dev-tools`.")
            self.skipTest("PowerShell is not installed; run `task deps:dev-tools` to check this.")
        launch, entry = self.gitnexus_codex_launch()
        words = parse_words(pwsh, self.encoded_script(launch))
        self.assertEqual(words, self.expected_words(entry))

    def test_every_powershell_single_quote_character_is_doubled(self):
        for quote in ("'", "\u2018", "\u2019", "\u201a", "\u201b"):
            with self.subTest(quote=quote):
                self.assertEqual(setup.powershell_quote(f"a{quote}b"), f"'a{quote}{quote}b'")

    def test_claude_gitnexus_hook_is_a_plain_command_and_arguments(self):
        entry = f"{REPOSITORY}/cli.js"
        with patch.object(setup, "tool_command", return_value=[NODE, entry]):
            launch = setup.gitnexus_hook_launch("claude")
        self.assertEqual(launch["command"], NODE)
        self.assertEqual(launch["args"][-1], entry)
        self.assertNotIn("commandWindows", launch)

    def test_private_permissions_runs_the_script_through_windows_powershell(self):
        calls = []
        with patch.object(setup, "run", side_effect=lambda *args, **kwargs: calls.append(args)):
            setup.private_permissions(Path("C:/Users/O\u2019Brien/.codex/config.toml"))
            setup.private_permissions(
                Path("C:/Users/O\u2019Brien/.codex/config.toml"),
                copy_from=Path("C:/Users/O\u2019Brien/.codex/config.toml.bak"),
            )
        base = [
            POWERSHELL_5,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            f"{REPOSITORY}/scripts/set_private_permissions.ps1",
            "-Path",
            "C:/Users/O\u2019Brien/.codex/config.toml",
        ]
        self.assertEqual(
            calls,
            [
                (base,),
                ([*base, "-CopyFrom", "C:/Users/O\u2019Brien/.codex/config.toml.bak"],),
            ],
        )


if __name__ == "__main__":
    unittest.main()
