from __future__ import annotations

import pytest

from now_blender.blend import compute_blend
from now_blender.components import BlendComponents
from now_blender.weights import BlendWeights


def test_all_components_available_scores_near_one_when_all_maxed():
    weights = BlendWeights()
    components = BlendComponents(semantic=1.0, covis=1.0, freshness=1.0, quality=1.0, geo=1.0, promo=1.0)
    result = compute_blend(components, weights)
    assert result.normalized_score == pytest.approx(1.0)
    assert result.available_weight_sum == pytest.approx(1.0)
    assert all(c.available for c in result.components)


def test_missing_components_are_excluded_and_renormalized():
    weights = BlendWeights(w_sem=0.5, w_cf=0.2, w_fresh=0.1, w_qual=0.1, w_geo=0.05, w_promo=0.05)
    components = BlendComponents(semantic=0.8, covis=None, freshness=None, quality=0.6, geo=None, promo=None)
    result = compute_blend(components, weights)

    expected_available_weight = 0.5 + 0.1  # w_sem + w_qual only
    expected_raw = 0.5 * 0.8 + 0.1 * 0.6
    assert result.available_weight_sum == pytest.approx(expected_available_weight)
    assert result.raw_weighted_sum == pytest.approx(expected_raw)
    assert result.normalized_score == pytest.approx(expected_raw / expected_available_weight)

    by_key = {c.key: c for c in result.components}
    assert by_key["semantic"].available is True
    assert by_key["covis"].available is False
    assert by_key["covis"].value is None


def test_uniform_unavailability_does_not_change_relative_order():
    """The exact claim blend.py's docstring makes: when every candidate is
    missing the same terms (covis/geo/promo, today's reality), renormalization
    is a monotonic rescale and cannot flip an order that raw weighted sums
    would have produced."""
    weights = BlendWeights()
    a = BlendComponents(semantic=0.9, covis=None, freshness=None, quality=0.5, geo=None, promo=None)
    b = BlendComponents(semantic=0.6, covis=None, freshness=None, quality=0.9, geo=None, promo=None)

    result_a = compute_blend(a, weights)
    result_b = compute_blend(b, weights)

    raw_order = result_a.raw_weighted_sum > result_b.raw_weighted_sum
    normalized_order = result_a.normalized_score > result_b.normalized_score
    assert raw_order == normalized_order


def test_no_available_components_scores_zero_not_an_exception():
    weights = BlendWeights()
    components = BlendComponents()
    result = compute_blend(components, weights)
    assert result.normalized_score == 0.0
    assert result.available_weight_sum == 0.0
    assert all(not c.available for c in result.components)


def test_component_list_always_has_all_six_named_terms():
    weights = BlendWeights()
    result = compute_blend(BlendComponents(semantic=0.5), weights)
    keys = {c.key for c in result.components}
    assert keys == {"semantic", "covis", "freshness", "quality", "geo", "promo"}
