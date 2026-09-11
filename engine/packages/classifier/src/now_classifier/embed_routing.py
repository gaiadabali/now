"""F120 routing ("route now, LLM later"): for the four type/format
confidence bands where F118 (keyword-cue instrument) and F120 (embeddings
centroid instrument) were measured against the identical 253 human-
adjudicated labels, this module routes each band to whichever instrument
measured better ON IT, and stamps the MEASURED accuracy of the winning
instrument as the value's confidence -- never the old invented
0.95/0.93/0.75/0.72 numbers (F96/F111 already established those never
meant anything; F118/F120 measured what they actually deliver).

Routing table (PROGRESS.md, this ticket -- pooled type+format, both
cities, same two-stage estimator F118/F120 used):

    band                     old label   population  winner              measured accuracy
    category_fixed_high      0.95        9,095        keyword_cue          0.660
    cue_confident             0.93        3,535        embeddings_centroid  0.780
    category_fixed_medium    0.75        2,391        keyword_cue          0.610
    cue_fired                 0.72        979          embeddings_centroid  0.530

`category_fixed_low` (0.45) and the per-article cue-abstain fallback
(0.40) are DELIBERATELY NOT in this table: this ticket's routing decision
never measured an embeddings replacement for them, so they are out of
scope here and keep going to review unrouted, at their existing
`confidence.py` numbers, exactly as before this ticket.

Hansel's F120 acceptance ("route now, LLM later" -- see PROGRESS.md):
auto-apply below the old 0.85 `AUTO_APPLY_AT_OR_ABOVE` gate is fine for
these four routed bands specifically, because the client reviews
everything at the end -- the gate existed to protect against unreviewed
errors reaching readers, and that assumption no longer holds for this
one, measured, disclosed case. This is expressed as an explicit
`FacetDecision.auto_apply` override (see `resolve.py`/`db.py`), not a
change to `confidence.AUTO_APPLY_AT_OR_ABOVE` itself -- the gate still
governs every other facet/band untouched by this ticket (subtype,
location, category_fixed_low, cue_abstain_fallback).

Reuses `now_taxonomy_evidence.embed_similarity` (moved there from
`now_eval.calibration.embed_instrument` by this same ticket) for the
actual centroid math -- not a second implementation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from now_taxonomy_evidence.embed_similarity import Vector, centroid_predict

# --------------------------------------------------------------------------
# Routing table
# --------------------------------------------------------------------------

CATEGORY_FIXED_HIGH = "category_fixed_high"
CATEGORY_FIXED_MEDIUM = "category_fixed_medium"
CATEGORY_FIXED_LOW = "category_fixed_low"          # NOT routed
CUE_CONFIDENT_BAND = "cue_confident"
CUE_FIRED_BAND = "cue_fired"
CUE_ABSTAIN_BAND = "cue_abstain_fallback"          # NOT routed

KEYWORD_CUE = "keyword_cue"
EMBEDDINGS_CENTROID = "embeddings_centroid"

# Measured accuracy of the WINNING instrument for each routed band, PER
# FACET. F118/F120/this ticket's own PROGRESS.md table originally reported
# one number per band pooled across type+format (matching how
# `mapping.combine_across_cells` pools -- "the gate compares one float
# regardless of facet"). That pooling is fine for a gate threshold decision
# (a single number), but it is NOT fine for the number this ticket stamps
# onto every auto-applied VALUE as its measured confidence: `type` and
# `format` diverge enough per band that a pooled number misrepresents
# whichever facet is worse. Verified directly against the same 253-item
# two-stage estimate, facet-scoped instead of pooled (`engine/packages/
# eval/scripts/f120_facet_scoped_report.py`):
#
#   band                     facet     cue-only   centroid-CV   winner used below
#   category_fixed_high       type      0.760       0.680        keyword_cue  -> 0.760
#   category_fixed_high       format     0.560       0.340        keyword_cue  -> 0.560
#   cue_confident              type      0.520       0.840        embeddings   -> 0.840
#   cue_confident              format     0.380       0.720        embeddings   -> 0.720
#   category_fixed_medium     type      0.640       0.520        keyword_cue  -> 0.640
#   category_fixed_medium     format     0.580       0.300        keyword_cue  -> 0.580
#   cue_fired                  type      0.267       0.667        embeddings   -> 0.667
#   cue_fired                  format     0.300       0.400        embeddings   -> 0.400
#
# Pooling these (population-weighted, ~50/50 type/format split per band)
# reproduces F118/F120's own published pooled numbers exactly (e.g.
# (0.760+0.560)/2 = 0.660 for category_fixed_high) -- a live cross-check
# that this facet split is a refinement of the same measurement, not a
# different one. The WINNING INSTRUMENT is the same for both facets on
# every band (keyword_cue for the two category-fixed bands, embeddings for
# the two cue bands) -- only the stamped confidence differs -- so
# `ROUTED_INSTRUMENT` below stays keyed by band alone; only
# `ROUTED_CONFIDENCE` needs the facet.
ROUTED_CONFIDENCE: dict[tuple[str, str], float] = {
    (CATEGORY_FIXED_HIGH, "type"): 0.760,
    (CATEGORY_FIXED_HIGH, "format"): 0.560,
    (CUE_CONFIDENT_BAND, "type"): 0.840,
    (CUE_CONFIDENT_BAND, "format"): 0.720,
    (CATEGORY_FIXED_MEDIUM, "type"): 0.640,
    (CATEGORY_FIXED_MEDIUM, "format"): 0.580,
    (CUE_FIRED_BAND, "type"): 0.667,
    (CUE_FIRED_BAND, "format"): 0.400,
}
ROUTED_INSTRUMENT: dict[str, str] = {
    CATEGORY_FIXED_HIGH: KEYWORD_CUE,
    CUE_CONFIDENT_BAND: EMBEDDINGS_CENTROID,
    CATEGORY_FIXED_MEDIUM: KEYWORD_CUE,
    CUE_FIRED_BAND: EMBEDDINGS_CENTROID,
}
ROUTED_BANDS = frozenset(ROUTED_INSTRUMENT)

# An instrument that abstains (no article vector, or the class a centroid
# would have predicted was excluded for having too few labelled exemplars
# -- see `now_taxonomy_evidence.embed_similarity.build_trusted_centroids`)
# is not owed auto-apply just because its band was routed to it. F120:
# vectors exist for all 9,201 articles, so this should be near-zero in
# practice -- but principled rather than silently reusing a stale
# pre-routing number (0.93/0.72) if it ever does occur, which would be
# exactly the "invented number" mistake this ticket exists to end.
EMBEDDINGS_ABSTAIN_FALLBACK = 0.40

DEFAULT_CENTROID_ARTIFACT = Path(__file__).resolve().parent.parent.parent / "data" / "embed_routing_centroids.json"


@dataclass(frozen=True)
class CentroidModel:
    """Per-facet class centroids, loaded from the version-controlled
    artifact `embed_routing_centroids.json` (built once, offline, by
    `engine/packages/eval/scripts/build_routing_centroids.py` from the
    same 253-item human-adjudicated ground truth F118/F120 measured
    against -- ALL of it, not a CV fold: there is no held-out concern at
    deploy time, these are training exemplars now, not a test set).
    `excluded_classes` are classes that had fewer than the artifact's
    `min_class_n` labelled exemplars and are therefore never a candidate
    prediction -- see `embed_similarity.build_trusted_centroids`."""
    facet: str
    centroids: dict[str, Vector]
    class_n: dict[str, int]
    excluded_classes: frozenset[str]
    min_class_n: int

    def predict(self, vec: Vector | None) -> tuple[str | None, float, str]:
        """Returns (value, margin, abstain_reason); abstain_reason is ""
        on a real prediction."""
        if vec is None:
            return None, 0.0, "no_vector"
        if not self.centroids:
            return None, 0.0, "no_trusted_classes"
        value, margin = centroid_predict(vec, self.centroids)
        return value, margin, ""


def load_centroid_models(path: Path = DEFAULT_CENTROID_ARTIFACT) -> dict[str, CentroidModel]:
    """facet -> CentroidModel, read from the version-controlled JSON
    artifact. Returns {} (never raises) if the artifact is missing, so a
    checkout that hasn't built it yet degrades to "embeddings_centroid
    bands abstain, fall back to review" rather than crashing the whole
    classify run -- disclosed via the abstain path, not hidden."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, CentroidModel] = {}
    for facet, blob in data.get("facets", {}).items():
        out[facet] = CentroidModel(
            facet=facet,
            centroids={k: list(v) for k, v in blob["centroids"].items()},
            class_n=dict(blob["class_n"]),
            excluded_classes=frozenset(blob["excluded_classes"]),
            min_class_n=int(blob["min_class_n"]),
        )
    return out


@dataclass(frozen=True)
class RoutedDecision:
    value: str | None
    confidence: float
    source: str          # "ai" | "inferred", matching FacetDecision's convention
    reasoning_suffix: str
    auto_apply: bool


def route(
    band: str,
    facet: str,
    base_value: str | None,
    base_source: str,
    article_vector: Vector | None,
    centroid_model: CentroidModel | None,
) -> RoutedDecision:
    """Only ever called for `band in ROUTED_BANDS`. `facet` is `"type"` or
    `"format"` -- required because the measured confidence is FACET-scoped
    (see `ROUTED_CONFIDENCE`'s module-level comment: `type` and `format`
    diverge enough per band that a pooled number would misrepresent
    whichever facet is worse; the winning INSTRUMENT is the same for both
    facets on every band, only the stamped number differs). `base_value`/
    `base_source` are the PRE-routing decision (the keyword-cue/category-
    prior value already computed by `resolve.py` as before this ticket) --
    used unchanged when the band routes to keyword_cue, and as the abstain
    fallback when it routes to embeddings_centroid but this article has no
    trusted prediction available."""
    instrument = ROUTED_INSTRUMENT[band]
    confidence = ROUTED_CONFIDENCE[(band, facet)]

    if instrument == KEYWORD_CUE:
        suffix = (
            f" [F120 routing: band={band} facet={facet} -> {KEYWORD_CUE} (measured accuracy "
            f"{confidence:.3f} on the same 253-label two-stage estimate F118/F120 used, facet-scoped -- "
            f"see embed_routing.ROUTED_CONFIDENCE); auto-applied per Hansel's F120 acceptance of "
            f"auto-apply below 0.85 (the client reviews everything at the end).]"
        )
        return RoutedDecision(base_value, confidence, base_source, suffix, True)

    # instrument == EMBEDDINGS_CENTROID
    if centroid_model is None:
        suffix = (
            f" [F120 routing: band={band} facet={facet} -> {EMBEDDINGS_CENTROID}, but no centroid model "
            f"was loaded this run -- abstained; falling back to {KEYWORD_CUE}'s own value at "
            f"{EMBEDDINGS_ABSTAIN_FALLBACK:.2f}, unrouted, review-gated.]"
        )
        return RoutedDecision(base_value, EMBEDDINGS_ABSTAIN_FALLBACK, base_source, suffix, False)

    value, margin, abstain_reason = centroid_model.predict(article_vector)
    if abstain_reason:
        suffix = (
            f" [F120 routing: band={band} facet={facet} -> {EMBEDDINGS_CENTROID}, but this article "
            f"abstained ({abstain_reason}) -- falling back to {KEYWORD_CUE}'s own value at "
            f"{EMBEDDINGS_ABSTAIN_FALLBACK:.2f}, unrouted, review-gated (F120 did not measure this "
            f"fallback path as auto-apply-safe).]"
        )
        return RoutedDecision(base_value, EMBEDDINGS_ABSTAIN_FALLBACK, base_source, suffix, False)

    suffix = (
        f" [F120 routing: band={band} facet={facet} -> {EMBEDDINGS_CENTROID} (measured accuracy "
        f"{confidence:.3f} on the same 253-label two-stage estimate, facet-scoped; predicted-class "
        f"margin={margin:.3f}); auto-applied per Hansel's F120 acceptance of auto-apply below 0.85 (the "
        f"client reviews everything at the end).]"
    )
    return RoutedDecision(value, confidence, "ai", suffix, True)
