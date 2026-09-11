"""Read-only article/quality lookups against the city DB. No writes, no
migration -- this package owns nothing in the schema, it only SELECTs.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_inspector.models import ArticleRow, QualityBreakdown

_ARTICLE_SQL = text(
    """
    SELECT id, title, dek, legacy_wp_id, legacy_permalink,
           primary_type::text AS primary_type, format::text AS format,
           series_key, _status::text AS status, published_at::text AS published_at
      FROM public.articles
     WHERE id = :id
    """
)

_ARTICLES_BY_IDS_SQL = text(
    """
    SELECT id, title, dek, legacy_wp_id, legacy_permalink,
           primary_type::text AS primary_type, format::text AS format,
           series_key, _status::text AS status, published_at::text AS published_at
      FROM public.articles
     WHERE id = ANY(:ids)
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
    )


def fetch_article(conn: Connection, article_id: int) -> ArticleRow | None:
    row = conn.execute(_ARTICLE_SQL, {"id": article_id}).first()
    return _row_to_article(row) if row else None


def fetch_articles(conn: Connection, article_ids: list[int]) -> dict[int, ArticleRow]:
    if not article_ids:
        return {}
    rows = conn.execute(_ARTICLES_BY_IDS_SQL, {"ids": article_ids}).fetchall()
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
