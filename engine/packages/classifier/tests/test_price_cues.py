from __future__ import annotations

from now_classifier.facet_tagging.price_cues import score_price_band


def test_luxury_signals_win() -> None:
    r = score_price_band(
        "Fine Dining at the New 5-Star Resort",
        "A luxurious tasting menu experience with a private villa and butler service.",
    )
    assert r.value == "luxury"
    assert r.confident is True


def test_budget_signals_win() -> None:
    r = score_price_band(
        "Best Street Food Warungs in Canggu",
        "Cheap and cheerful, these hawker stalls serve up affordable local dishes.",
    )
    assert r.value == "budget"


def test_no_signal_abstains() -> None:
    r = score_price_band("A Nice Day Out", "We had a lovely time and the weather was pleasant.")
    assert r.value is None


def test_weak_body_only_signal_cannot_win_alone() -> None:
    # No title anchor, and only a single weak cue occurrence -- stays
    # under NO_TITLE_CEILING (2.0) and under min_score (1.2).
    r = score_price_band(
        "A Nice Day Out",
        "filler text about the day " * 20 + "reasonably priced menu" + " more filler" * 20,
    )
    assert r.value is None


def test_repeated_lead_signal_can_cross_without_a_title_anchor() -> None:
    # price_band's own min_score (1.2) sits BELOW NO_TITLE_CEILING (2.0),
    # unlike now_taxonomy_evidence.text's type/format instrument -- a
    # repeated, unambiguous lead-zone price signal is allowed to win even
    # with no title support at all (see score_price_band's docstring).
    r = score_price_band(
        "A Nice Day Out",
        "fine dining " * 2 + "filler text about the day " * 20,
    )
    assert r.value == "luxury"
