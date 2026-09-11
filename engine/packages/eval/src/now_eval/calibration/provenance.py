"""Pure lookup: (facet, confidence, source) -> the human-legible mechanism
in `now_classifier.confidence` that produced that number. No DB, no network.

This exists because of a finding from the parallel F101 audit that changed
this calibration's design: `now_classifier`'s `location` facet reuses the
number **0.90** for two mechanisms with completely different provenance --
`LOCATION_SITE_HOME_FALLBACK` (source="inferred": no signal at all, default
to the site's own home city) and `LOCATION_LITERAL_MATCH` (source="ai": a
place name was actually matched in the title). Averaging their accuracy
together under one number would hide whichever one is worse. `source`
disambiguates the two; `confidence` alone does not.

The audit's headline number: Jakarta's `location` review queue holds
**1,124 rows at confidence 0.75** -- every one a *category-fixed* location
(`source="inferred"`), meaning it is not a classifier guess at all but a
literal restatement of a decision `taxonomy-review.json` records as already
made by a human (`resolution.decided_by`), sitting under the same 0.75
number this package already flags (via `now_classifier.confidence`'s own
`CATEGORY_FIXED_CONFIDENCE["medium"]`) as one of the two values immediately
below the gate. Whether that number is really "0.75-accurate" or badly
under-priced is close to the single highest-leverage question this whole
calibration can answer, since it alone gates ~1,807 rows across both cities
(1,124 Jakarta + 683 Bali; see `location.py`).
"""
from __future__ import annotations

CATEGORY_FIXED = {0.95: "category_fixed_high", 0.75: "category_fixed_medium", 0.45: "category_fixed_low"}


def provenance_label(facet: str, confidence: float, source: str) -> str:
    conf = round(float(confidence), 2)
    if source == "inferred" and conf in CATEGORY_FIXED:
        return CATEGORY_FIXED[conf]
    if source == "inferred" and conf == 0.40:
        return "cue_abstain_fallback"
    if source == "ai" and conf == 0.93:
        return "cue_confident"
    if source == "ai" and conf == 0.72:
        return "cue_fired"
    if facet == "location":
        if source == "inferred" and conf == 0.90:
            return "site_home_fallback"
        if source == "ai" and conf == 0.90:
            return "title_match"
        if source == "ai" and conf == 0.55:
            return "lead_only_match"
    if facet == "subtype":
        # `now_classifier.confidence.SUBTYPE_KEYWORD_MATCH` (0.70) and
        # `SUBTYPE_NO_MATCH_FALLBACK` (0.35) are subtype's own two mechanisms,
        # distinct numbers from type/format's 0.72/0.40 cue bands -- no
        # overload to disambiguate here (unlike location's 0.90), but they
        # still need their own labels since they don't fit CATEGORY_FIXED.
        if source == "ai" and conf == 0.70:
            return "subtype_keyword_match"
        if source == "inferred" and conf == 0.35:
            return "subtype_no_match_fallback"
    return f"unrecognised:{facet}:{source}:{conf}"
