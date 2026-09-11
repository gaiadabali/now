"""`engine.quality_scores` for `entity_type='place'` -- the places-side
sibling of `now_blender.quality.fetch_quality` (which is hardcoded to
`entity_type='article'` and lives in a package this one does not own).

Real data note: `now-quality` (E2.6) has only ever scored articles --
`SELECT count(*) FROM engine.quality_scores WHERE entity_type='place'` is
**0** on `now_jakarta` today (verified). Wired for real, honestly empty
today, exactly like `now_blender.covisitation` -- the day a places quality
scorer ships, this reader needs no change.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SELECT_SQL = text(
    """
    SELECT entity_id::int AS place_id, score
      FROM engine.quality_scores
     WHERE entity_type = 'place' AND entity_id::int = ANY(:ids)
    """
)


@dataclass(frozen=True)
class PlaceQualityRow:
    score: float


def fetch_place_quality(conn: Connection, place_ids: list[int]) -> dict[int, PlaceQualityRow]:
    if not place_ids:
        return {}
    rows = conn.execute(_SELECT_SQL, {"ids": place_ids}).fetchall()
    return {place_id: PlaceQualityRow(score=float(score)) for place_id, score in rows}
