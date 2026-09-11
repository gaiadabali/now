"""End-to-end real-Postgres test: lexical + semantic + RRF + facets,
through the same `SearchEngine` the CLI and eval SUT use. This is the
only test in this package that loads the real fastembed ONNX model
(via `query_embedder`), so it is the slowest test here by a wide margin
(one-time model load) -- everything else mocks or sidesteps that cost
deliberately.
"""

from __future__ import annotations

from now_search.engine import SearchEngine


def test_search_end_to_end_returns_ranked_fused_hits(conn):
    se = SearchEngine(conn)
    warm = se.warm_up()
    assert warm.embedding_model_load_ms >= 0

    result = se.search("jakarta restaurant", k=10)
    assert len(result.hits) > 0
    assert len(result.hits) <= 10
    scores = [h.rrf_score for h in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert result.timing.total_ms > 0
    assert set(result.facet_counts.keys()) == {"type", "format"}


def test_second_search_on_same_connection_reuses_warm_embedding_model(conn):
    se = SearchEngine(conn)
    se.warm_up()
    first = se.search("bali beach", k=5)
    second = se.search("coffee shop", k=5)
    assert first.query != second.query
    # Embedding model already loaded, article_search is a real indexed
    # table -- both well under the p95 budget once warm.
    assert second.timing.total_ms < 500
