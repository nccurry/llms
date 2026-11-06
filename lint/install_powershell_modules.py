#!/usr/bin/env python3
"""Download the pinned PowerShell modules, check their SHA-256, and unpack them.

Usage: install_powershell_modules.py <pins.json> <modules folder>

Each module lands in <modules folder>/<name>/<version>/, the layout PowerShell
finds through PSModulePath. A package whose checksum differs from its pin is
never unpacked.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

GALLERY = "https://www.powershellgallery.com/api/v2/package/{name}/{version}"
TIMEOUT_SECONDS = 120
ARGUMENT_COUNT = 2


def download(url: str) -> bytes:
    """Return the bytes served at an https URL."""
    if not url.startswith("https://"):
        message = f"Refusing to download from a non-https URL: {url}"
        raise ValueError(message)
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - https only, checked above
        return response.read()


def install_module(name: str, version: str, sha256: str, modules: Path) -> None:
    """Unpack one verified package, replacing any earlier copy of that version."""
    package = download(GALLERY.format(name=name, version=version))
    actual = hashlib.sha256(package).hexdigest()
    if actual != sha256:
        message = (
            f"{name} {version}: SHA-256 mismatch, expected {sha256} but the download is {actual}."
        )
        raise ValueError(message)
    destination = modules / name / version
    modules.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=modules) as scratch:
        unpacked = Path(scratch) / version
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            archive.extractall(unpacked)
        shutil.rmtree(destination, ignore_errors=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        unpacked.replace(destination)
    print(f"{name} {version}: checksum verified, installed in {destination}")


def main(arguments: list[str]) -> int:
    """Install every module in the pins file; return the exit code."""
    if len(arguments) != ARGUMENT_COUNT:
        print(__doc__, file=sys.stderr)
        return 2
    pins = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))["modules"]
    modules = Path(arguments[1])
    # Remove folders of other versions so only the pinned ones can load.
    for name, pin in pins.items():
        for other in (modules / name).glob("*"):
            if other.name != pin["version"]:
                shutil.rmtree(other, ignore_errors=True)
    try:
        for name, pin in pins.items():
            install_module(name, pin["version"], pin["sha256"], modules)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"install_powershell_modules: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
