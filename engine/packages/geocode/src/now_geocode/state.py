"""Resumable cache for paid-provider calls (`ARCHITECTURE.md` E2.5:
"idempotent and resumable — this will run in batches against a paid
API"). An append-only JSONL log, keyed by `PlaceCandidate.key`: every
provider attempt (success, stable zero-result, or transient failure) is
appended as one line, and `load_cache` folds the log down to the latest
record per key. Re-running `now-geocode build` with the same `--state`
file:

- skips any key whose latest record is `final=True` (a resolved point or
  a stable ZERO_RESULTS) — no repeat billing for something already
  answered
- retries any key whose latest record is `final=False` (a
  `RetryableProviderError` — rate limit, transient network) — a crash or
  a deliberate `OVER_QUERY_LIMIT` backoff does not lose progress and does
  not get treated as a permanent negative

Append-only rather than a single rewritten JSON file so a crash mid-run
can never corrupt previously-recorded results — the log is always valid
JSONL up to wherever it was last flushed, and the loader is tolerant of
being pointed at a file that doesn't exist yet (first run).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class StateRecord:
    place_key: str
    final: bool  # True = don't re-attempt; False = retryable, attempt again next run
    rung: str  # models.Rung value that produced this outcome (or "unresolved")
    status: str  # models.Status value
    lat: float | None
    lng: float | None
    google_place_id: str | None
    confidence: float
    location_type: str | None
    note: str | None
    attempted_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self._cache: dict[str, StateRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                self._cache[data["place_key"]] = StateRecord(**data)

    def get(self, place_key: str) -> StateRecord | None:
        record = self._cache.get(place_key)
        if record and record.final:
            return record
        return None  # absent, or present-but-retryable -> caller should attempt

    def record(self, record: StateRecord) -> None:
        self._cache[record.place_key] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def __len__(self) -> int:
        return len(self._cache)
