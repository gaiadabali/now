from __future__ import annotations

import pytest

from now_blender.geo import (
    geo_distance_m,
    geo_proximity_component,
    haversine_m,
    price_compat,
    same_area,
)


def test_haversine_known_distance_jakarta_to_bali_roughly_correct():
    # Jakarta (-6.2, 106.8) to Denpasar (-8.65, 115.2) -- ~980km great-circle.
    d = haversine_m(-6.2, 106.8, -8.65, 115.2)
    assert 950_000 < d < 1_010_000


def test_haversine_zero_distance_for_identical_points():
    assert haversine_m(-6.2, 106.8, -6.2, 106.8) == pytest.approx(0.0, abs=1e-6)


def test_geo_distance_none_when_any_coordinate_missing():
    assert geo_distance_m(None, 106.8, -6.2, 106.8) is None
    assert geo_distance_m(-6.2, 106.8, None, None) is None


def test_geo_proximity_decays_with_distance_and_is_one_at_zero():
    assert geo_proximity_component(0.0) == pytest.approx(1.0)
    close = geo_proximity_component(500)
    far = geo_proximity_component(10_000)
    assert close > far
    assert geo_proximity_component(None) is None


def test_price_compat_identical_band_is_one():
    assert price_compat("moderate", "moderate") == 1.0


def test_price_compat_decays_with_ordinal_distance():
    adjacent = price_compat("budget", "moderate")
    far = price_compat("budget", "luxury")
    assert adjacent > far
    assert far == 0.0


def test_price_compat_none_for_unknown_band():
    assert price_compat("budget", "not-a-real-band") is None
    assert price_compat(None, "budget") is None


def test_same_area_true_false_none():
    assert same_area("senopati", "senopati") is True
    assert same_area("senopati", "kemang") is False
    assert same_area(None, "kemang") is None
