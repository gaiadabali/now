"""Read-through cache over `engine.rail_cache` (E0.2 baseline, `article_id
text` since F33/migration 0005 -- **no migration needed**, per this
ticket's own scope note).

    engine.rail_cache(article_id text, segment_id text, rail text,
                       candidates jsonb, rung smallint, computed_at timestamptz,
                       PRIMARY KEY (article_id, segment_id, rail))

A `RailResult` round-trips through `candidates` (jsonb) via
`RailResult.as_dict()`/`.from_dict()` -- the whole result, not just the
entity-id list, so a cache HIT needs zero recomputation of components/
rung/pool_size and, critically, **never touches `engine.embeddings` or the
fastembed model** (see `row3_similar.py`'s docstring on why that matters
for p95). `rung` (smallint) duplicates `rung_index` from the jsonb blob as
a real, queryable column -- so "how often does rail X land on rung >= 4"
is a plain `SELECT`, not a jsonb walk -- but the jsonb blob stays the
source of truth `from_dict` reads back from.

**Precompute vs. read-through.** ARCHITECTURE.md Sec.7 describes an
offline worker precomputing `rail_cache` on a schedule; this package owns
no scheduler (out of `engine/packages/rails/**`'s remit). What is
implemented here is the read-through half of that contract --
`get_or_compute` below is transparently correct whether the row it finds
was written by a future offline worker or by a previous request's own
cache miss, and is the seam a scheduled precompute job would slot into
(call the same `write_rail_cache` this module already uses)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_rails.models import RailResult

DEFAULT_MAX_AGE = timedelta(hours=6)  # judgment call -- no precompute worker exists yet to refresh this on a schedule

_SELECT_SQL = text(
    """
    SELECT rail, candidates, rung, computed_at
      FROM engine.rail_cache
     WHERE article_id = :article_id AND segment_id = :segment_id AND rail = ANY(:rails)
    """
)

_UPSERT_SQL = text(
    """
    INSERT INTO engine.rail_cache (article_id, segment_id, rail, candidates, rung, computed_at)
    VALUES (:article_id, :segment_id, :rail, CAST(:candidates AS jsonb), :rung, :computed_at)
    ON CONFLICT (article_id, segment_id, rail)
    DO UPDATE SET candidates = EXCLUDED.candidates, rung = EXCLUDED.rung, computed_at = EXCLUDED.computed_at
    """
)


@dataclass(frozen=True)
class CachedRail:
    result: RailResult
    computed_at: datetime

    @property
    def age(self) -> timedelta:
        now = datetime.now(timezone.utc)
        computed_at = self.computed_at if self.computed_at.tzinfo else self.computed_at.replace(tzinfo=timezone.utc)
        return now - computed_at


def read_cached_rails(
    conn: Connection, article_id: int, segment: str, rails: list[str]
) -> dict[str, CachedRail]:
    rows = conn.execute(
        _SELECT_SQL, {"article_id": str(article_id), "segment_id": segment, "rails": rails}
    ).fetchall()
    return {
        r.rail: CachedRail(result=RailResult.from_dict(r.candidates), computed_at=r.computed_at)
        for r in rows
    }


def write_rail_cache(
    conn: Connection, article_id: int, segment: str, result: RailResult, *, now: datetime | None = None, commit: bool = True
) -> None:
    computed_at = now or datetime.now(timezone.utc)
    conn.execute(
        _UPSERT_SQL,
        {
            "article_id": str(article_id),
            "segment_id": segment,
            "rail": result.rail,
            "candidates": json.dumps(result.as_dict()),
            "rung": result.rung_index,
            "computed_at": computed_at,
        },
    )
    if commit:
        conn.commit()


def write_rail_caches(
    conn: Connection, article_id: int, segment: str, results: list[RailResult], *, now: datetime | None = None
) -> None:
    """Writes every rail's cache row as ONE multi-row INSERT plus a
    SINGLE commit -- two round trips total, not `write_rail_cache` called
    N times (each its own INSERT *and* its own commit, N*2 round trips).
    Measured, not assumed: on this dev box (Postgres in Docker, ~11-15ms
    per round trip -- see the package README's timing section), three
    separate INSERT+COMMIT pairs cost ~60-90ms on their own, close to a
    third of this rail's entire cold-path p95 budget, for zero benefit --
    all three rows belong to the same `(article_id, segment)` compute and
    become visible atomically either way."""
    if not results:
        return
    computed_at = now or datetime.now(timezone.utc)
    values_sql: list[str] = []
    params: dict = {}
    for i, result in enumerate(results):
        values_sql.append(f"(:article_id, :segment_id, :rail_{i}, CAST(:candidates_{i} AS jsonb), :rung_{i}, :computed_at)")
        params[f"rail_{i}"] = result.rail
        params[f"candidates_{i}"] = json.dumps(result.as_dict())
        params[f"rung_{i}"] = result.rung_index
    params["article_id"] = str(article_id)
    params["segment_id"] = segment
    params["computed_at"] = computed_at

    sql = text(
        "INSERT INTO engine.rail_cache (article_id, segment_id, rail, candidates, rung, computed_at) "
        "VALUES " + ", ".join(values_sql) + " "
        "ON CONFLICT (article_id, segment_id, rail) "
        "DO UPDATE SET candidates = EXCLUDED.candidates, rung = EXCLUDED.rung, computed_at = EXCLUDED.computed_at"
    )
    conn.execute(sql, params)
    conn.commit()


def is_fresh(cached: CachedRail, *, max_age: timedelta = DEFAULT_MAX_AGE) -> bool:
    return cached.age <= max_age
