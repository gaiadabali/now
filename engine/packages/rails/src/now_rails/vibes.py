"""Batch fetch of `public.places_vibe` -- the one facet Row 1's cold-start
formula (ARCHITECTURE.md Sec.7: `compat = price_band_proximity *
vibe_overlap * geo_proximity * user_taste`) needs that no existing package
already exposes on a `Candidate` (`now_filters.models.Candidate` -- a
package this one does not own -- has no `vibe` field; `hard.py`'s places
query does not select it, since `places_vibe` is a separate multi-valued
join table, not a `places` column). Kept as this package's own small
reader rather than asking `now-filters` to widen `Candidate` for one
rail's one facet.

Real data note: `SELECT count(*) FROM public.places_vibe` is **0** on
`now_jakarta` today (verified) -- every real place is the F27 loader
sentinel with no vibe tags assigned. This reader is genuinely wired and
genuinely returns nothing on real content, matching the same "ask, get
zero rows, report the honest result" pattern as `now_blender.covisitation`.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SELECT_SQL = text(
    """
    SELECT parent_id, value::text AS value
      FROM public.places_vibe
     WHERE parent_id = ANY(:ids)
    """
)


def fetch_place_vibes(conn: Connection, place_ids: list[int]) -> dict[int, frozenset[str]]:
    if not place_ids:
        return {}
    rows = conn.execute(_SELECT_SQL, {"ids": place_ids}).fetchall()
    out: dict[int, set[str]] = {}
    for parent_id, value in rows:
        out.setdefault(parent_id, set()).add(value)
    return {k: frozenset(v) for k, v in out.items()}


def vibe_overlap(subject_vibes: frozenset[str] | None, candidate_vibes: frozenset[str] | None) -> float | None:
    """Jaccard overlap -- `None` (not 0.0) when either side has no vibe
    tags at all, the same "missing is not the same as worst-case" rule
    `now_blender.geo`/`now_blender.decay` already follow, so Row 1's
    multiplicative compat formula can treat a missing facet as a neutral
    `1.0` factor rather than silently zeroing out every candidate the
    moment vibe data is absent (true for 100% of real places today)."""
    if not subject_vibes or not candidate_vibes:
        return None
    intersection = len(subject_vibes & candidate_vibes)
    union = len(subject_vibes | candidate_vibes)
    if union == 0:
        return None
    return intersection / union
