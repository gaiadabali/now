"""Lexical retrieval: Postgres full-text (`ts_rank_cd`) over the
materialised `engine.article_search.tsv` (F41's migration 0006), title >
dek > body weighted, with a GIN index that survives across
connections/processes.

**History, for anyone diffing this file**: E3.1 originally computed this
tsvector "on the fly" per the task brief's literal wording, approximated
in a session-scoped `pg_temp` cache -- a real per-query CTE recomputing
`to_tsvector` from raw `body_blocks` jsonb on every call measured 2,619ms
(unusable; see the E3.1 report), and even the `pg_temp` memoization
carried a ~4s one-time-per-*connection* warm-up plus a SQL-side body-text
approximation that skipped `list`/`gallery`/`columns` blocks entirely
(F40 -- the false positive that ranked "7 Best Padel Courts in Jakarta"
above real brunch-spot listicles for the query "brunch spots kemang",
because none of a listicle's actual venue names lived in any tsvector).

F41's migration 0006 removes both problems at once: `engine.article_search`
is a real, persisted, GIN-indexed table, refreshed by
`tsv_pipeline.py`/`tsv_worker.py` using `now_content_clean.metrics.
visible_text_out` -- the same lxml-based block walker `now-embeddings`
already uses for the semantic side, which handles every block type
(including `list`/`gallery`/`columns`) correctly. This module is now a
plain read against that table: no cache to build, no warm-up cost, no
`pg_temp` object anywhere in this package (grep it -- there is nothing
left to find).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_search.models import RankedHit
from now_search.rrf import to_ranked_hits

_SEARCH_SQL = text(
    """
    SELECT entity_id, ts_rank_cd(tsv, websearch_to_tsquery('english', :query)) AS rank
      FROM engine.article_search
     WHERE tsv @@ websearch_to_tsquery('english', :query)
     ORDER BY rank DESC
     LIMIT :limit
    """
)

_SEARCH_SQL_RESTRICTED = text(
    """
    SELECT entity_id, ts_rank_cd(tsv, websearch_to_tsquery('english', :query)) AS rank
      FROM engine.article_search
     WHERE tsv @@ websearch_to_tsquery('english', :query)
       AND entity_id = ANY(:candidate_ids)
     ORDER BY rank DESC
     LIMIT :limit
    """
)


def search_lexical(
    conn: Connection,
    query: str,
    *,
    limit: int,
    candidate_ids: list[int] | None = None,
) -> list[RankedHit]:
    """Best-first lexical hits for `query` against `engine.article_search`.
    No warm-up call is required before this (unlike the old `pg_temp`
    cache) -- the GIN index lives on the table itself and is already
    built by the time `now-search backfill-tsv` / the worker populated
    it."""
    if candidate_ids is not None:
        rows = conn.execute(
            _SEARCH_SQL_RESTRICTED,
            {"query": query, "limit": limit, "candidate_ids": candidate_ids},
        ).fetchall()
    else:
        rows = conn.execute(_SEARCH_SQL, {"query": query, "limit": limit}).fetchall()
    pairs = [(str(r[0]), float(r[1])) for r in rows]
    return to_ranked_hits(pairs)
