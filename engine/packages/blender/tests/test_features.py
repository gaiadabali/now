from __future__ import annotations

from now_filters.models import Candidate
from now_filters.type_relations import TypeRelation
from now_search.models import FusedHit

from now_blender.features import build_stage4_features

RELATIONS = {
    "stay": TypeRelation(type="stay", exclude_same=True, complements=("eat", "drink", "wellness")),
    "eat": TypeRelation(type="eat", exclude_same=True, complements=("stay", "drink")),
}


def _candidate(**kwargs) -> Candidate:
    base = dict(entity_type="article", entity_id=1)
    base.update(kwargs)
    return Candidate(**base)


def test_every_field_is_present_even_when_none():
    features = build_stage4_features(
        fused_hit=None,
        candidate=_candidate(),
        subject=None,
        relations=None,
        freshness=None,
        quality=None,
        popularity_prior=None,
        covis_score=None,
        already_read=None,
        position=1,
    )
    d = features.as_dict()
    expected_keys = {
        "semantic_sim", "bm25", "covis_score", "type_compat", "price_compat", "geo_distance",
        "same_area", "freshness", "quality", "popularity_prior", "user_facet_affinity",
        "user_vec_sim", "session_intent_sim", "author_affinity", "seen_before", "position_bias",
    }
    assert set(d.keys()) == expected_keys
    # Every field not explicitly given a value above must be None -- "log
    # as null, don't omit the field" (task brief) verified structurally.
    always_unavailable_today = [
        "covis_score", "user_facet_affinity", "user_vec_sim", "session_intent_sim", "author_affinity",
    ]
    for key in always_unavailable_today:
        assert d[key] is None
    assert d["position_bias"] == 1.0


def test_semantic_and_bm25_come_from_the_fused_hit():
    hit = FusedHit(entity_id="42", rrf_score=0.5, lexical_rank=3, semantic_rank=1, lexical_raw_score=1.2, semantic_raw_score=0.83)
    features = build_stage4_features(
        fused_hit=hit, candidate=_candidate(entity_id=42), subject=None, relations=None,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=None, position=1,
    )
    assert features.semantic_sim == 0.83
    assert features.bm25 == 1.2


def test_type_compat_zero_for_competitor_one_for_complement():
    subject = _candidate(entity_id=1, type="stay", price_band="luxury", area_term="senopati", lat=-6.2, lng=106.8)
    competitor = _candidate(entity_id=2, type="stay")
    complement = _candidate(entity_id=3, type="eat")
    neutral = _candidate(entity_id=4, type="do")

    f_competitor = build_stage4_features(
        fused_hit=None, candidate=competitor, subject=subject, relations=RELATIONS,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=None, position=1,
    )
    f_complement = build_stage4_features(
        fused_hit=None, candidate=complement, subject=subject, relations=RELATIONS,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=None, position=2,
    )
    f_neutral = build_stage4_features(
        fused_hit=None, candidate=neutral, subject=subject, relations=RELATIONS,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=None, position=3,
    )
    assert f_competitor.type_compat == 0.0
    assert f_complement.type_compat == 1.0
    assert f_neutral.type_compat == 0.5


def test_type_compat_none_without_a_subject():
    features = build_stage4_features(
        fused_hit=None, candidate=_candidate(type="eat"), subject=None, relations=RELATIONS,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=None, position=1,
    )
    assert features.type_compat is None


def test_seen_before_true_false_none():
    candidate = _candidate(entity_id=99)
    seen = frozenset({("article", 99)})

    f_seen = build_stage4_features(
        fused_hit=None, candidate=candidate, subject=None, relations=None,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=seen, position=1,
    )
    f_unseen = build_stage4_features(
        fused_hit=None, candidate=_candidate(entity_id=1), subject=None, relations=None,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=seen, position=1,
    )
    f_unknown = build_stage4_features(
        fused_hit=None, candidate=candidate, subject=None, relations=None,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=None, position=1,
    )
    assert f_seen.seen_before == 1.0
    assert f_unseen.seen_before == 0.0
    assert f_unknown.seen_before is None


def test_position_bias_is_always_available():
    features = build_stage4_features(
        fused_hit=None, candidate=_candidate(), subject=None, relations=None,
        freshness=None, quality=None, popularity_prior=None, covis_score=None, already_read=None, position=7,
    )
    assert features.position_bias == 7.0
