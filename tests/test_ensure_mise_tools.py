"""scripts/ensure_mise_tools.sh never installs into a mise data directory another checkout owns."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ensure_mise_tools.sh"
# A stand-in mise: it records its arguments and the first PATH entry, and answers `ls --missing`
# with the text in $FAKE_MISSING.
FAKE_MISE = """#!/bin/sh
printf '%s|%s\\n' "$*" "${PATH%%:*}" >> "$LOG"
if [ "$1" = ls ]; then cat "$FAKE_MISSING" 2>/dev/null || true; fi
"""
INSTALL = ["install", "task", "--locked", "--quiet"]


@unittest.skipIf(os.name == "nt", "The script needs a POSIX shell and symbolic links.")
class EnsureMiseToolsTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.log = self.base / "log"
        self.missing = self.base / "missing"
        self.owner = self.checkout("owner")
        (self.owner / ".tools/mise/data").mkdir(parents=True)

    def checkout(self, name):
        """Make a checkout with the script, a stand-in mise and a .tools folder."""
        root = self.base / name
        (root / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, root / "scripts")
        (root / ".tools/bin").mkdir(parents=True)
        mise = root / ".tools/bin/mise"
        mise.write_text(FAKE_MISE)
        mise.chmod(0o755)
        return root

    def run_script(self, root, data=None):
        return subprocess.run(
            [
                "sh",
                str(root / "scripts/ensure_mise_tools.sh"),
                str(root / ".tools/bin/mise"),
                *INSTALL,
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            env={
                **os.environ,
                "LOG": str(self.log),
                "FAKE_MISSING": str(self.missing),
                "MISE_DATA_DIR": str(data or root / ".tools/mise/data"),
            },
        )

    def calls(self):
        return (
            [line.split("|")[0] for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )

    def worktree(self, name="worktree"):
        """A checkout whose .tools is its own, ready for a link at .tools/mise or below."""
        root = self.checkout(name)
        (root / ".tools/mise").mkdir()
        return root

    def link_cases(self):
        """Each way a worktree can share the owner's data directory."""
        owner_data = self.owner / ".tools/mise/data"
        by_data = self.worktree("by-data")
        (by_data / ".tools/mise/data").symlink_to(owner_data)
        by_parent = self.checkout("by-parent")
        (by_parent / ".tools/mise").symlink_to(owner_data.parent)
        by_tools = self.base / "by-tools"
        (by_tools / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, by_tools / "scripts")
        (by_tools / ".tools").symlink_to(self.owner / ".tools")
        relative = self.worktree("relative")
        (relative / ".tools/mise/data").symlink_to("../../../owner/.tools/mise/data")
        chain = self.worktree("chain")
        (self.base / "middle").symlink_to(owner_data)
        (chain / ".tools/mise/data").symlink_to(self.base / "middle")
        return {
            "link at .tools/mise/data": by_data,
            "link at .tools/mise": by_parent,
            "link at .tools": by_tools,
            "relative link": relative,
            "chain of links": chain,
        }

    def test_a_checkout_that_owns_its_data_installs_then_reshims_with_its_own_mise(self):
        result = self.run_script(self.owner)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["install task --locked --quiet", "reshim"])
        self.assertEqual(
            self.log.read_text().splitlines()[1].split("|")[1], f"{self.owner}/.tools/bin"
        )

    def test_a_data_directory_that_does_not_exist_yet_counts_as_owned(self):
        root = self.checkout("fresh")
        result = self.run_script(root, data=root / ".tools/mise/not-yet/data")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["install task --locked --quiet", "reshim"])

    def test_a_shared_data_directory_is_never_installed_into_when_the_tools_are_there(self):
        for label, root in self.link_cases().items():
            with self.subTest(label):
                self.log.unlink(missing_ok=True)
                result = self.run_script(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                # Only the read-only check ran: no install and no reshim.
                self.assertEqual(self.calls(), ["ls --missing task"])

    def test_a_shared_data_directory_with_missing_tools_stops_with_the_owner_named(self):
        self.missing.write_text("uv  0.13.7 (missing)\n")
        for label, root in self.link_cases().items():
            with self.subTest(label):
                self.log.unlink(missing_ok=True)
                result = self.run_script(root)
                self.assertEqual(result.returncode, 1)
                self.assertIn(str(self.owner), result.stderr)
                self.assertIn("uv  0.13.7 (missing)", result.stderr)
                self.assertIn("./bootstrap.sh deps:tools", result.stderr)
                self.assertEqual(self.calls(), ["ls --missing task"])


if __name__ == "__main__":
    unittest.main()
