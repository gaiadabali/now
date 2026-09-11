"""Thin, streaming JSONL readers over the E1.1 extraction contract
(`jakarta/content/extracted/*.jsonl`). No validation beyond `json.loads` —
each loader module is explicit about which keys it reads and what it does
when one is missing/null, so that's the single place to look for "what
happens if the source is messy" rather than a second schema layer here.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())
