"""Orchestration: fetch -> diff against `text_hash` -> embed only what
changed -> upsert -> drop stale rows. Used by both the CLI's `backfill`
command (bulk, all rows) and the worker's `article.published` handler
(one row) -- `reembed_one` below is the single-entity path the worker
calls, sharing every line of upsert/hash logic with the bulk path so the
two can never drift into different behaviour.

Resumability: each batch commits independently (`with engine.begin()`
around each `upsert_batch` call). If the process is killed mid-run, every
already-committed batch is durable; re-running `backfill` recomputes
`existing_hashes` fresh and only re-embeds what is still missing or
changed -- there is no separate checkpoint file to go stale or corrupt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import Engine

from now_embeddings.providers.base import EmbeddingProvider
from now_embeddings.store import (
    EmbeddableRow,
    delete_stale,
    existing_hashes,
    fetch_article_by_id,
    fetch_place_by_id,
    upsert_batch,
)

logger = logging.getLogger("now_embeddings")

BATCH_SIZE = 32


@dataclass
class BackfillStats:
    entity_type: str
    total: int = 0
    embedded: int = 0
    skipped_unchanged: int = 0
    deleted_stale: int = 0
    errors: list[str] = field(default_factory=list)


def backfill_entity_type(
    engine: Engine,
    *,
    entity_type: str,
    rows: list[EmbeddableRow],
    provider: EmbeddingProvider,
    batch_size: int = BATCH_SIZE,
    prune_stale: bool = True,
) -> BackfillStats:
    stats = BackfillStats(entity_type=entity_type, total=len(rows))

    with engine.connect() as conn:
        existing = existing_hashes(conn, entity_type, provider.name)

    to_embed = [r for r in rows if existing.get(r.entity_id) != r.text_hash]
    stats.skipped_unchanged = len(rows) - len(to_embed)

    for i in range(0, len(to_embed), batch_size):
        batch = to_embed[i : i + batch_size]
        try:
            vecs = provider.embed_batch([r.text for r in batch])
        except Exception as exc:  # noqa: BLE001 -- one bad batch must not abort the whole backfill
            msg = f"{entity_type} batch [{i}:{i + len(batch)}] failed: {exc}"
            logger.error(msg)
            stats.errors.append(msg)
            continue
        with engine.begin() as conn:
            upsert_batch(
                conn,
                entity_type=entity_type,
                model=provider.name,
                dim=provider.dim,
                rows=[(r.entity_id, v, r.text_hash) for r, v in zip(batch, vecs)],
            )
        stats.embedded += len(batch)
        logger.info(
            "%s: embedded %d/%d (skipped %d unchanged)",
            entity_type,
            stats.embedded,
            len(to_embed),
            stats.skipped_unchanged,
        )

    if prune_stale and rows:
        with engine.begin() as conn:
            stats.deleted_stale = delete_stale(
                conn,
                entity_type=entity_type,
                model=provider.name,
                keep_entity_ids={r.entity_id for r in rows},
            )

    return stats


def reembed_one(
    engine: Engine,
    *,
    entity_type: str,
    row: EmbeddableRow,
    provider: EmbeddingProvider,
) -> bool:
    """Single-entity path for the publish-event worker. Returns True if a
    model call happened (text actually changed), False if the existing
    embedding was already current (still a success -- just no-op)."""
    with engine.connect() as conn:
        current = existing_hashes(conn, entity_type, provider.name)
    if current.get(row.entity_id) == row.text_hash:
        return False
    vec = provider.embed_batch([row.text])[0]
    with engine.begin() as conn:
        upsert_batch(
            conn,
            entity_type=entity_type,
            model=provider.name,
            dim=provider.dim,
            rows=[(row.entity_id, vec, row.text_hash)],
        )
    return True


def fetch_one(engine: Engine, entity_type: str, entity_id: str) -> EmbeddableRow | None:
    """Indexed single-row fetch for the publish-event worker -- `article`
    and `place` each resolve to a `WHERE id = :id` query (`store.py`), not
    a full-table scan, so handling one publish event costs one indexed
    lookup regardless of archive size."""
    with engine.connect() as conn:
        if entity_type == "article":
            return fetch_article_by_id(conn, entity_id)
        if entity_type == "place":
            return fetch_place_by_id(conn, entity_id)
    raise ValueError(f"no single-row fetch wired for entity_type={entity_type!r}")
