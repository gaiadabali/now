from now_inspector.blender import illustrative_blend


def test_all_components_present_averages_three():
    r = illustrative_blend(semantic_raw_score=0.6, rrf_score=0.03, quality_score=0.5, freshness_component=0.4)
    assert abs(r.illustrative_score - (0.6 + 0.5 + 0.4) / 3) < 1e-9


def test_missing_components_marked_unavailable():
    r = illustrative_blend(semantic_raw_score=None, rrf_score=0.02, quality_score=0.5, freshness_component=None)
    by_key = {c.key: c for c in r.components}
    assert by_key["semantic"].available is False
    assert by_key["freshness"].available is False
    assert by_key["covis"].available is False
    assert by_key["geo"].available is False
    assert by_key["promo"].available is False
    assert r.illustrative_score == 0.5


def test_no_components_available_gives_none():
    r = illustrative_blend(semantic_raw_score=None, rrf_score=0.0, quality_score=None, freshness_component=None)
    assert r.illustrative_score is None
