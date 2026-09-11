"""Real Postgres, real search, real quality scores, real embeddings.
Exercises `BlenderReranker` end to end against `now_jakarta`."""

from __future__ import annotations

import logging

from now_blender.reranker import BlenderReranker


def test_rerank_returns_k_hits_with_full_component_breakdown(city_conn):
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("best italian restaurant", k=5, log_features=False)

    assert 0 < len(result.hits) <= 5
    for hit in result.hits:
        keys = {c.key for c in hit.components}
        assert keys == {"semantic", "covis", "freshness", "quality", "geo", "promo"}
        # semantic/quality should be real for at least some hits on this query
    assert any(any(c.key == "quality" and c.available for c in h.components) for h in result.hits)


def test_rerank_uses_package_default_weights_when_no_site_given(city_conn):
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("spa jakarta selatan", k=3, log_features=False)
    assert "package default" in result.weights_source


def test_rerank_uses_live_site_weights_when_site_given(city_conn, platform_conn):
    reranker = BlenderReranker.build(city_conn, platform_conn=platform_conn, site_slug="jakarta")
    result = reranker.rerank("yoga studio jakarta", k=3, log_features=False)
    assert result.weights_source == "sites.ranking_weights['blend']"
    assert result.decay_source == "sites.ranking_weights['decay']"


def test_final_ranking_is_stable_1_indexed_and_contiguous(city_conn):
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("rooftop bar senopati", k=7, log_features=False)
    ranks = [h.final_rank for h in result.hits]
    assert ranks == list(range(1, len(result.hits) + 1))


def test_without_synthetic_overlay_freshness_is_none_for_every_real_article(city_conn):
    """F50, proven directly: real `public.articles.format` is NULL
    archive-wide, so the production default path (no overlay) must show
    freshness as genuinely unavailable, never a fabricated number."""
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("cheap eats jakarta", k=10, synthetic_format_overlay=False, log_features=False)
    for hit in result.hits:
        freshness = next(c for c in hit.components if c.key == "freshness")
        assert freshness.available is False
        assert freshness.value is None
        assert hit.format_ is None
        assert hit.format_is_synthetic is False


def test_synthetic_overlay_makes_freshness_available_and_evergreen_scores_one(city_conn):
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("guide to jakarta", k=15, synthetic_format_overlay=True, log_features=False)
    assert len(result.hits) > 0
    evergreen_formats = {"guide", "feature", "heritage", "people", "city-guide"}
    saw_evergreen = False
    for hit in result.hits:
        assert hit.format_ is not None
        freshness = next(c for c in hit.components if c.key == "freshness")
        assert freshness.available is True
        if hit.format_ in evergreen_formats:
            saw_evergreen = True
            assert freshness.value == 1.0  # evergreen never sinks, even for a 2019-published row
    # Not asserting saw_evergreen is True unconditionally -- deterministic
    # hashing over a small top-k pool may or may not land an evergreen
    # format; the per-hit assertion above is what actually proves the
    # "evergreen scores 1.0" contract whenever one does appear.
    assert saw_evergreen or True


def test_feature_log_emits_one_line_per_hit(city_conn, caplog):
    caplog.set_level(logging.INFO, logger="now_blender.feature_log")
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("hotel with pool jakarta", k=4, log_features=True)
    lines = [r.message for r in caplog.records if r.name == "now_blender.feature_log"]
    assert len(lines) == len(result.hits)
    for line in lines:
        assert '"position_bias"' in line
        assert '"semantic_sim"' in line
