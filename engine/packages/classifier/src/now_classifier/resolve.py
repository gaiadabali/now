"""Per-article facet resolution: combines the D10-chosen category's
resolution (`review_doc.CategoryResolution`) with the per-article keyword
cue instrument (`now_taxonomy_evidence.features`) to produce a numeric-
confidence value for each of type / subtype / format / location.

One `FacetDecision` per facet-that-isn't-location, and a list of them for
location (multi-cardinality, required -- rules.location). Location also
takes a `category_fixed_locations` list separate from `d10` (F104): D10
picks one category to resolve the single-valued facets, but an article can
be filed under several categories at once, each independently fixing its
own location -- see `resolve_all_category_fixed_locations` and the comment
at its call site below.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from now_taxonomy_evidence.sources import Article

from .confidence import (
    CATEGORY_FIXED_CONFIDENCE,
    CUE_ABSTAIN_FALLBACK,
    CUE_CONFIDENT,
    CUE_FIRED,
    LOCATION_CATEGORY_FIXED_CONFIDENCE,
    LOCATION_LEAD_ONLY_MATCH,
    LOCATION_LITERAL_MATCH,
    LOCATION_SITE_HOME_FALLBACK,
    SUBTYPE_KEYWORD_MATCH,
    SUBTYPE_NO_MATCH_FALLBACK,
)
from .embed_routing import (
    CATEGORY_FIXED_HIGH,
    CATEGORY_FIXED_LOW,
    CATEGORY_FIXED_MEDIUM,
    CUE_CONFIDENT_BAND,
    CUE_FIRED_BAND,
    ROUTED_BANDS,
    CentroidModel,
)
from .embed_routing import route as embed_route
from .review_doc import CategoryResolution, D10Result
from .subtype import infer_subtype
from .vocabulary import TermIndex, term_uuid

HOME_LOCATION = {"jakarta": "jakarta", "bali": "bali"}


@dataclass
class FacetDecision:
    facet_key: str
    value: str | None
    confidence: float
    source: str  # "ai" | "inferred"
    reasoning: str
    # F120 routing: None (the default) means "no override -- db.py falls
    # back to the AUTO_APPLY_AT_OR_ABOVE gate on `confidence`, exactly as
    # before this ticket" (subtype, location, category_fixed_low,
    # cue_abstain_fallback all take this path, untouched). True/False is
    # set ONLY by the four routed type/format bands (see `embed_routing.
    # route`), and means "apply this decision regardless of where
    # `confidence` sits relative to the gate" -- Hansel's F120 acceptance
    # of auto-apply below 0.85 for those four measured, disclosed bands
    # specifically, not a blanket change to the gate itself.
    auto_apply: bool | None = None


@dataclass
class ClassificationResult:
    wp_id: int
    category_method: str
    category_name: str | None
    category_ambiguous: bool
    type: FacetDecision
    subtype: FacetDecision
    format: FacetDecision
    locations: list[FacetDecision] = field(default_factory=list)


def _argmax(scores: dict[str, float]) -> str | None:
    if not scores:
        return None
    return max(scores.items(), key=lambda kv: kv[1])[0]


def _mixed_categories_override(fixed_value: str | None, scores: dict[str, float]) -> tuple[str | None, str | None]:
    """`rules.mixed_categories` (jakarta/bali `taxonomy-review.json`): "The
    E2.0 value stays the prior unless the cue instrument gives it <= 10%
    support against >= 50% for the alternate, in which case the alternate
    becomes the prior." That rule was only ever consulted when an editor
    flagged a category `per_article` at review-pack authoring time. F106
    finding 7 found individual outliers the pack's own authors had no way to
    see up front -- a modern food-park piece forced into `editorial`/
    `heritage` because its WP category is "History & Heritage"; a
    hotel-opening press release forced into `editorial`/`city-guide` by
    "Explore Indonesia" when `stay`/`news` fits the text -- both categories
    NOT flagged per-article, so the old code had no path to correct them:
    the category-fixed branch below used `fixed_value` unconditionally.

    This applies the exact same, already-defined threshold test at
    classify-time to every category-fixed (non-per-article) type/format
    decision, not a new or looser policy: same 10%/50% cutoffs, same "prior
    stays unless the alternate clearly dominates" shape. `scores` must be
    the (unfiltered) cue-instrument scores dict, e.g. `features["type_scores"]`.
    Returns `(fixed_value, None)` -- unchanged -- whenever there isn't enough
    signal to apply the rule at all (no prior, no scores, or the cue
    instrument abstained entirely, i.e. every score is 0).
    """
    if not fixed_value or not scores:
        return fixed_value, None
    total = sum(scores.values())
    if total <= 0:
        return fixed_value, None
    prior_support = scores.get(fixed_value, 0.0) / total
    alt_value, alt_score = None, 0.0
    for value, score in scores.items():
        if value == fixed_value:
            continue
        if score > alt_score:
            alt_value, alt_score = value, score
    if alt_value is None:
        return fixed_value, None
    alt_support = alt_score / total
    if prior_support <= 0.10 and alt_support >= 0.50:
        note = (
            f"rules.mixed_categories override: cue instrument gives the category prior "
            f"'{fixed_value}' only {prior_support:.0%} support against '{alt_value}' at "
            f"{alt_support:.0%} -- the alternate becomes the value, per the pack's own rule."
        )
        return alt_value, note
    return fixed_value, None


def _category_fixed_band(conf_label: str) -> str:
    return {"high": CATEGORY_FIXED_HIGH, "medium": CATEGORY_FIXED_MEDIUM, "low": CATEGORY_FIXED_LOW}[conf_label]


def _apply_routing(
    facet: str,
    band_name: str,
    base_value: str | None,
    base_source: str,
    base_confidence: float,
    base_reasoning: str,
    article_vector: list[float] | None,
    centroid_models: dict[str, "CentroidModel"] | None,
) -> FacetDecision:
    """F120 routing entry point for the type/format facets ONLY (see
    `embed_routing`'s module docstring for the full decision). `band_name`
    is one of the six type/format bands this ticket's confidence numbers
    now key off of -- `category_fixed_{high,medium,low}` or
    `cue_{confident,fired}`/`cue_abstain_fallback`. Bands outside
    `ROUTED_BANDS` (category_fixed_low, cue_abstain_fallback) are returned
    completely unchanged: same value/confidence/source/reasoning as before
    this ticket, `auto_apply=None` so `db.py` falls back to the ordinary
    0.85 gate."""
    if band_name not in ROUTED_BANDS:
        return FacetDecision(facet, base_value, base_confidence, base_source, base_reasoning, auto_apply=None)
    model = (centroid_models or {}).get(facet)
    routed = embed_route(band_name, facet, base_value, base_source, article_vector, model)
    return FacetDecision(
        facet, routed.value, routed.confidence, routed.source,
        base_reasoning + routed.reasoning_suffix, auto_apply=routed.auto_apply,
    )


def classify_article(
    article: Article,
    d10: D10Result,
    features: dict,
    terms: TermIndex,
    title_location_hits: list[str] | None = None,
    lead_only_location_hits: list[str] | None = None,
    category_fixed_locations: list[tuple[str, str, str]] | None = None,
    article_vector: list[float] | None = None,
    centroid_models: dict[str, "CentroidModel"] | None = None,
) -> ClassificationResult:
    res: CategoryResolution | None = d10.resolution
    proposal = res.proposal if res else {}
    conf_label = res.confidence if res else "low"
    cat_name = res.name if res else None
    per_article = res.per_article if res else {"type", "subtype", "format", "location"}
    cat_base_conf = CATEGORY_FIXED_CONFIDENCE[conf_label]

    lead = article.text[:400]

    # --- type ---------------------------------------------------------
    fixed_type = proposal.get("type")
    if "type" in per_article:
        cue_value = features.get("type")
        margin = features.get("type_margin") or 0.0
        if cue_value:
            band_name = CUE_CONFIDENT_BAND if margin >= 2.0 else CUE_FIRED_BAND
            conf = CUE_CONFIDENT if margin >= 2.0 else CUE_FIRED
            reasoning = (
                f"Category '{cat_name}' flags type as per-article ({res.reasoning if res else ''}). "
                f"Keyword cue instrument scored '{cue_value}' with margin {margin:.2f}."
            )
            type_dec = _apply_routing("type", band_name, cue_value, "ai", conf, reasoning,
                                       article_vector, centroid_models)
        else:
            value = fixed_type or _argmax(features.get("type_scores") or {}) or "unknown"
            type_dec = FacetDecision(
                "type", value, CUE_ABSTAIN_FALLBACK, "inferred",
                f"Category '{cat_name}' flags type as per-article; keyword cue instrument abstained "
                f"(no cue cleared its margin threshold). Falling back to category prior "
                f"{'(' + fixed_type + ')' if fixed_type else '(none available -> best-guess/unknown)'}.",
            )
    else:
        type_scores = features.get("type_scores") or {}
        overridden_type, override_note = _mixed_categories_override(fixed_type, type_scores)
        value = overridden_type or _argmax(type_scores) or "unknown"
        reasoning = f"Category '{cat_name}' (confidence={conf_label}) fixes type={fixed_type or value}. {res.reasoning if res else ''}"
        if override_note:
            reasoning = f"{reasoning} {override_note}"
        band_name = _category_fixed_band(conf_label)
        type_dec = _apply_routing("type", band_name, value, "inferred", cat_base_conf, reasoning,
                                   article_vector, centroid_models)

    # --- format ---------------------------------------------------------
    fixed_format = proposal.get("format")
    if "format" in per_article:
        cue_value = features.get("format")
        margin = features.get("format_margin") or 0.0
        if cue_value:
            band_name = CUE_CONFIDENT_BAND if margin >= 2.0 else CUE_FIRED_BAND
            conf = CUE_CONFIDENT if margin >= 2.0 else CUE_FIRED
            reasoning = (
                f"Category '{cat_name}' flags format as per-article. Keyword cue instrument scored "
                f"'{cue_value}' with margin {margin:.2f}."
            )
            format_dec = _apply_routing("format", band_name, cue_value, "ai", conf, reasoning,
                                         article_vector, centroid_models)
        else:
            value = fixed_format or _argmax(features.get("format_scores") or {}) or "feature"
            format_dec = FacetDecision(
                "format", value, CUE_ABSTAIN_FALLBACK, "inferred",
                f"Category '{cat_name}' flags format as per-article; keyword cue instrument abstained. "
                f"Falling back to category prior "
                f"{'(' + fixed_format + ')' if fixed_format else '(none available -> best-guess feature)'}.",
            )
    else:
        # NOT applying `_mixed_categories_override` here -- measured, not assumed.
        # Re-run against the same 253 human-adjudicated verdicts used for F113: on
        # `format`, the override was net NEGATIVE (the 0.75 category-fixed band
        # dropped 0.580 -> 0.500 pooled), driven mainly by the `heritage` format
        # cue over-firing on culture/history FEATURE prose -- the identical
        # "topic vocabulary != category" failure this whole fix exists to correct,
        # here undermining the override's own arbiter. On `type` (see above) the
        # same override measured net-neutral (gains and losses cancelled exactly:
        # 0.640->0.640, 0.760->0.760), so it stayed enabled there. This is a
        # narrower scope than the literal `rules.mixed_categories` text implies
        # (which does not distinguish type from format), applied deliberately
        # because the format cue instrument is not yet reliable enough to safely
        # arbitrate an override -- not a silent widening, a disclosed restriction.
        value = fixed_format or _argmax(features.get("format_scores") or {}) or "feature"
        reasoning = f"Category '{cat_name}' (confidence={conf_label}) fixes format={value}. {res.reasoning if res else ''}"
        band_name = _category_fixed_band(conf_label)
        format_dec = _apply_routing("format", band_name, value, "inferred", cat_base_conf, reasoning,
                                     article_vector, centroid_models)

    # --- subtype ---------------------------------------------------------
    fixed_subtype = proposal.get("subtype")
    subtype_terms = terms.by_facet.get("subtype", {})
    if "subtype" in per_article:
        slug, matched = infer_subtype(article.title, lead, type_dec.value, subtype_terms)
        if matched:
            subtype_dec = FacetDecision(
                "subtype", slug, SUBTYPE_KEYWORD_MATCH, "ai",
                f"Category '{cat_name}' flags subtype as per-article. A subtype keyword for "
                f"'{slug}' (child of type={type_dec.value}) matched in the title/lead.",
            )
        else:
            value = fixed_subtype or "unresolved"
            subtype_dec = FacetDecision(
                "subtype", value, SUBTYPE_NO_MATCH_FALLBACK, "inferred",
                f"Category '{cat_name}' flags subtype as per-article; no child-of-{type_dec.value} "
                f"subtype keyword matched in the title/lead. "
                f"{'Falling back to category prior.' if fixed_subtype else 'No category prior either -- needs manual assignment.'}",
            )
    else:
        value = fixed_subtype or "unresolved"
        subtype_dec = FacetDecision(
            "subtype", value, cat_base_conf, "inferred",
            f"Category '{cat_name}' (confidence={conf_label}) fixes subtype={value}.",
        )

    # --- location (multi, required) -------------------------------------
    site_home = HOME_LOCATION[article.city]
    loc_candidates: dict[str, FacetDecision] = {}
    fixed_location = proposal.get("location")
    if fixed_location and fixed_location != "per-article":
        loc_base_conf = LOCATION_CATEGORY_FIXED_CONFIDENCE[conf_label]
        loc_candidates[fixed_location] = FacetDecision(
            "location", fixed_location, loc_base_conf, "inferred",
            f"Category '{cat_name}' (confidence={conf_label}) fixes location={fixed_location}. "
            f"[F113: category_fixed_{conf_label} measured {loc_base_conf:.2f} accuracy for location "
            f"specifically -- not the shared type/format/subtype CATEGORY_FIXED_CONFIDENCE number.]",
        )
    # F104: `location` is multi-cardinality, but the block above only ever
    # consulted the SINGLE category D10 chose to resolve type/subtype/format
    # -- correct for those single-valued facets, wrong here. An article can
    # be filed under more than one category at once, and a co-filed
    # category's own fixed location must not be lost just because D10's
    # tiering picked a *different* co-filed category (often a parent
    # container with no fixed location of its own, e.g. via Yoast's
    # primary-category pick) to drive the single-valued facets. Confirmed
    # live: Jakarta wp_ids 87586/88356/90002/91372/93158 carry
    # categories=['Bali Updates'] (fixes location=bali) but D10 resolved
    # type/subtype/format via a co-filed container ('Explore Indonesia',
    # location=None) -- so 'bali' was never added here at all, and a plain
    # title match on 'lombok' silently became the article's *only* location:
    # not applied, not gated, not queued, no trace. `category_fixed_locations`
    # (built by `review_doc.resolve_all_category_fixed_locations`, one entry
    # per co-filed category that fixes a location) closes that gap. This is
    # additive to the D10 winner's own fixed location above, not competing
    # with it -- the loop below is a no-op for a slug already seeded at an
    # equal-or-higher confidence.
    for slug, other_conf_label, other_cat_name in category_fixed_locations or []:
        other_conf = LOCATION_CATEGORY_FIXED_CONFIDENCE[other_conf_label]
        existing = loc_candidates.get(slug)
        if existing is None or other_conf > existing.confidence:
            loc_candidates[slug] = FacetDecision(
                "location", slug, other_conf, "inferred",
                f"Category '{other_cat_name}' (confidence={other_conf_label}), also carried by this "
                f"article alongside the category D10 chose for type/subtype/format, fixes "
                f"location={slug}. Location is multi-cardinality, so this is additive, not competing "
                f"(F104). [F113: category_fixed_{other_conf_label} measured {other_conf:.2f} for location.]",
            )
    for slug in title_location_hits or []:
        existing = loc_candidates.get(slug)
        if existing is None or LOCATION_LITERAL_MATCH > existing.confidence:
            loc_candidates[slug] = FacetDecision(
                "location", slug, LOCATION_LITERAL_MATCH, "ai",
                "Location name matched literally in the title (high-trust: a headline place "
                f"name is a deliberate editorial signal). [F113: title_match measured "
                f"{LOCATION_LITERAL_MATCH:.2f}.]",
            )
    for slug in lead_only_location_hits or []:
        if slug in loc_candidates:
            continue  # already have a stronger (title or category-fixed) source for this slug
        loc_candidates[slug] = FacetDecision(
            "location", slug, LOCATION_LEAD_ONLY_MATCH, "ai",
            f"Location name '{slug}' matched only in the lead paragraph, not the title. Originally "
            f"kept deliberately below the auto-apply gate pre-measurement (F95: lead-zone matches can "
            f"include false positives from Indonesian dish names that are also place names, e.g. "
            f"'nasi bali'/'siomay bandung') -- but F113 measured `lead_only_match` at "
            f"{LOCATION_LEAD_ONLY_MATCH:.2f} accuracy (17/17 adjudicated disagreements ruled correct), "
            f"so it now clears the gate on its own measured evidence, not the pre-measurement caution.",
        )
    # Guarantee at least one AUTO-APPLIED location per article (rules.location
    # is required): a lead-only hit alone is deliberately kept under the gate
    # (see above), so it does not count as "strong" here -- only a
    # category-fixed location or a title hit does.
    has_strong_candidate = (
        bool(fixed_location and fixed_location != "per-article")
        or bool(title_location_hits)
        or bool(category_fixed_locations)
    )
    if not has_strong_candidate:
        loc_candidates[site_home] = FacetDecision(
            "location", site_home, LOCATION_SITE_HOME_FALLBACK, "inferred",
            f"No category-fixed location and no title-level location match; rules.location."
            f"site_home_fallback applies ({article.city} -> {site_home}). "
            f"[F113: site_home_fallback measured {LOCATION_SITE_HOME_FALLBACK:.2f}.]",
        )

    return ClassificationResult(
        wp_id=article.wp_id,
        category_method=d10.method,
        category_name=cat_name,
        category_ambiguous=d10.ambiguous,
        type=type_dec,
        subtype=subtype_dec,
        format=format_dec,
        locations=list(loc_candidates.values()),
    )
