"""The Sec.10 stage-4 feature vector -- the exact 16 named fields:

    semantic_sim, bm25, covis_score, type_compat, price_compat,
    geo_distance, same_area, freshness, quality, popularity_prior,
    user_facet_affinity, user_vec_sim, session_intent_sim,
    author_affinity, seen_before, position_bias

"Logged at serve time while the blender is still hand-tuned, so the
training set accumulates" -- six months of these is what makes the
LambdaMART re-ranker (E7.6) possible. Every field is `Optional[float]`
(`seen_before` optional[bool], serialized as 0.0/1.0/null) and **always
present in the logged record even when unavailable** -- `None`/`null`,
never a dropped key -- so a future consumer never has to distinguish
"this feature didn't exist yet" from "this field was 0". Today, 10 of
16 fields are structurally `None` for every real query (no facets, no
user profiles, no covisitation traffic, no session state, no author
affinity model) -- see `StageFourFeatures`'s field-by-field docstring
below for exactly why each one is or isn't available, and README.md's
acceptance-criteria section for the summary table.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from now_filters.models import Candidate
from now_filters.type_relations import TypeRelation, is_competitor
from now_search.models import FusedHit

from now_blender.geo import geo_distance_m, price_compat, same_area


@dataclass(frozen=True)
class StageFourFeatures:
    semantic_sim: float | None  # RAILS: cosine sim, RRF FusedHit.semantic_raw_score. Real when candidate hit the semantic rail.
    bm25: float | None  # ts_rank_cd, RRF FusedHit.lexical_raw_score. Real when candidate hit the lexical rail.
    covis_score: float | None  # engine.covisitation; None -- 0 rows archive-wide (see covisitation.py).
    type_compat: float | None  # subject present + both types known -> 1.0 complement / 0.0 not. None: no subject (plain search).
    price_compat: float | None  # geo.price_compat. None: no subject price band (plain search / articles have none).
    geo_distance: float | None  # meters, geo.geo_distance_m. None: no subject lat/lng (plain search).
    same_area: float | None  # 1.0/0.0, geo.same_area. None: no subject area_term (plain search).
    freshness: float | None  # decay.freshness_component. None: format is NULL for every real article (F50).
    quality: float | None  # engine.quality_scores.score. Real for all 4,772 articles.
    popularity_prior: float | None  # engine.quality_scores.components.popularity.prior_score. Real (mostly 0.0 -- see README).
    user_facet_affinity: float | None  # E7.2, not built. Always None.
    user_vec_sim: float | None  # E7.2 taste embedding, not built. Always None.
    session_intent_sim: float | None  # Sec.10 "two speeds" intent vector, not built. Always None.
    author_affinity: float | None  # user<->author affinity model, not built. Always None.
    seen_before: float | None  # 1.0/0.0 from caller-supplied SessionState.already_read. None if no session state given.
    position_bias: float | None  # 1-indexed final serve position -- always known at serve time by construction.

    def as_dict(self) -> dict:
        return asdict(self)


def build_stage4_features(
    *,
    fused_hit: FusedHit | None,
    candidate: Candidate,
    subject: Candidate | None,
    relations: dict[str, TypeRelation] | None,
    freshness: float | None,
    quality: float | None,
    popularity_prior: float | None,
    covis_score: float | None,
    already_read: frozenset[tuple[str, int]] | None,
    position: int,
) -> StageFourFeatures:
    type_compat: float | None = None
    if subject is not None and subject.type is not None and candidate.type is not None and relations is not None:
        # A complement is a co-recommendation, not a competitor -- see
        # now_filters.type_relations module docstring. type_compat asks
        # "is this a good complementary pick", i.e. NOT a competitor and
        # (if the taxonomy models it) an explicit complement.
        relation = relations.get(subject.type)
        is_complement = relation is not None and candidate.type in relation.complements
        type_compat = 0.0 if is_competitor(relations, subject.type, candidate.type) else (1.0 if is_complement else 0.5)

    seen_before: float | None = None
    if already_read is not None:
        seen_before = 1.0 if candidate.key in already_read else 0.0

    return StageFourFeatures(
        semantic_sim=fused_hit.semantic_raw_score if fused_hit else None,
        bm25=fused_hit.lexical_raw_score if fused_hit else None,
        covis_score=covis_score,
        type_compat=type_compat,
        price_compat=price_compat(subject.price_band if subject else None, candidate.price_band),
        geo_distance=geo_distance_m(
            subject.lat if subject else None, subject.lng if subject else None, candidate.lat, candidate.lng
        ),
        same_area=(
            None
            if same_area(subject.area_term if subject else None, candidate.area_term) is None
            else float(same_area(subject.area_term if subject else None, candidate.area_term))
        ),
        freshness=freshness,
        quality=quality,
        popularity_prior=popularity_prior,
        user_facet_affinity=None,
        user_vec_sim=None,
        session_intent_sim=None,
        author_affinity=None,
        seen_before=seen_before,
        position_bias=float(position),
    )
