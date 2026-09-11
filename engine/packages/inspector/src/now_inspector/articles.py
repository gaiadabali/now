"""Read-only article/quality lookups against the city DB. No writes, no
migration -- this package owns nothing in the schema, it only SELECTs.

F124/F125 (T2 decay trust gate): also fetches the format term's
`(confidence, source)` via the same LEFT JOIN shape as
`now_blender.articles.fetch_article_meta` -- `format_term_ids` is required
to disambiguate the format-facet `engine.entity_terms` row from
type/subtype/location rows sharing the same `entity_id` (F92: no cross-DB
FK; the caller resolves/caches these ids from the platform vocabulary, see
`now_inspector.connections.platform_engine` / `now_blender
.format_terms_cache`).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_inspector.models import ArticleRow, QualityBreakdown

_ARTICLE_SQL = text(
    """
    SELECT a.id, a.title, a.dek, a.legacy_wp_id, a.legacy_permalink,
           a.primary_type::text AS primary_type, a.format::text AS format,
           a.series_key, a._status::text AS status, a.published_at::text AS published_at,
           et.confidence::float8 AS format_confidence, et.source AS format_source
      FROM public.articles a
      LEFT JOIN engine.entity_terms et
        ON et.entity_type = 'article'
       AND et.entity_id = a.id::text
       AND et.term_id = ANY(CAST(:format_term_ids AS uuid[]))
     WHERE a.id = :id
    """
)

_ARTICLES_BY_IDS_SQL = text(
    """
    SELECT a.id, a.title, a.dek, a.legacy_wp_id, a.legacy_permalink,
           a.primary_type::text AS primary_type, a.format::text AS format,
           a.series_key, a._status::text AS status, a.published_at::text AS published_at,
           et.confidence::float8 AS format_confidence, et.source AS format_source
      FROM public.articles a
      LEFT JOIN engine.entity_terms et
        ON et.entity_type = 'article'
       AND et.entity_id = a.id::text
       AND et.term_id = ANY(CAST(:format_term_ids AS uuid[]))
     WHERE a.id = ANY(:ids)
    """
)

_QUALITY_SQL = text(
    """
    SELECT entity_id, score::float AS score, components
      FROM engine.quality_scores
     WHERE entity_type = 'article' AND entity_id = :entity_id
    """
)


def _row_to_article(r) -> ArticleRow:
    return ArticleRow(
        id=r.id,
        title=r.title or "(untitled)",
        dek=r.dek,
        legacy_wp_id=int(r.legacy_wp_id) if r.legacy_wp_id is not None else None,
        legacy_permalink=r.legacy_permalink,
        primary_type=r.primary_type,
        format=r.format,
        series_key=r.series_key,
        status=r.status,
        published_at=r.published_at,
        format_confidence=r.format_confidence,
        format_source=r.format_source,
    )


def fetch_article(
    conn: Connection, article_id: int, format_term_ids: frozenset[str] = frozenset()
) -> ArticleRow | None:
    row = conn.execute(_ARTICLE_SQL, {"id": article_id, "format_term_ids": list(format_term_ids)}).first()
    return _row_to_article(row) if row else None


def fetch_articles(
    conn: Connection, article_ids: list[int], format_term_ids: frozenset[str] = frozenset()
) -> dict[int, ArticleRow]:
    if not article_ids:
        return {}
    rows = conn.execute(
        _ARTICLES_BY_IDS_SQL, {"ids": article_ids, "format_term_ids": list(format_term_ids)}
    ).fetchall()
    return {r.id: _row_to_article(r) for r in rows}


def fetch_quality(conn: Connection, entity_id: str) -> QualityBreakdown:
    row = conn.execute(_QUALITY_SQL, {"entity_id": entity_id}).first()
    if row is None:
        return QualityBreakdown(
            entity_id=entity_id,
            score=None,
            components=None,
            found=False,
            note="No engine.quality_scores row for this article -- E2.6 has not scored it "
            "(or it postdates the last score run).",
        )
    return QualityBreakdown(
        entity_id=entity_id,
        score=row.score,
        components=row.components,
        found=True,
    )


def fetch_quality_bulk(conn: Connection, entity_ids: list[str]) -> dict[str, QualityBreakdown]:
    if not entity_ids:
        return {}
    rows = conn.execute(
        text(
            "SELECT entity_id, score::float AS score, components FROM engine.quality_scores "
            "WHERE entity_type = 'article' AND entity_id = ANY(:ids)"
        ),
        {"ids": entity_ids},
    ).fetchall()
    found = {
        r.entity_id: QualityBreakdown(entity_id=r.entity_id, score=r.score, components=r.components, found=True)
        for r in rows
    }
    out: dict[str, QualityBreakdown] = {}
    for eid in entity_ids:
        out[eid] = found.get(
            eid,
            QualityBreakdown(
                entity_id=eid,
                score=None,
                components=None,
                found=False,
                note="No engine.quality_scores row for this article.",
            ),
        )
    return out
