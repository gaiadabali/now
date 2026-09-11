from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Write rows as newline-delimited JSON. Returns the row count written."""
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str))
            f.write("\n")
            n += 1
    return n


def iso(value: "str | datetime | None") -> str | None:
    """MySQL datetime -> ISO 8601 'YYYY-MM-DDTHH:MM:SS'.

    pymysql parses valid DATETIME columns into `datetime` objects directly;
    WordPress's zero-date sentinel ('0000-00-00 00:00:00') can't be parsed
    as a real date and comes back as the raw string instead — treated here
    as "never actually dated" (an imported draft/malformed row) and mapped
    to None rather than a fake date.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        if not value or value.startswith("0000-00-00"):
            return None
        return value.replace(" ", "T")
    return None
