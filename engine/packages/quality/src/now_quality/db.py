"""Postgres access for the city DB. Reuses `now_db.settings.
city_database_url` (a bare `db_ref` like `now_jakarta` or a full DSN) so
this package agrees with `now-db`/`now-embeddings` on connection
resolution rather than inventing another `NOW_PG_*` reader.

`engine.quality_scores.entity_id` is `text` as of migration 0005 (F33) --
it holds the native `public.articles.id` integer PK, stringified, not a
derived uuid. See `now_quality.db.upsert_quality_score` and the deleted
`now_quality.entity_id` module's git history for the stopgap this replaced.
"""

from __future__ import annotations

from dataclasses import dataclass

from now_db.settings import city_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def make_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref))


@dataclass
class ArticleRecord:
    id: int
    legacy_wp_id: int | None
    title: str
    body_blocks: list | None
    author_id: int | None
    hero_media_id: int | None
    published_at: str | None
    series_key: str | None


_FETCH_SQL = text(
    """
    select id, legacy_wp_id, title, body_blocks, author_id, hero_media_id,
           published_at::date::text as published_date, series_key
    from public.articles
    order by id
    """
)


def fetch_articles(engine: Engine) -> list[ArticleRecord]:
    with engine.connect() as conn:
        rows = conn.execute(_FETCH_SQL).mappings().all()
    out = []
    for r in rows:
        legacy = r["legacy_wp_id"]
        out.append(
            ArticleRecord(
                id=r["id"],
                legacy_wp_id=int(legacy) if legacy is not None else None,
                title=r["title"] or "",
                body_blocks=r["body_blocks"],
                author_id=r["author_id"],
                hero_media_id=r["hero_media_id"],
                published_at=r["published_date"],
                series_key=r["series_key"],
            )
        )
    return out


_UPSERT_QUALITY_SQL = text(
    """
    insert into engine.quality_scores (entity_type, entity_id, score, components, computed_at)
    values (:entity_type, :entity_id, :score, cast(:components as jsonb), now())
    on conflict (entity_type, entity_id)
    do update set score = excluded.score,
                  components = excluded.components,
                  computed_at = excluded.computed_at
    """
)


def upsert_quality_score(engine: Engine, *, entity_type: str, entity_id: str, score: float, components_json: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            _UPSERT_QUALITY_SQL,
            {"entity_type": entity_type, "entity_id": entity_id, "score": score, "components": components_json},
        )


def upsert_quality_scores_bulk(engine: Engine, rows: list[dict]) -> None:
    """Same upsert, batched in one transaction. `rows` items:
    {entity_type, entity_id, score, components_json}."""
    if not rows:
        return
    with engine.begin() as conn:
        conn.execute(
            _UPSERT_QUALITY_SQL,
            [
                {
                    "entity_type": r["entity_type"],
                    "entity_id": r["entity_id"],
                    "score": r["score"],
                    "components": r["components_json"],
                }
                for r in rows
            ],
        )


_ASSIGN_SERIES_KEY_SQL = text(
    """
    update public.articles
    set series_key = :series_key
    where id = :article_id
      and series_key is null
    """
)


def assign_series_key(engine: Engine, *, article_id: int, series_key: str) -> bool:
    """Idempotent by construction: only ever fires on a NULL series_key, so
    a pre-existing value (loader-seeded or a prior manual correction) is
    never touched. Returns True if a row was actually updated."""
    with engine.begin() as conn:
        result = conn.execute(_ASSIGN_SERIES_KEY_SQL, {"series_key": series_key, "article_id": article_id})
        return result.rowcount > 0


def assign_series_keys_bulk(engine: Engine, assignments: list[tuple[int, str]]) -> int:
    if not assignments:
        return 0
    updated = 0
    with engine.begin() as conn:
        for article_id, series_key in assignments:
            result = conn.execute(
                _ASSIGN_SERIES_KEY_SQL, {"series_key": series_key, "article_id": article_id}
            )
            updated += result.rowcount
    return updated
