"""Numeric confidence, gated at `rules.confidence_gate.auto_apply_at_or_above`
(0.85, from taxonomy-review.json, matching PROGRESS.md's E2.1 spec).

**This mapping is this ticket's own invention, not something the taxonomy
review pack specifies.** The pack's per-category `confidence` is a label
(high/medium/low) and the keyword cue instrument (`now_taxonomy_evidence
.text`) produces a margin, not a 0..1 score -- neither the review JSON nor
ARCHITECTURE.md nor PROGRESS.md defines a label->number or margin->number
mapping anywhere. Reported as a decision made, per the ticket's own
instruction to say so rather than inventing a policy silently.

Rationale for the specific numbers:
- A category-FIXED facet (not flagged `per_article`) is a human decision
  recorded in the 27-answer review pack; "high" was explicitly re-checked by
  Hansel and/or the LLM second opinion and should clear the gate on its own.
  "low" categories are exactly the shaky ones the pack itself flags as
  needing a second look (Uncategorized, print issues with no prior, etc.)
  and should NOT auto-apply merely because a human wrote a category-level
  guess -- so "low" sits well under the gate.
- A `per_article`-flagged facet cannot inherit the category's own
  confidence at all (that is the entire reason it was flagged per-article:
  the category-wide prior is known to be wrong some of the time). Its
  number comes only from the cue instrument's own margin, using the same
  threshold the instrument already defines for its internal "confident"
  bit (margin >= 2x its own min_margin) -- reusing the instrument's own
  self-assessment rather than inventing a second one.
- A per-article facet whose cue abstains (no signal) falls back to the
  category's prior value, but at a confidence low enough to virtually
  always miss the gate -- an abstain is exactly the "we don't actually
  know" case the review queue exists for.
"""
from __future__ import annotations

AUTO_APPLY_AT_OR_ABOVE = 0.85

CATEGORY_FIXED_CONFIDENCE = {"high": 0.95, "medium": 0.75, "low": 0.45}

CUE_CONFIDENT = 0.93       # per-article cue fired with margin >= 2x its own min_margin
CUE_FIRED = 0.72           # per-article cue fired but below the "confident" margin
CUE_ABSTAIN_FALLBACK = 0.40  # cue abstained; falling back to the (per-article-flagged, so
                             # already-distrusted) category prior value

SUBTYPE_KEYWORD_MATCH = 0.70   # exactly one child-of-type subtype label matched in title/lead
SUBTYPE_NO_MATCH_FALLBACK = 0.35

# --- F113/F117 (2026-09-10): every location mechanism was measured against
# 405 of Hansel's real adjudication verdicts (the two-stage estimator also
# used for F118/F120's type/format work) and EVERY ONE cleared 0.85 on its
# own measured accuracy -- so, unlike type/format, location needed no
# routing/auto_apply-override machinery: replacing these invented numbers
# with the measured ones is sufficient on its own. F117 originally applied
# this as a one-time SQL promotion of already-pending rows; that fixed the
# rows that existed then but NOT future re-runs, which kept recomputing the
# OLD invented numbers below the gate and re-queuing thousands of already-
# resolved location facts back to `pending` -- caught live by this ticket's
# (F120's) own re-classification run regressing location's pending queue
# away from F117's zero. These constants are the permanent fix: measured
# accuracy baked into the classifier itself, not a one-off backfill.
#
# Location's category-fixed bands measured DIFFERENTLY from type/format's
# (0.86/1.00/1.00 vs type/format's four bands), so location gets its own
# dict rather than reusing the shared `CATEGORY_FIXED_CONFIDENCE` below --
# that dict is also still used, unmeasured, by `subtype` (F119, awaiting
# Hansel's own calibration queue), and silently changing it here would have
# repeated the exact "one measurement, applied to an un-measured facet"
# mistake F120's own routing work found and fixed for type/format's
# pooled-vs-per-facet numbers.
LOCATION_CATEGORY_FIXED_CONFIDENCE = {"high": 0.86, "medium": 1.00, "low": 1.00}

LOCATION_LITERAL_MATCH = 0.97     # title_match, F113 measured (was invented 0.90)
LOCATION_LEAD_ONLY_MATCH = 1.00   # lead_only_match, F113 measured (was invented 0.55, deliberately
                                   # cautious pre-measurement -- live-verified false positives from
                                   # Indonesian dish names that are also place names, e.g. "nasi
                                   # bali"/"siomay bandung", motivated that caution, but F113's
                                   # 17/17 adjudicated-correct result showed it was over-cautious)
LOCATION_CATEGORY_FIXED = None  # resolved to LOCATION_CATEGORY_FIXED_CONFIDENCE[label] at call site
LOCATION_SITE_HOME_FALLBACK = 0.87  # site_home_fallback, F113 measured (was invented 0.90) --
                                     # rules.location.required: an explicit, intentional default


def band(value: float) -> str:
    if value >= AUTO_APPLY_AT_OR_ABOVE:
        return "high"
    if value >= 0.6:
        return "medium"
    return "low"
