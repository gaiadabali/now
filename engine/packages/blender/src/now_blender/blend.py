"""The §7 weighted blend -- **F39's resolution point**. See the package
README for the full design-decision writeup; the short version this
module encodes:

    score = w_sem*semantic + w_cf*covis + w_fresh*decay(format) + w_qual*quality
          + w_geo*proximity + w_promo*boost - diversity_penalty

RRF (`now_search.rrf`, untouched) already produced the candidate POOL
this module re-ranks -- rank-based fusion of two incomparable-scale
rails (BM25 vs. cosine) is what RRF is for for exactly this reason (see
that module's own docstring), and re-deriving a weighted sum straight
from raw BM25 + raw cosine would reintroduce the scale-mismatch problem
RRF exists to avoid. Downstream of fusion, though, every §7 term this
module computes IS already on a comparable, roughly-[0,1] scale
(cosine similarity, a quality score, an exponential decay factor, an
exponential proximity factor) -- so a weighted sum is meaningful HERE in
a way it would not be pre-fusion. `-diversity_penalty` is deliberately
NOT a seventh term subtracted in this module: it is `now_filters.
diversity.diversify`'s own `(1-lambda)*max_sim` term, applied by
`mmr.py` to the scores this module produces, treating this module's
output as exactly the `relevance` MMR's docstring says it greedily
re-picks against. One subtraction, one place, no double-counting.

## Renormalization over available components

Every candidate is scored only on the terms with a non-`None` value in
its `BlendComponents`; the weights of the unavailable terms are dropped
and the remaining weights rescaled to sum to 1 before use
(`raw_weighted_sum / available_weight_sum`). Two reasons, not one:

1. **Interpretability.** A candidate with every term available scores
   close to 1.0; a candidate scored on semantic+quality alone (today's
   reality for a plain search query -- no geo, no covis, no promo) ALSO
   scores close to 1.0 when it is a good semantic+quality match, rather
   than being capped near `w_sem + w_qual = 0.55` purely because three
   terms happen to be structurally unavailable for this surface.
2. **It does not change ranking ORDER when unavailability is uniform
   across the candidate pool** -- which is the case for every query this
   package's `reranker.py` runs today (no candidate in a plain keyword
   search has geo/covis/promo data; they are ALL missing the same three
   terms). Dividing every candidate's raw weighted sum by the same
   constant (`w_sem + w_fresh + w_qual`, whatever is available) is a
   monotonic rescaling -- it cannot reorder anything. Renormalization
   changes DISPLAYED magnitude, never the decision, in the uniform-
   availability case; it only changes ranking order in the (not-yet-
   reachable) mixed-availability case, e.g. some candidates having real
   geo distance and others not -- exactly where treating a missing
   term as if it scored 0 would otherwise unfairly bury them.
"""

from __future__ import annotations

from dataclasses import dataclass

from now_blender.components import BlendComponents, ComponentScore
from now_blender.weights import BlendWeights

_EXPLANATIONS: dict[str, str] = {
    "semantic": "Cosine similarity between the query embedding and this article's embedding "
    "(engine.embeddings, BAAI/bge-small-en-v1.5, model-filtered per F42). Real data.",
    "covis": "Cross-type covisitation prior from engine.covisitation. Real query against a real "
    "table -- currently 0 rows archive-wide (verified), gated behind E7.3 (~50k beacon sessions). "
    "Always None today, not a stub.",
    "freshness": "Type-aware exponential decay, ARCHITECTURE.md Sec.4 half-life table, read live "
    "from sites.ranking_weights['decay']. None whenever format is NULL, which is every real "
    "public.articles row today (F50) -- not computed on synthetic data in the production path.",
    "quality": "engine.quality_scores.score -- now-quality's E2.6 weighted blend "
    "(length/structure/media/yoast/author). Real data for all 4,772 articles.",
    "geo": "Exponential proximity decay from a subject location. None for plain keyword search "
    "(no subject place/article) -- populated when a subject with lat/lng is supplied (Row 1/2, "
    "E3.5-3.6).",
    "promo": "Partnership/campaign boost (Sec.11), capped within a relevance floor. Not built -- "
    "E4 (orgs/partnerships/campaigns) has not started.",
}


@dataclass(frozen=True)
class BlendResult:
    raw_weighted_sum: float
    available_weight_sum: float
    normalized_score: float
    components: list[ComponentScore]


def compute_blend(components: BlendComponents, weights: BlendWeights) -> BlendResult:
    named: list[tuple[str, float | None, float]] = [
        ("semantic", components.semantic, weights.w_sem),
        ("covis", components.covis, weights.w_cf),
        ("freshness", components.freshness, weights.w_fresh),
        ("quality", components.quality, weights.w_qual),
        ("geo", components.geo, weights.w_geo),
        ("promo", components.promo, weights.w_promo),
    ]

    raw_weighted_sum = 0.0
    available_weight_sum = 0.0
    scored: list[ComponentScore] = []
    for key, value, weight in named:
        available = value is not None
        if available:
            raw_weighted_sum += weight * value
            available_weight_sum += weight
        # F124/F125 (T2): `freshness_explanation` overrides the static
        # per-key text ONLY for `freshness`, and only when the caller
        # supplied one (e.g. the decay trust gate withheld this candidate's
        # value) -- every other key/candidate keeps the plain static text.
        explanation = _EXPLANATIONS[key]
        if key == "freshness" and components.freshness_explanation is not None:
            explanation = components.freshness_explanation
        scored.append(
            ComponentScore(
                key=key,
                label=key,
                value=value,
                weight=weight,
                explanation=explanation,
                available=available,
            )
        )

    normalized_score = raw_weighted_sum / available_weight_sum if available_weight_sum > 0 else 0.0

    return BlendResult(
        raw_weighted_sum=raw_weighted_sum,
        available_weight_sum=available_weight_sum,
        normalized_score=normalized_score,
        components=scored,
    )
