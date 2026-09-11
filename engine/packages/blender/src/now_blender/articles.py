"""Batch fetch of the `public.articles` columns the blend needs beyond
what `now_search.SearchEngine.fetch_summaries` already returns (title/
dek only) -- `format` (for freshness) and `published_at` (for freshness
age and, incidentally, the same field `now_search`'s own facets module
already reads). One query for the whole rerank pool, matching
`now_blender.quality.fetch_quality`'s batching shape and Sec.8.G's
"per-candidate work runs in memory over the already-reduced set" rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SELECT_SQL = text(
    """
    SELECT id, primary_type::text AS primary_type, format::text AS format,
           series_key, published_at
      FROM public.articles
     WHERE id = ANY(:ids)
    """
)


@dataclass(frozen=True)
class ArticleMeta:
    primary_type: str | None
    format: str | None
    series_key: str | None
    published_at: datetime | None


def fetch_article_meta(conn: Connection, article_ids: list[int]) -> dict[int, ArticleMeta]:
    if not article_ids:
        return {}
    rows = conn.execute(_SELECT_SQL, {"ids": article_ids}).fetchall()
    return {
        r.id: ArticleMeta(
            primary_type=r.primary_type, format=r.format, series_key=r.series_key, published_at=r.published_at
        )
        for r in rows
    }
