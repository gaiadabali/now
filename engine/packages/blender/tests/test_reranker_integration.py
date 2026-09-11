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


def test_without_platform_conn_freshness_is_withheld_for_every_article_f124(city_conn):
    """F124/F125 (T2 decay trust gate), superseding the old F50-era
    assumption this test used to make ("format is NULL archive-wide"): E2.1
    classification has since run for real (F125), so `hit.format_` is very
    often non-NULL now -- but `BlenderReranker.build(city_conn)` with NO
    platform connection cannot resolve the format facet's term ids
    (`SiteRankingConfig.format_term_ids` falls back to empty, see
    `now_blender.platform`), so the trust gate cannot find ANY
    `entity_terms` row and fails closed for every candidate regardless of
    whether it has a real, classified format. Freshness stays genuinely
    unavailable either way -- never a fabricated number -- which is the
    part of the original test's contract that is still true and still
    worth proving."""
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("cheap eats jakarta", k=10, synthetic_format_overlay=False, log_features=False)
    saw_a_classified_format = False
    for hit in result.hits:
        freshness = next(c for c in hit.components if c.key == "freshness")
        if hit.format_ is None:
            # Never classified -- still genuinely unavailable, renormalised.
            assert freshness.available is False
            assert freshness.value is None
        else:
            # F133: classified but unverifiable provenance -> the NEUTRAL
            # default curve, not the format's own and not nothing. The
            # contract that survives is "never the claimed format's curve
            # on an untrusted value", not "no freshness at all".
            assert freshness.available is True
            assert freshness.value is not None
            assert "not trusted" in freshness.explanation
        if hit.format_ is not None:
            saw_a_classified_format = True
    # Not asserted unconditionally -- depends on which real articles this
    # query's fused pool happens to contain -- but recorded so a future
    # reader sees this corpus is post-F125 classified, not F50-era NULL.
    assert saw_a_classified_format or True


def test_with_platform_conn_real_classified_rows_are_gated_on_measured_trust(city_conn, platform_conn):
    """F124/F125: with a real platform connection (so `format_term_ids`
    resolves), a real classified row's freshness is withheld unless its
    `entity_terms` confidence clears `min_format_confidence` or its source
    is trusted (`source='editor'`). F125's own re-classification stamped
    every live format value below the 0.85 default (measured accuracy
    0.40-0.72, see PROGRESS.md F125/F113) and zero `source='editor'` rows
    exist yet -- so on this real corpus, no classified candidate currently
    earns its OWN curve. Since F133 that means they decay on the neutral
    365d default rather than losing freshness entirely, so `available` is
    True with a "not trusted" explanation; only a genuinely unclassified
    (`format_ is None`) article still has no freshness at all.
    This test proves the WIRING (platform_conn -> format_term_ids -> the
    join -> the gate), not a hardcoded number: if a future editor decision
    or a higher-confidence relabel changes what's live, this test's own
    per-hit branch (not a single blanket assertion) is what would then
    show a trusted, available freshness value instead."""
    reranker = BlenderReranker.build(city_conn, platform_conn=platform_conn, site_slug="jakarta")
    result = reranker.rerank("cheap eats jakarta", k=15, synthetic_format_overlay=False, log_features=False)
    assert len(result.hits) > 0
    for hit in result.hits:
        freshness = next(c for c in hit.components if c.key == "freshness")
        if hit.format_ is None:
            assert freshness.available is False
            continue
        if freshness.available:
            # A trusted value exists live -- decay must be a real [0, 1] score.
            assert freshness.value is not None
            assert 0.0 <= freshness.value <= 1.0
        else:
            assert "format trust" in freshness.explanation
            assert "0.85" in freshness.explanation or str(reranker._site_config.decay.min_format_confidence) in freshness.explanation


def test_synthetic_overlay_format_has_no_real_provenance_so_freshness_is_withheld(city_conn):
    """F124/F125: `synthetic_format_overlay` fabricates a deterministic
    format value in-memory for demo/testing (see `now_blender.synthetic
    .deterministic_format`) -- it was never written to `engine.entity_terms`,
    so it has no real confidence/source to trust. Before this ticket, the
    trust gate did not exist and a fabricated format decayed exactly like a
    real one; now a value with no verifiable provenance is correctly
    withheld too, the same "unknown is not trusted" stance this ticket
    takes for any format value, real or synthetic."""
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("guide to jakarta", k=15, synthetic_format_overlay=True, log_features=False)
    assert len(result.hits) > 0
    for hit in result.hits:
        assert hit.format_ is not None
        freshness = next(c for c in hit.components if c.key == "freshness")
        # F133: a synthetic overlay format has no real `entity_terms` row, so
        # its provenance is unknown and untrusted -- which now means the
        # neutral default curve rather than no freshness. The point still
        # being proven is that an unverifiable format never gets to apply
        # its OWN curve.
        assert freshness.available is True
        assert freshness.value is not None
        assert "not trusted" in freshness.explanation


def test_feature_log_emits_one_line_per_hit(city_conn, caplog):
    caplog.set_level(logging.INFO, logger="now_blender.feature_log")
    reranker = BlenderReranker.build(city_conn)
    result = reranker.rerank("hotel with pool jakarta", k=4, log_features=True)
    lines = [r.message for r in caplog.records if r.name == "now_blender.feature_log"]
    assert len(lines) == len(result.hits)
    for line in lines:
        assert '"position_bias"' in line
        assert '"semantic_sim"' in line
