"""Diversity (Sec.8.D) -- pure Python, no DB.
`max 1 per org` is tested against the exact scenario the ticket names:
"marriott.com appears 63x in the archive." """

from __future__ import annotations

from now_filters.diversity import DiversityCaps, default_facet_similarity, diversify
from now_filters.models import Candidate


def marriott_place(entity_id: int, **kw) -> Candidate:
    base = dict(entity_type="place", entity_id=entity_id, org_id="marriott.com", type="stay")
    base.update(kw)
    return Candidate(**base)


def test_max_one_per_org_even_with_63_marriott_candidates():
    candidates = [marriott_place(i, area_term=f"area{i % 5}") for i in range(63)]
    relevance = {c.key: 1.0 - i * 0.001 for i, c in enumerate(candidates)}  # all near-tied, highest id=0
    result = diversify(candidates, relevance, k=10)
    marriott_count = sum(1 for c in result if c.org_id == "marriott.com")
    assert marriott_count == 1
    assert len(result) == 1  # nothing else in the pool to fill remaining slots -- proves the cap, not starvation


def test_max_two_per_area():
    candidates = [
        Candidate(entity_type="place", entity_id=i, org_id=f"org{i}", area_term="senopati", type="eat")
        for i in range(5)
    ]
    relevance = {c.key: 1.0 for c in candidates}
    result = diversify(candidates, relevance, k=5, caps=DiversityCaps(max_per_area=2))
    assert len(result) == 2


def test_max_two_per_format():
    candidates = [
        Candidate(entity_type="article", entity_id=i, org_id=f"org{i}", format="news", type="editorial")
        for i in range(5)
    ]
    relevance = {c.key: 1.0 for c in candidates}
    result = diversify(candidates, relevance, k=5, caps=DiversityCaps(max_per_format=2))
    assert len(result) == 2


def test_max_one_paid_per_rail():
    candidates = [
        Candidate(entity_type="place", entity_id=i, org_id=f"org{i}", is_paid=True, type="eat") for i in range(4)
    ]
    relevance = {c.key: 1.0 for c in candidates}
    result = diversify(candidates, relevance, k=4, caps=DiversityCaps(max_paid_per_rail=1))
    assert sum(1 for c in result if c.is_paid) == 1


def test_diversity_still_fills_k_when_pool_has_enough_distinct_orgs():
    """Caps must not starve the rail when there IS enough variety --
    only when the pool itself lacks it (Sec.8.D is about diversity, the
    fallback ladder Sec.8.F is what handles genuine starvation)."""
    candidates = [
        Candidate(entity_type="place", entity_id=i, org_id=f"org{i}", area_term=f"area{i}", type="eat")
        for i in range(10)
    ]
    relevance = {c.key: 1.0 for c in candidates}
    result = diversify(candidates, relevance, k=8)
    assert len(result) == 8


def test_mmr_prefers_relevance_when_no_similarity_penalty_applies():
    a = Candidate(entity_type="place", entity_id=1, org_id="a", type="eat", subtype="cafe", area_term="x")
    b = Candidate(entity_type="place", entity_id=2, org_id="b", type="do", subtype="museum", area_term="y")
    relevance = {a.key: 0.9, b.key: 0.5}
    result = diversify([a, b], relevance, k=1)
    assert result == [a]


def test_mmr_penalizes_similarity_to_already_selected():
    """Two near-identical candidates (same type/subtype/area/price) with
    a close second by relevance but from a distinct org/area: at lambda
    0.7, similarity penalty should be able to flip the second pick."""
    a = Candidate(entity_type="place", entity_id=1, org_id="a", type="eat", subtype="cafe", area_term="x", price_band="moderate")
    a_twin = Candidate(entity_type="place", entity_id=2, org_id="a2", type="eat", subtype="cafe", area_term="x", price_band="moderate")
    distinct = Candidate(entity_type="place", entity_id=3, org_id="c", type="do", subtype="museum", area_term="y", price_band="luxury")
    relevance = {a.key: 1.0, a_twin.key: 0.95, distinct.key: 0.80}
    result = diversify([a, a_twin, distinct], relevance, k=2, lambda_=0.3)
    assert result[0] == a
    assert result[1] == distinct  # penalized twin loses to the lower-relevance-but-distinct candidate


def test_default_facet_similarity_bounds():
    a = Candidate(entity_type="place", entity_id=1, type="eat", subtype="cafe", area_term="x", price_band="moderate")
    identical = Candidate(entity_type="place", entity_id=2, type="eat", subtype="cafe", area_term="x", price_band="moderate")
    disjoint = Candidate(entity_type="place", entity_id=3, type="do", subtype="museum", area_term="y", price_band="luxury")
    assert default_facet_similarity(a, identical) == 1.0
    assert default_facet_similarity(a, disjoint) == 0.0
