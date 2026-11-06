"""scripts/reshim_shared_data.sh rebuilds shims with the mise of the checkout that owns them."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/reshim_shared_data.sh"
# A stand-in mise that records who ran it, with what arguments, and what came first on PATH.
FAKE_MISE = """#!/bin/sh
checkout=$(dirname "$(dirname "$(dirname "$0")")")
printf '%s|%s|%s\\n' "$(basename "$checkout")" "$*" "${PATH%%:*}" >> "$LOG"
"""


@unittest.skipIf(os.name == "nt", "The script needs a POSIX shell and symbolic links.")
class ReshimSharedDataTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.log = self.directory / "log"

    def checkout(self, name, *, with_mise=True):
        bin_dir = self.directory / name / ".tools/bin"
        bin_dir.mkdir(parents=True)
        if with_mise:
            (bin_dir / "mise").write_text(FAKE_MISE)
            (bin_dir / "mise").chmod(0o755)
        return self.directory / name

    def run_script(self, checkout):
        return subprocess.run(
            ["sh", str(SCRIPT), str(checkout / ".tools/bin/mise")],
            check=False,
            capture_output=True,
            encoding="utf-8",
            env={
                **os.environ,
                "LOG": str(self.log),
                "MISE_DATA_DIR": str(checkout / ".tools/mise/data"),
            },
        )

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_a_checkout_that_owns_its_data_directory_reshims_with_its_own_mise(self):
        owner = self.checkout("owner")
        (owner / ".tools/mise/data").mkdir(parents=True)
        result = self.run_script(owner)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [f"owner|reshim|{owner}/.tools/bin"])

    def test_a_checkout_that_links_to_another_data_directory_reshims_with_the_owners_mise(self):
        owner = self.checkout("owner")
        (owner / ".tools/mise/data").mkdir(parents=True)
        worktree = self.checkout("worktree")
        (worktree / ".tools/mise").mkdir()
        (worktree / ".tools/mise/data").symlink_to(owner / ".tools/mise/data")
        result = self.run_script(worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        # The worktree's own mise never ran, so no shim can point at it.
        self.assertEqual(self.calls(), [f"owner|reshim|{owner.resolve()}/.tools/bin"])

    def test_a_link_to_a_folder_without_a_mise_leaves_the_shims_alone(self):
        owner = self.checkout("owner", with_mise=False)
        (owner / ".tools/mise/data").mkdir(parents=True)
        worktree = self.checkout("worktree")
        (worktree / ".tools/mise").mkdir()
        (worktree / ".tools/mise/data").symlink_to(owner / ".tools/mise/data")
        result = self.run_script(worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("shims left unchanged", result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
