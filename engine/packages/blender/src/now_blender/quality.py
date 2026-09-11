"""Batch reads of `engine.quality_scores` for the blend's `w_qual` term
and the Sec.10 feature vector's `popularity_prior` (both real data for
articles -- 4,772/4,772 scored, E2.6). One query per `rerank()` call over
the whole candidate pool (~40 ids), not one query per candidate, per
ARCHITECTURE.md Sec.8.G's "per-user/per-candidate work runs in memory
over the already-reduced set" ordering rule -- this is exactly the same
batching shape `now_search.engine.fetch_summaries` uses for
`public.articles`.

`entity_id` is `text` holding the stringified `public.articles.id`
(F33, migration 0005) -- joined back to an `int` article id by this
module so callers work in `int` article-id space like the rest of
`now_search`/`now_filters`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SELECT_SQL = text(
    """
    SELECT entity_id::int AS article_id, score, components->'popularity'->>'prior_score' AS prior_score
      FROM engine.quality_scores
     WHERE entity_type = 'article' AND entity_id::int = ANY(:ids)
    """
)


@dataclass(frozen=True)
class QualityRow:
    score: float
    popularity_prior: float | None


def fetch_quality(conn: Connection, article_ids: list[int]) -> dict[int, QualityRow]:
    """article_id -> QualityRow for every id that has a real
    `engine.quality_scores` row. An id with no row (should not happen for
    a published article post-E2.6, but not asserted here -- this module
    has no opinion on whether that is an error) is simply absent from the
    returned dict; callers treat a missing key as "score unknown", never
    as "score is 0"."""
    if not article_ids:
        return {}
    rows = conn.execute(_SELECT_SQL, {"ids": article_ids}).fetchall()
    out: dict[int, QualityRow] = {}
    for article_id, score, prior_score in rows:
        out[article_id] = QualityRow(
            score=float(score),
            popularity_prior=float(prior_score) if prior_score is not None else None,
        )
    return out
