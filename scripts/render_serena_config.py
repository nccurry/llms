#!/usr/bin/env python3
"""Render managed Serena preferences using its installed YAML parser, without writes."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

from ruamel.yaml import YAML
from serena.constants import SERENA_CONFIG_TEMPLATE_FILE


def main() -> None:
    defaults = json.loads(sys.argv[1])
    path = Path(sys.argv[2])
    existed = path.is_file()
    source = path if existed else Path(SERENA_CONFIG_TEMPLATE_FILE)
    original = source.read_text(encoding="utf-8")
    original_digest = (
        hashlib.sha256(original.encode("utf-8")).hexdigest() if existed else ""
    )
    yaml = YAML()
    yaml.preserve_quotes = True
    document = yaml.load(original)
    current = {key: document.get(key) for key in defaults}
    text = original
    if current != defaults:
        document.update(defaults)
        stream = io.StringIO()
        yaml.dump(document, stream)
        text = stream.getvalue()
    print(
        json.dumps(
            {
                "config": str(path),
                "current": current,
                "settings": defaults,
                "text": text,
                "original_digest": original_digest,
            }
        )
    )


if __name__ == "__main__":
    main()
