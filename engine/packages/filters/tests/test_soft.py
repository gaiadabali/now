"""Soft/personalization filters (Sec.8.C) -- pure Python, no DB. The
central invariant under test: "Personalization never hard-filters" --
`compute_soft_weight` must never return 0 or negative for a candidate
with no facet/interaction data, and `apply_personalization_hard_filters`
must be the ONLY function in the module capable of removing a
candidate."""

from __future__ import annotations

import inspect

from now_filters.models import ActiveFacetFilters, Candidate
from now_filters import soft
from now_filters.soft import (
    SoftSignals,
    apply_personalization_hard_filters,
    compute_soft_weight,
)


def art(entity_id: int) -> Candidate:
    return Candidate(entity_type="article", entity_id=entity_id)


def test_no_signal_data_means_full_weight_no_penalty():
    c = art(1)
    weight = compute_soft_weight(c, SoftSignals())
    assert weight == 1.0


def test_low_affinity_down_weights_but_never_zeroes():
    c = art(1)
    signals = SoftSignals(
        facet_affinity={"cuisine:padang": 0.05},
        candidate_facets={c.key: frozenset({"cuisine:padang"})},
    )
    weight = compute_soft_weight(c, signals)
    assert 0.0 < weight < 1.0


def test_seen_not_clicked_down_weights_but_never_zeroes():
    c = art(1)
    signals = SoftSignals(seen_not_clicked=frozenset({c.key}))
    weight = compute_soft_weight(c, signals)
    assert 0.0 < weight < 1.0


def test_over_represented_area_down_weights():
    c = Candidate(entity_type="place", entity_id=1, area_term="senopati")
    weight_first = compute_soft_weight(c, SoftSignals(), area_counts_so_far={"senopati": 0})
    weight_saturated = compute_soft_weight(c, SoftSignals(), area_counts_so_far={"senopati": 5})
    assert weight_saturated < weight_first


def test_penalties_compound_multiplicatively_but_stay_positive():
    c = art(1)
    signals = SoftSignals(
        facet_affinity={"cuisine:padang": 0.0},
        candidate_facets={c.key: frozenset({"cuisine:padang"})},
        seen_not_clicked=frozenset({c.key}),
    )
    weight = compute_soft_weight(c, signals, already_read_weight=0.5, area_counts_so_far={"x": 10})
    assert weight > 0.0
    assert weight < 0.5  # every multiplier is <= 1, several < 1 here


def test_thumbs_down_is_hard_excluded():
    c1, c2 = art(1), art(2)
    filters = ActiveFacetFilters(thumbs_down_ids=frozenset({c1.key}))
    survivors = apply_personalization_hard_filters([c1, c2], filters)
    assert [c.entity_id for c in survivors] == [2]


def test_muted_facet_is_hard_excluded():
    c1, c2 = art(1), art(2)
    filters = ActiveFacetFilters(
        muted_facet_values=frozenset({"cuisine:padang"}),
        candidate_facet_values={c1.key: frozenset({"cuisine:padang"})},
    )
    survivors = apply_personalization_hard_filters([c1, c2], filters)
    assert [c.entity_id for c in survivors] == [2]


def test_algorithmic_signals_have_no_hard_filter_code_path():
    """Structural check on the invariant, not just a behavioural one:
    `apply_personalization_hard_filters` is the only function in
    `soft.py` whose signature accepts an `ActiveFacetFilters` -- there is
    no function here that could remove a candidate based on
    `SoftSignals` (affinity/seen-not-clicked/area) alone."""
    hard_filter_functions = [
        name
        for name, fn in inspect.getmembers(soft, inspect.isfunction)
        if "ActiveFacetFilters" in inspect.signature(fn).__str__()
    ]
    assert hard_filter_functions == ["apply_personalization_hard_filters"]
