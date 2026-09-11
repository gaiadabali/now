from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Write rows as newline-delimited JSON. Returns the row count written.

    Mirrors now-wp-extract's `jsonl.write_jsonl` byte-for-byte (same
    separators, same `ensure_ascii=False`, same trailing "\n", same
    `default=str` fallback) so output is directly comparable.
    """
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str))
            f.write("\n")
            n += 1
    return n


def iso(value: "str | datetime | None") -> str | None:
    """WXR datetime string ('YYYY-MM-DD HH:MM:SS') -> ISO 8601.

    WXR's zero-date sentinel ('0000-00-00 00:00:00') maps to None, matching
    wp-extract's treatment of the same sentinel from the raw DB column.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.startswith("0000-00-00"):
        return None
    return value.replace(" ", "T")
