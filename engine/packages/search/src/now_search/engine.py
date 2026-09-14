"""Public orchestration API: `SearchEngine.search(query, k)` runs lexical
+ semantic retrieval in parallel-ish (sequential, both are single fast
queries -- see README for why threading wasn't worth it at these
latencies), fuses with RRF, and computes facet counts over the fused
candidate set. This is the one class both the CLI (`cli.py`) and the
eval SUT adapter (`now_search.eval_sut`) drive.

**Warm-up, post-F41**: the lexical side used to build a session-scoped
`pg_temp` cache here (~3-4s per connection) before F41's migration 0006
materialised `engine.article_search` as a real, persisted, GIN-indexed
table -- there is nothing left for the lexical side to warm up (see
`lexical.py`'s docstring for the history). `warm_up()` now only loads the
fastembed ONNX model for the semantic/query-embedding side, kept as its
own explicit step (rather than folded into the first `search()` call by
default) so a caller doing many queries can still see/log that one-time
cost separately from per-query timing, exactly as before.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from now_search import lexical, query_embedder, semantic
from now_search.facets import ActiveFilter, compute_facet_counts
from now_search.models import ArticleSummary, RankedHit, SearchResult, SearchTiming
from now_search.rrf import DEFAULT_K as RRF_K
from now_search.rrf import reciprocal_rank_fusion

DEFAULT_LEXICAL_LIMIT = 100
DEFAULT_SEMANTIC_LIMIT = 100

# Above this many ids, `candidate_ids` stops being a constraint and starts
# being a cost. ARCHITECTURE.md §8.G's rule ("constrain the vector search
# rather than post-filtering") holds when the candidate set is SELECTIVE;
# it inverts when the set is most of the corpus, because `= ANY(:ids)`
# with a large array defeats both indexes. Measured on the 4,772-article
# Jakarta corpus with a 3,421-id pool (the §8.A hard filter alone, no
# reader facets -- i.e. the DEFAULT request):
#
#     semantic   1.2ms  ->  49.2ms   (41x, HNSW degraded to a scan)
#     lexical   15.2ms  ->  49.3ms   (3.2x, GIN index bypassed)
#
# So a large set is applied AFTER retrieval instead, over-fetching to
# absorb the rows the filter drops. This is not "retrieve 100 and filter
# to 3" -- the case §8.G actually warns about is a *selective* filter,
# which still takes the constrained path below.
LARGE_CANDIDATE_SET = 1_000

# How much deeper to retrieve when post-filtering, to land `limit` rows
# that survive it. 4x covers a filter keeping >=25% of the corpus; below
# that `_retrieve` falls back to the constrained query rather than
# returning a short result set.
POST_FILTER_OVERFETCH = 4

_ARTICLE_SUMMARY_SQL = text(
    """
    SELECT id, title, dek, legacy_wp_id, legacy_permalink
      FROM public.articles
     WHERE id = ANY(:ids)
    """
)


@dataclass(frozen=True)
class WarmUpStats:
    embedding_model_load_ms: float


def _renumber(hits: list[RankedHit]) -> list[RankedHit]:
    """Re-1-indexes `rank` after post-filtering.

    RRF scores a hit by its *rank*, so leaving the pre-filter ranks in
    place (1, 4, 9, ...) would fuse differently from the constrained
    path, which never sees the dropped rows at all. Renumbering is what
    makes the two paths agree on the same answer.
    """
    return [
        RankedHit(entity_id=h.entity_id, rank=i, raw_score=h.raw_score)
        for i, h in enumerate(hits, start=1)
    ]


def _retrieve(
    fetch,
    *,
    limit: int,
    candidate_ids: list[int] | None,
) -> list[RankedHit]:
    """One retrieval rail, taking whichever of the two paths is cheaper.

    `fetch(limit, candidate_ids)` is the rail's own query function. It
    MUST be exact and complete in its unconstrained form -- i.e. asking
    for `n` returns the true best `n` whenever `n` rows exist. The
    post-filter path below reads a short result as "no more rows exist",
    so a rail whose unconstrained query is *approximate* would silently
    lose recall here. `lexical.search_lexical` qualifies (GIN, exact);
    `semantic.search_semantic` qualifies only when passed `exact=True`,
    which is why `SearchEngine.search` sets it -- see that function's
    docstring for the measured failure (limit=400 returning 28 rows) this
    rule exists to prevent.
    """
    if candidate_ids is None:
        return fetch(limit, None)
    if len(candidate_ids) <= LARGE_CANDIDATE_SET:
        return fetch(limit, candidate_ids)

    allowed = set(candidate_ids)
    deep_limit = limit * POST_FILTER_OVERFETCH
    raw = fetch(deep_limit, None)
    kept = [h for h in raw if int(h.entity_id) in allowed]
    if len(kept) < limit and len(raw) >= deep_limit:
        # The over-fetch filled up while more matching rows may exist
        # deeper -- only the constrained query can say.
        return fetch(limit, candidate_ids)
    return _renumber(kept[:limit])


class SearchEngine:
    def __init__(self, conn: Connection) -> None:
        """Takes an already-open Connection (not an Engine) for
        consistency with the pre-F41 shape of this class and because the
        semantic/facet queries below are still naturally scoped to one
        session; nothing about `engine.article_search` (a real,
        persisted table, unlike the old `pg_temp` cache) requires this
        anymore, but there is no reason to widen the contract for its
        own sake."""
        self._conn = conn
        self._warmed_up = False

    @classmethod
    def from_engine_dedicated_connection(cls, engine: Engine) -> "SearchEngine":
        """Convenience for callers happy to let this object own a
        connection checked out from `engine` for its own lifetime (the
        CLI and the eval SUT both do this)."""
        return cls(engine.connect())

    def warm_up(self) -> WarmUpStats:
        t0 = time.perf_counter()
        query_embedder.warm_up()
        embed_load_ms = (time.perf_counter() - t0) * 1000

        self._warmed_up = True
        return WarmUpStats(embedding_model_load_ms=embed_load_ms)

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        lexical_limit: int = DEFAULT_LEXICAL_LIMIT,
        semantic_limit: int = DEFAULT_SEMANTIC_LIMIT,
        rrf_k: float = RRF_K,
        candidate_ids: list[int] | None = None,
        active_filters: list[ActiveFilter] | None = None,
        compute_facets: bool = True,
    ) -> SearchResult:
        if not self._warmed_up:
            self.warm_up()

        t_start = time.perf_counter()

        t0 = time.perf_counter()
        lexical_hits = _retrieve(
            lambda lim, cids: lexical.search_lexical(
                self._conn, query, limit=lim, candidate_ids=cids
            ),
            limit=lexical_limit,
            candidate_ids=candidate_ids,
        )
        lexical_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        query_vec = query_embedder.embed_query(query)
        semantic_hits = _retrieve(
            lambda lim, cids: semantic.search_semantic(
                self._conn,
                query_vec,
                model=query_embedder.model_name(),
                limit=lim,
                candidate_ids=cids,
                # `_retrieve` requires an exact unconstrained fetch; the
                # default HNSW path is approximate and returns short.
                exact=True,
            ),
            limit=semantic_limit,
            candidate_ids=candidate_ids,
        )
        semantic_ms = (time.perf_counter() - t1) * 1000

        t2 = time.perf_counter()
        fused = reciprocal_rank_fusion(lexical_hits, semantic_hits, k=rrf_k)
        top = fused[:k]
        fuse_ms = (time.perf_counter() - t2) * 1000

        facet_counts: dict[str, dict[str, int]] = {}
        if compute_facets:
            fused_ids = [int(h.entity_id) for h in fused]
            facet_counts = compute_facet_counts(
                self._conn, candidate_ids=fused_ids, active_filters=active_filters or []
            )

        total_ms = (time.perf_counter() - t_start) * 1000

        return SearchResult(
            query=query,
            hits=top,
            facet_counts=facet_counts,
            timing=SearchTiming(
                lexical_ms=lexical_ms, semantic_ms=semantic_ms, fuse_ms=fuse_ms, total_ms=total_ms
            ),
            lexical_candidate_count=len(lexical_hits),
            semantic_candidate_count=len(semantic_hits),
        )

    def fetch_summaries(self, article_ids: list[int]) -> dict[int, ArticleSummary]:
        if not article_ids:
            return {}
        rows = self._conn.execute(_ARTICLE_SUMMARY_SQL, {"ids": article_ids}).fetchall()
        return {
            r.id: ArticleSummary(
                id=r.id, title=r.title, dek=r.dek, legacy_wp_id=r.legacy_wp_id, legacy_permalink=r.legacy_permalink
            )
            for r in rows
        }

    def close(self) -> None:
        self._conn.close()
