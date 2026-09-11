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
from now_search.models import ArticleSummary, SearchResult, SearchTiming
from now_search.rrf import DEFAULT_K as RRF_K
from now_search.rrf import reciprocal_rank_fusion

DEFAULT_LEXICAL_LIMIT = 100
DEFAULT_SEMANTIC_LIMIT = 100

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
        lexical_hits = lexical.search_lexical(
            self._conn, query, limit=lexical_limit, candidate_ids=candidate_ids
        )
        lexical_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        query_vec = query_embedder.embed_query(query)
        semantic_hits = semantic.search_semantic(
            self._conn,
            query_vec,
            model=query_embedder.model_name(),
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
