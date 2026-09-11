"""Per-component score display -- ARCHITECTURE.md §7 "Blender":

    score = w_sem*semantic + w_cf*covis + w_fresh*decay(format) + w_qual*quality
          + w_geo*proximity + w_promo*boost - diversity_penalty

Weights live in `sites.ranking_weights` and are **E3.3's to tune** -- not
built yet, and explicitly out of this ticket's scope (`ARCHITECTURE.md`
§17: the Inspector is built *before* the public rails specifically so
E3.3 has something to tune against). Nothing in this repo defines
`w_sem`/`w_fresh`/`w_qual` today.

So `illustrative_blend()` below does two honest things and nothing more:

1. Lays out every component this article's candidate *could* contribute
   to a blend, each labelled with what it is and how it was derived
   (`semantic 0.71`, `quality 0.55`, `freshness 0.22`, ...), with
   `available=False` for `covis`/`geo`/`promo` since Row 1 covisitation,
   Row 2 proximity and promo-slot injection are not built (§7's
   "OFFLINE (worker)" column -- segment rail precompute -- doesn't exist
   yet either).
2. Computes one composite number using placeholder **equal weights**
   over only the available components, clearly labelled
   "ILLUSTRATIVE -- not the tuned blend; weights are equal-split
   placeholders, not `sites.ranking_weights`". This exists only so the
   per-result row has *a* combined number to eyeball while reading the
   individual components; it must never be mistaken for E3.3's real
   output.
"""

from __future__ import annotations

from dataclasses import dataclass

from now_inspector.models import ComponentExplained


@dataclass(frozen=True)
class BlendResult:
    components: list[ComponentExplained]
    illustrative_score: float | None
    note: str


def illustrative_blend(
    *,
    semantic_raw_score: float | None,
    rrf_score: float,
    quality_score: float | None,
    freshness_component: float | None,
) -> BlendResult:
    components = [
        ComponentExplained(
            key="semantic",
            label="semantic",
            value=semantic_raw_score,
            explanation="Cosine similarity between the query/seed embedding and this article's "
            "embedding (engine.embeddings, BAAI/bge-small-en-v1.5). Bounded [-1, 1]; empirically "
            "clusters ~0.4-0.9 for this model regardless of match quality (see now-search README).",
            available=semantic_raw_score is not None,
        ),
        ComponentExplained(
            key="rrf",
            label="rrf",
            value=rrf_score,
            explanation="Reciprocal Rank Fusion score combining this article's rank in the "
            "lexical and semantic rails (1/(k+rank), k=60). Not a blend component in §7's formula "
            "-- shown because it is what the search rail's own results are ordered by pre-blend.",
            available=True,
        ),
        ComponentExplained(
            key="quality",
            label="quality",
            value=quality_score,
            explanation="engine.quality_scores.score -- weighted blend of length/structure/media/"
            "yoast/author components (now-quality, E2.6). See the quality-components panel for the "
            "full breakdown.",
            available=quality_score is not None,
        ),
        ComponentExplained(
            key="freshness",
            label="freshness",
            value=freshness_component,
            explanation="Illustrative decay curve fitted to §4's format half-life table. "
            "Unavailable whenever `format` is NULL (not classified yet) or the format is "
            "evergreen/hard-expiry (no decay applies).",
            available=freshness_component is not None,
        ),
        ComponentExplained(
            key="covis",
            label="covis",
            value=None,
            explanation="Row 1 cross-type covisitation prior (§7). Not built -- no traffic yet to "
            "learn covisitation from; §7's cold-start formula (price/vibe/geo/taste compat) is "
            "Row-1-specific and out of this generic blend's scope.",
            available=False,
        ),
        ComponentExplained(
            key="geo",
            label="geo",
            value=None,
            explanation="Row 2 proximity score (PostGIS distance decay). Not computed here -- "
            "this Inspector view runs the search rails (lexical+semantic), not the Row 2 nearby "
            "rail.",
            available=False,
        ),
        ComponentExplained(
            key="promo",
            label="promo",
            value=None,
            explanation="Promo slot boost (§11 partnerships). Not built.",
            available=False,
        ),
    ]

    available = [c for c in components if c.available and c.value is not None and c.key != "rrf"]
    if available:
        illustrative_score = sum(c.value for c in available) / len(available)
    else:
        illustrative_score = None

    return BlendResult(
        components=components,
        illustrative_score=illustrative_score,
        note="ILLUSTRATIVE composite: unweighted mean of whichever of {semantic, quality, "
        "freshness} are available for this candidate. This is NOT E3.3's tuned blend -- "
        "sites.ranking_weights does not exist yet, and covis/geo/promo aren't built. Shown only "
        "so the per-component numbers above have one eyeball-able summary next to them.",
    )
