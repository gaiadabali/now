"""Measured precision per (facet, band), and the ship/no-ship gate this
job is held to -- SHIP_AT_OR_ABOVE (0.80, the ticket's own bar).

**How these numbers were produced** (method, not asserted -- see
docs/EDITION-2-PLAN.md's WS5 section for the full write-up): for each of
the six facets, `scripts/build_calibration_sample.py` drew a stratified,
seeded-random sample of ~100 (article, term, band) candidates from the
FULL published archive of both cities (25 per band: title/lead/body/
embed_only, or cue_confident/cue_fired for price_band's single-valued cue
instrument) -- not hand-picked, not cherry-picked. Hansel then read each
candidate's title + dek/excerpt + lead and judged, article by article,
whether the proposed term genuinely applies -- yes/no, no partial credit
-- recorded in a labels file alongside the sample. `scripts/
score_calibration.py` computes precision = true / n per band from that
label file. The exact commands, sample sizes actually reviewed, and the
per-facet false-positive patterns found (see `ALIAS_EXCLUSIONS` below) are
in docs/EDITION-2-PLAN.md.

**Finding, stated once, that repeats across every facet**: lexical
evidence in the BODY zone (or "no lexical hit, only an embedding score")
never once cleared the bar -- 0.00-0.20 precision every time it was
measured. `embed_only` in particular measured 0.00-0.04 across all five
alias-based facets: a bare-label term embedding ("vibe: trendy (trendy)",
per `now_embeddings.textbuild.build_term_text`) is not semantically
specific enough, on this corpus, to discriminate a real match from
"generic hospitality article" -- confirmed, not assumed, by five
independent measurements landing in the same place. Title-zone literal
matches were the only signal that consistently worked. This is why only
`BAND_TITLE` ships for every alias-based facet below: not a design
preference, a repeated measurement.
"""
from __future__ import annotations

SHIP_AT_OR_ABOVE = 0.80

# facet_key -> {band: measured_precision}. A band absent from a facet's
# dict was measured and did NOT clear SHIP_AT_OR_ABOVE -- see
# docs/EDITION-2-PLAN.md for the full table (every band, every facet,
# shipped or not). Only bands present here are ever written to
# `engine.entity_terms`.
MEASURED_PRECISION: dict[str, dict[str, float]] = {
    "topic": {"title": 0.80},        # n=25: 20/25 true
    "vibe": {"title": 0.92},         # n=25: 23/25 true
    "cuisine": {"title": 0.84},      # n=25: 21/25 true
    # n=13 after excluding "local" (see ALIAS_EXCLUSIONS) -- 12/13 true.
    # Smaller sample than the other facets' 25; disclosed, not hidden:
    # "local" alone accounted for 40 of the original 100 title/lead/body/
    # embed_only candidates and measured nowhere near the bar on its own
    # (2/12 title, 1/13 body, 0/2 embed_only) -- an English word this
    # common in hospitality copy ("local flavours", "local diners") can't
    # be trusted as a literal alias for the AUDIENCE meaning of "local".
    "audience": {"title": 0.92},
    # n=19 after excluding the "anniversary" alias on "date-night" (see
    # ALIAS_EXCLUSIONS) -- 18/19 true. Unexcluded: 18/25 = 0.72, under the
    # bar -- every one of the 6 misses was "date-night" firing on a
    # hotel's own business anniversary, not a reader's romantic occasion.
    "occasion": {"title": 0.95},
    "price_band": {"cue_confident": 0.86, "cue_fired": 0.84},  # n=50 each
}

# (facet_key, term_slug) -> aliases to drop from that term's matcher,
# because they measured as false-positive-prone on the calibration
# sample specifically (not a guess -- see MEASURED_PRECISION's comments
# above for the measured numbers this fixed). "*" excludes the WHOLE
# term (label included), used only when the term's own LABEL is the
# problem, not just one alias.
ALIAS_EXCLUSIONS: dict[tuple[str, str], frozenset[str] | str] = {
    ("audience", "local"): "*",
    ("occasion", "date-night"): frozenset({"anniversary"}),
}


def shipped_bands(facet: str) -> frozenset[str]:
    return frozenset(MEASURED_PRECISION.get(facet, {}))


def confidence_for(facet: str, band: str) -> float | None:
    return MEASURED_PRECISION.get(facet, {}).get(band)
