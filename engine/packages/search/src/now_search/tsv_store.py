"""SQL for `engine.article_search` (F41): fetch the text-bearing columns of
`public.articles`, build the exact tsvector-input text with
`now_content_clean.metrics.visible_text_out` -- the same lxml-based block
walker `now-embeddings` already uses for the semantic side, which handles
`list`/`gallery`/`columns` blocks correctly (this is the whole fix for
F40) -- and read/write `engine.article_search` itself.

Deliberately raw SQL (`sqlalchemy.text`), matching this monorepo's
convention (`now_embeddings.store`, `now_loader`, `now_geocode`) of not
putting an ORM in front of a table this package does not own the
migrations for (this package owns `engine/packages/search/**` only; the
migration itself is `engine/packages/db/.../0006_*.py`).

`entity_id` is a plain Python `int` throughout this module -- unlike
`engine.embeddings.entity_id` (which is `text`, because that table holds
articles *and* places *and* terms under one column), `engine.article_search`
is article-only by construction (see migration 0006's docstring), so
`public.articles.id`'s native `integer` type is used verbatim with no
stringify/parse round-trip anywhere in this package's tsv path.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from now_content_clean.metrics import visible_text_out
from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class ArticleTsvRow:
    article_id: int
    title: str
    dek: str | None
    body_text: str
    text_hash: str


def _hash(title: str, dek: str | None, body_text: str) -> str:
    """sha256 over the exact three strings that go into the tsvector --
    same idempotency pattern as `engine.embeddings.text_hash`
    (`now_embeddings.textbuild._hash`): an unchanged hash means an
    unchanged tsvector-input text, which means an unchanged tsvector, so
    skipping the write is not an approximation."""
    raw = f"{title}\n\n{dek or ''}\n\n{body_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _to_tsv_row(article_id: int, title: str | None, dek: str | None, body_blocks: list[dict] | None) -> ArticleTsvRow:
    title = title or ""
    body_text = visible_text_out(body_blocks or [])
    return ArticleTsvRow(
        article_id=article_id,
        title=title,
        dek=dek,
        body_text=body_text,
        text_hash=_hash(title, dek, body_text),
    )


_FETCH_ALL_SQL = text(
    """
    SELECT id, title, dek, body_blocks
      FROM public.articles
     WHERE _status = 'published'
     ORDER BY id
    """
)

_FETCH_ONE_SQL = text(
    """
    SELECT id, title, dek, body_blocks
      FROM public.articles
     WHERE id = :id AND _status = 'published'
    """
)


def fetch_all_for_tsv(conn: Connection) -> list[ArticleTsvRow]:
    """Every published article, as the text this package will index --
    the bulk path used by `now-search backfill-tsv`."""
    rows = conn.execute(_FETCH_ALL_SQL).fetchall()
    return [_to_tsv_row(r.id, r.title, r.dek, r.body_blocks) for r in rows]


def fetch_one_for_tsv(conn: Connection, article_id: int) -> ArticleTsvRow | None:
    """Indexed single-row fetch for the publish-event worker -- one
    `WHERE id = :id` lookup per event, not a full-corpus scan (mirrors
    `now_embeddings.store.fetch_article_by_id` exactly)."""
    row = conn.execute(_FETCH_ONE_SQL, {"id": article_id}).first()
    if row is None:
        return None
    return _to_tsv_row(row.id, row.title, row.dek, row.body_blocks)


def existing_hashes(conn: Connection) -> dict[int, str]:
    """article_id -> body_text_hash for every row already in
    `engine.article_search`. Used by the bulk backfill to diff the whole
    corpus in one round trip."""
    rows = conn.execute(text("SELECT entity_id, body_text_hash FROM engine.article_search")).fetchall()
    return {int(r[0]): r[1] for r in rows}


def existing_hash_for(conn: Connection, article_id: int) -> str | None:
    """Single-row counterpart to `existing_hashes` -- the worker's
    per-event idempotency check costs one indexed lookup, not an O(n)
    fetch of every article's hash to check one."""
    return conn.execute(
        text("SELECT body_text_hash FROM engine.article_search WHERE entity_id = :id"),
        {"id": article_id},
    ).scalar()


_UPSERT_SQL = text(
    """
    INSERT INTO engine.article_search (entity_id, tsv, body_text_hash, updated_at)
    VALUES (
        :id,
        setweight(to_tsvector('english', :title), 'A')
        || setweight(to_tsvector('english', coalesce(:dek, '')), 'B')
        || setweight(to_tsvector('english', :body), 'C'),
        :hash,
        now()
    )
    ON CONFLICT (entity_id) DO UPDATE SET
        tsv = EXCLUDED.tsv,
        body_text_hash = EXCLUDED.body_text_hash,
        updated_at = now()
    """
)


def upsert_tsv_batch(conn: Connection, rows: list[ArticleTsvRow]) -> None:
    """`to_tsvector` still runs in Postgres (there is no Python tsvector
    type) -- what changed vs. the old `pg_temp` cache is *what text* it
    runs against: the real `visible_text_out` output, computed once here
    in Python and passed as a bind parameter, not a SQL-side
    `regexp_replace` approximation recomputed from raw jsonb on every
    build. `title`/`dek`/`body` are always plain Python strings from our
    own extractor, never user input, so this is not an injection
    surface -- same reasoning `now_embeddings.store._vec_literal`
    documents for its own generated SQL fragment."""
    for r in rows:
        conn.execute(
            _UPSERT_SQL,
            {"id": r.article_id, "title": r.title, "dek": r.dek, "body": r.body_text, "hash": r.text_hash},
        )


def delete_stale(conn: Connection, keep_ids: set[int]) -> int:
    """Removes `article_search` rows for articles no longer published
    (unpublished, deleted, or draft) -- keeps this table from
    accumulating rows the rest of search can never legitimately surface.
    Mirrors `now_embeddings.store.delete_stale`."""
    if not keep_ids:
        return 0
    result = conn.execute(
        text("DELETE FROM engine.article_search WHERE entity_id <> ALL(:keep)"),
        {"keep": list(keep_ids)},
    )
    return result.rowcount or 0
