from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator


class Ledger:
    """Append-only, resumable record of one outcome per URL key.

    Unlike a paginated harvest, mirror order doesn't matter and any subset of
    keys may already be done. Resumability here means: read every line ever
    appended, keep the last outcome per key, and skip any key already marked
    'done' before touching the network again. A crash mid-write only ever
    loses the one in-flight fetch, never prior progress, because each line is
    flushed+fsynced before the next fetch starts.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def record(self, entry: dict[str, Any]) -> None:
        self._handle.write(json.dumps(entry, ensure_ascii=False, default=str))
        self._handle.write("\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def load_done(self) -> dict[str, dict[str, Any]]:
        """Last recorded outcome per key, for keys that terminated cleanly.

        'done' = a status that should never be retried: ok (uploaded), or a
        definitive 404/410 (we do not hammer a dead link every re-run).
        Transient errors (network, 5xx, timeout) are NOT considered done, so
        a re-run retries them.
        """
        outcomes: dict[str, dict[str, Any]] = {}
        if not self.path.exists():
            return outcomes
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                key = rec.get("key")
                if key:
                    outcomes[key] = rec
        return {k: v for k, v in outcomes.items() if v.get("status") in ("ok", "not_found")}


def iter_ledger(path: Path) -> Iterator[dict[str, Any]]:
    if not Path(path).exists():
        return
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)
