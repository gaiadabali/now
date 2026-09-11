"""`RailsOrchestrator` end to end against a real article: cache miss ->
compute + write, then cache hit -> read-through, no recomputation. Cleans
up its own `engine.rail_cache` rows."""

from __future__ import annotations

from sqlalchemy import text

from now_rails.models import RAIL_NAMES
from now_rails.orchestrator import ArticleNotFoundError, RailsOrchestrator


def _cleanup(conn, article_id: int) -> None:
    conn.execute(text("DELETE FROM engine.rail_cache WHERE article_id = :aid"), {"aid": str(article_id)})
    conn.commit()


def test_compute_rails_cold_then_warm(city_conn):
    row = city_conn.execute(text("SELECT id FROM public.articles ORDER BY id LIMIT 1")).first()
    article_id = row.id
    _cleanup(city_conn, article_id)

    orch = RailsOrchestrator.build(city_conn)
    try:
        cold = orch.compute_rails(article_id, k=5, rerank_pool=40)
        assert cold.cache_hit is False
        assert set(cold.rails.keys()) == set(RAIL_NAMES)
        assert cold.timing is not None
        assert cold.timing.total_ms > 0

        warm = orch.compute_rails(article_id, k=5, rerank_pool=40)
        assert warm.cache_hit is True
        assert set(warm.rails.keys()) == set(RAIL_NAMES)
        # Warm path must not recompute -- subject/row timings are exactly
        # zero because those functions are never called on a cache hit.
        assert warm.timing.subject_ms == 0.0
        assert warm.timing.row1_ms == 0.0
        assert warm.timing.row2_ms == 0.0
        assert warm.timing.row3_ms == 0.0
    finally:
        _cleanup(city_conn, article_id)


def test_unknown_article_raises(city_conn):
    orch = RailsOrchestrator.build(city_conn)
    try:
        orch.compute_rails(2_000_000_000, k=5)
        assert False, "expected ArticleNotFoundError"
    except ArticleNotFoundError:
        pass


def test_synthetic_overlay_never_cached(city_conn):
    row = city_conn.execute(text("SELECT id FROM public.articles ORDER BY id LIMIT 1")).first()
    article_id = row.id
    _cleanup(city_conn, article_id)

    orch = RailsOrchestrator.build(city_conn)
    try:
        bundle = orch.compute_rails(article_id, k=5, synthetic_overlay=True)
        assert bundle.synthetic_overlay is True
        assert bundle.cache_hit is False

        from now_rails.cache import read_cached_rails

        cached = read_cached_rails(city_conn, article_id, "default", list(RAIL_NAMES))
        assert cached == {}, "a synthetic-overlay result must never be written to the real cache"
    finally:
        _cleanup(city_conn, article_id)
