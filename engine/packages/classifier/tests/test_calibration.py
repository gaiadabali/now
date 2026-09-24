from __future__ import annotations

from now_classifier.facet_tagging.calibration import (
    ALIAS_EXCLUSIONS,
    MEASURED_PRECISION,
    SHIP_AT_OR_ABOVE,
    confidence_for,
    shipped_bands,
)


def test_every_shipped_band_clears_the_gate() -> None:
    """The whole point of calibration: nothing is shipped below the
    measured 0.80 bar. If this ever fails, a number was edited without
    re-measuring -- the exact mistake this module exists to prevent."""
    for facet, bands in MEASURED_PRECISION.items():
        for band, precision in bands.items():
            assert precision >= SHIP_AT_OR_ABOVE, f"{facet}/{band} = {precision} is below the ship bar"


def test_shipped_bands_matches_measured_precision_keys() -> None:
    for facet in MEASURED_PRECISION:
        assert shipped_bands(facet) == frozenset(MEASURED_PRECISION[facet])


def test_unmeasured_facet_ships_nothing() -> None:
    assert shipped_bands("not-a-real-facet") == frozenset()


def test_confidence_for_returns_none_for_unshipped_band() -> None:
    assert confidence_for("topic", "body") is None
    assert confidence_for("topic", "title") == MEASURED_PRECISION["topic"]["title"]


def test_alias_exclusions_reference_real_facets() -> None:
    valid_facets = set(MEASURED_PRECISION) | {"topic", "audience", "vibe", "cuisine", "occasion", "price_band"}
    for (facet, _slug), value in ALIAS_EXCLUSIONS.items():
        assert facet in valid_facets
        assert value == "*" or (isinstance(value, frozenset) and value)
