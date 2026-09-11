"""Orchestration for `engine.article_search` (F41): fetch -> diff against
`body_text_hash` -> upsert only what changed -> drop stale rows. Used by
both `now-search backfill-tsv` (bulk, all published articles) and
`tsv_worker.TsvRefreshWorker`'s `article.published` handler (one row) --
`fetch_one`/`refresh_row` below are the single-article path the worker
calls, sharing every line of upsert logic with the bulk path so the two
can never drift into different behaviour. Mirrors
`now_embeddings.pipeline`'s `backfill_entity_type`/`fetch_one`/
`reembed_one` split exactly.

Resumability: each batch commits independently (`with engine.begin()`
around each `upsert_tsv_batch` call). If the process is killed mid-run,
every already-committed batch is durable; re-running `backfill_tsv`
recomputes `existing_hashes` fresh and only rewrites what is still
missing or changed -- no separate checkpoint file to go stale.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Engine

from now_search.tsv_store import (
    ArticleTsvRow,
    delete_stale,
    existing_hash_for,
    existing_hashes,
    fetch_all_for_tsv,
    fetch_one_for_tsv,
    upsert_tsv_batch,
)

logger = logging.getLogger("now_search.tsv")

BATCH_SIZE = 200


@dataclass
class TsvBackfillStats:
    total: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    deleted_stale: int = 0


def backfill_tsv(engine: Engine, *, batch_size: int = BATCH_SIZE, prune_stale: bool = True) -> TsvBackfillStats:
    """Builds/refreshes `engine.article_search` for every published
    article in `engine`'s city DB. Idempotent: a rerun with nothing
    changed rewrites nothing (every row skipped on the `body_text_hash`
    check) and exits fast."""
    with engine.connect() as conn:
        rows = fetch_all_for_tsv(conn)
        existing = existing_hashes(conn)

    stats = TsvBackfillStats(total=len(rows))
    to_update = [r for r in rows if existing.get(r.article_id) != r.text_hash]
    stats.skipped_unchanged = len(rows) - len(to_update)

    for i in range(0, len(to_update), batch_size):
        batch = to_update[i : i + batch_size]
        with engine.begin() as conn:
            upsert_tsv_batch(conn, batch)
        stats.updated += len(batch)
        logger.info(
            "tsv backfill: %d/%d updated (skipped %d unchanged)",
            stats.updated,
            len(to_update),
            stats.skipped_unchanged,
        )

    if prune_stale and rows:
        with engine.begin() as conn:
            stats.deleted_stale = delete_stale(conn, {r.article_id for r in rows})

    return stats


def fetch_one(engine: Engine, article_id: int) -> ArticleTsvRow | None:
    """Single-entity read for the publish-event worker -- one indexed
    lookup, not a full-corpus scan."""
    with engine.connect() as conn:
        return fetch_one_for_tsv(conn, article_id)


def refresh_row(engine: Engine, row: ArticleTsvRow) -> bool:
    """Writes (or skips) one already-fetched row. Returns True if a write
    happened (text actually changed or the article is new to this
    table), False if the existing tsv was already current (still a
    success -- just a no-op, same contract as
    `now_embeddings.pipeline.reembed_one`)."""
    current_hash = None
    with engine.connect() as conn:
        current_hash = existing_hash_for(conn, row.article_id)
    if current_hash == row.text_hash:
        return False
    with engine.begin() as conn:
        upsert_tsv_batch(conn, [row])
    return True
