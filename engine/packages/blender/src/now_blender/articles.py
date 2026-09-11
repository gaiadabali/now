"""Batch fetch of the `public.articles` columns the blend needs beyond
what `now_search.SearchEngine.fetch_summaries` already returns (title/
dek only) -- `format` (for freshness) and `published_at` (for freshness
age and, incidentally, the same field `now_search`'s own facets module
already reads). One query for the whole rerank pool, matching
`now_blender.quality.fetch_quality`'s batching shape and Sec.8.G's
"per-candidate work runs in memory over the already-reduced set" rule.

F124/F125 (T2 decay trust gate): also fetches the format term's
`(confidence, source)` from `engine.entity_terms`, via a LEFT JOIN keyed
on `entity_id = a.id::text` and `term_id = ANY(format_term_ids)` --
`format_term_ids` disambiguates the format-facet row from the
type/subtype/location rows the same `entity_id` may also carry (F92: no
cross-DB FK, so the caller resolves and caches these ids from the
platform vocabulary -- see `now_blender.platform.SiteRankingConfig
.format_term_ids` / `format_terms_cache.py`). `entity_terms`'s primary key
is `(entity_type, entity_id, term_id)`, so this LEFT JOIN matches at most
one row per article (format is single-valued and F125's re-classification
retracts a stale second row for the same facet), never fanning out the
result set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SELECT_SQL = text(
    """
    SELECT a.id, a.primary_type::text AS primary_type, a.format::text AS format,
           a.series_key, a.published_at,
           et.confidence::float8 AS format_confidence, et.source AS format_source
      FROM public.articles a
      LEFT JOIN engine.entity_terms et
        ON et.entity_type = 'article'
       AND et.entity_id = a.id::text
       AND et.term_id = ANY(CAST(:format_term_ids AS uuid[]))
     WHERE a.id = ANY(:ids)
    """
)


@dataclass(frozen=True)
class ArticleMeta:
    primary_type: str | None
    format: str | None
    series_key: str | None
    published_at: datetime | None
    # F124/F125 (T2): None/None when no entity_terms row matched (a
    # format_term_ids empty set, or a format value with no recorded
    # provenance) -- see now_blender.decay.is_format_trusted for how that
    # is treated (fails closed, same as an untrusted confidence).
    format_confidence: float | None = None
    format_source: str | None = None


def fetch_article_meta(
    conn: Connection, article_ids: list[int], format_term_ids: frozenset[str] = frozenset()
) -> dict[int, ArticleMeta]:
    """`format_term_ids` is the platform vocabulary's format-facet term id
    set (`SiteRankingConfig.format_term_ids`) -- required for the T2 trust
    gate to find the right `entity_terms` row. Defaults to empty (not
    required positionally) so every pre-existing caller keeps compiling;
    an empty set makes the LEFT JOIN match nothing, which is the correct,
    disclosed fail-closed behaviour (see `platform.py`
    `FORMAT_TERM_IDS_FALLBACK_SOURCE`), not a silent bypass of the gate."""
    if not article_ids:
        return {}
    rows = conn.execute(
        _SELECT_SQL, {"ids": article_ids, "format_term_ids": list(format_term_ids)}
    ).fetchall()
    return {
        r.id: ArticleMeta(
            primary_type=r.primary_type,
            format=r.format,
            series_key=r.series_key,
            published_at=r.published_at,
            format_confidence=r.format_confidence,
            format_source=r.format_source,
        )
        for r in rows
    }
