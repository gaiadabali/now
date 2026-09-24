from __future__ import annotations

import pytest

from now_classifier.facet_tagging.scope import ALL_FACETS, in_scope


@pytest.mark.parametrize("ptype", ["eat", "drink"])
def test_cuisine_in_scope_for_eat_and_drink(ptype: str) -> None:
    assert in_scope("cuisine", ptype) is True


@pytest.mark.parametrize("ptype", ["stay", "wellness", "shop", "do", "event", "editorial", None])
def test_cuisine_out_of_scope_otherwise(ptype: str | None) -> None:
    assert in_scope("cuisine", ptype) is False


@pytest.mark.parametrize("ptype", ["stay", "eat", "drink", "wellness", "shop"])
def test_price_band_in_scope_for_venue_types(ptype: str) -> None:
    assert in_scope("price_band", ptype) is True


@pytest.mark.parametrize("ptype", ["do", "event", "editorial", None])
def test_price_band_out_of_scope_for_non_venues(ptype: str | None) -> None:
    assert in_scope("price_band", ptype) is False


@pytest.mark.parametrize("facet", ["topic", "audience", "vibe", "occasion"])
@pytest.mark.parametrize("ptype", ["stay", "eat", "editorial", "do", None])
def test_unscoped_facets_apply_to_everything(facet: str, ptype: str | None) -> None:
    assert in_scope(facet, ptype) is True


def test_unknown_facet_raises() -> None:
    with pytest.raises(ValueError):
        in_scope("not-a-real-facet", "eat")


def test_all_facets_is_exactly_the_six_ws5_facets() -> None:
    assert ALL_FACETS == {"topic", "audience", "vibe", "cuisine", "occasion", "price_band"}
