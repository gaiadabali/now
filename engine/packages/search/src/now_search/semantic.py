"""Semantic retrieval: pgvector kNN over `engine.embeddings`.

**Model filter, applied on every query -- not optional.** Per the task
brief: "`entity_id` is text holding the integer PK verbatim... Always
filter `WHERE model = :model`. The HNSW index does not discriminate by
model and several models will eventually coexist. A query without this
returns cross-model garbage." `_KNN_SQL` below has `AND model = :model`
in the WHERE clause on every code path -- there is no query variant in
this module that omits it.

`entity_id` join note: `engine.embeddings.entity_id` is `text` holding
`str(public.articles.id)` (verified: `now_embeddings.store.fetch_articles`
writes `str(article_id)`). This module casts it back with `entity_id::int`
to join/compare against `public.articles.id` -- exactly the
`entity_id::int = articles.id` pattern the task brief calls out.

**F67 -- the restricted path used to silently return zero rows.**
Root-caused with `EXPLAIN (ANALYZE, BUFFERS)` against real `now_jakarta`
data, not guessed: a naive `WHERE entity_id::int = ANY(:candidate_ids)
ORDER BY vec <=> :qvec LIMIT :limit` compiles to `Index Scan using
ix_embeddings_hnsw ... Filter: (... = ANY(...))`. `pgvector`'s HNSW is an
*approximate* index -- at this database's default `hnsw.ef_search = 40`
(`hnsw.iterative_scan` is also `off` here, so the index does not
automatically retry with a wider candidate list when the filter starves
it), the scan visits ~`ef_search` graph nodes *before* the `WHERE` filter
is applied, and returns whatever of those nodes happens to also satisfy
the filter. When `candidate_ids` is small and/or not clustered near the
query vector, none of the ~40 visited nodes need to intersect it. Proven
directly: restricting to the 40 *farthest* (least similar) ids from a
real subject vector, `EXPLAIN ANALYZE` shows `Index Scan using
ix_embeddings_hnsw` visiting exactly 40 rows (`Rows Removed by Filter:
40`) and returning **0 rows**, even though a plain `WHERE`-only count
against the same 40 ids confirms **all 40 are present** in the table.
No error, no warning -- a caller reads this as "nothing is similar",
which is exactly the failure E3.5/`now_rails.row3_similar` hit and
worked around with its own numpy exact-cosine (see that module's
`_restricted_semantic_knn` docstring for its own independent repro).

**Remedy chosen: never let the restricted path touch the ANN index at
all.** `_KNN_SQL_RESTRICTED` below applies the `entity_id`/`entity_type`/
`model` filter inside a `MATERIALIZED` CTE first (materialization is a
hard barrier in Postgres 12+ -- the planner cannot flatten it back into
one query and reintroduce the HNSW scan), which forces a plan of
`Seq Scan` (filter) -> `Sort` (exact `<=>` distance) -> `Limit`, i.e.
**exact, not approximate, cosine ranking over the restricted set**.
Verified with the same repro: 0 rows becomes the correct 10 rows, in
~2.7 ms end to end (`engine.embeddings` is ~5.2k rows across all
models/entity types today, so a full-table `Seq Scan` per restricted
query is cheap -- this is revisited if the table grows into the
hundreds of thousands of rows, at which point an indexed `entity_id`
column, out of this module's scope, would matter).

Other remedies were considered and rejected for *this* fix (see
PROGRESS.md F67 and this package's BENCHMARK.md for the write-up):
raising `hnsw.ef_search` only shrinks the failure probability, it does
not eliminate it (a restriction that happens to miss the wider candidate
list still returns silently-wrong zero rows); accepting exact cosine
only below a size threshold (what `now_rails` did, necessarily, since it
may not edit this module) requires picking and maintaining a threshold.
Exact-via-materialized-CTE is correct for every restriction size with no
threshold to tune, and is cheap at this table's current scale -- so it
is unconditional here, not threshold-gated.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_search.models import RankedHit
from now_search.rrf import to_ranked_hits

ENTITY_TYPE = "article"


def _vec_literal(vec: list[float]) -> str:
    # Same approach as now_embeddings.store._vec_literal: pgvector accepts
    # a text literal cast to ::vector; values here are always floats from
    # our own query_embedder, never user input, so an f-string build is
    # not an injection risk (same reasoning that module documents).
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


_KNN_SQL = text(
    """
    SELECT entity_id::int AS article_id, 1 - (vec <=> CAST(:qvec AS vector)) AS cosine_sim
      FROM engine.embeddings
     WHERE entity_type = :entity_type
       AND model = :model
     ORDER BY vec <=> CAST(:qvec AS vector)
     LIMIT :limit
    """
)

_KNN_SQL_RESTRICTED = text(
    """
    WITH candidates AS MATERIALIZED (
        SELECT entity_id::int AS article_id, vec
          FROM engine.embeddings
         WHERE entity_type = :entity_type
           AND model = :model
           AND entity_id::int = ANY(:candidate_ids)
    )
    SELECT article_id, 1 - (vec <=> CAST(:qvec AS vector)) AS cosine_sim
      FROM candidates
     ORDER BY vec <=> CAST(:qvec AS vector)
     LIMIT :limit
    """
)


def search_semantic(
    conn: Connection,
    query_vec: list[float],
    *,
    model: str,
    limit: int,
    candidate_ids: list[int] | None = None,
) -> list[RankedHit]:
    """Best-first semantic hits. `model` is required (no default) so a
    caller cannot forget it by omission -- see module docstring."""
    params = {"qvec": _vec_literal(query_vec), "entity_type": ENTITY_TYPE, "model": model, "limit": limit}
    if candidate_ids is not None:
        params["candidate_ids"] = candidate_ids
        rows = conn.execute(_KNN_SQL_RESTRICTED, params).fetchall()
    else:
        rows = conn.execute(_KNN_SQL, params).fetchall()
    pairs = [(str(r[0]), float(r[1])) for r in rows]
    return to_ranked_hits(pairs)
