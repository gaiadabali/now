"""Per-article subtype inference for categories that flag `subtype` as
`per_article`.

**Not specified by the rules.** `rules.mixed_categories` only describes what
happens to "the flagged facet" in general ("becomes per-article"); neither
it nor `rules.prior_resolution` gives a mechanism for resolving a per-article
*subtype* the way the keyword cue instrument already exists for `type` and
`format` (`now_taxonomy_evidence.text.score_type` / `score_format_full`).
This is this ticket's own addition to fill that gap, kept deliberately
simple and transparent to match the existing cue instrument's own
philosophy (crude, regex-based, evidence not a classifier): a case-
insensitive whole-word search for each candidate subtype's own label (and a
couple of hand-picked plurals) in the title + lead (first 400 chars),
restricted to subtypes that are children of the article's resolved `type`
so a "bar" mention cannot produce a `stay` subtype.
"""
from __future__ import annotations

import re

# label -> extra surface forms not covered by a plain case-insensitive
# substring match on the label itself (plurals, common short forms).
_EXTRA_FORMS: dict[str, list[str]] = {
    "restaurant": ["restaurants"],
    "cafe": ["cafes", "café", "cafés"],
    "bar": ["bars"],
    "hotel": ["hotels"],
    "resort": ["resorts"],
    "villa": ["villas"],
    "spa": ["spas"],
    "museum": ["museums"],
    "gallery": ["galleries"],
    "market": ["markets"],
    "mall": ["malls"],
    "festival": ["festivals"],
    "concert": ["concerts"],
}


def _patterns_for(slug: str, label: str) -> list[re.Pattern[str]]:
    forms = {label.lower()} | set(_EXTRA_FORMS.get(label.lower(), []))
    return [re.compile(r"\b" + re.escape(f) + r"\b", re.I) for f in forms]


def infer_subtype(
    title: str,
    lead: str,
    resolved_type: str | None,
    subtype_terms: dict[str, tuple[str, str | None]],
) -> tuple[str | None, bool]:
    """Returns (subtype_slug_or_None, matched). `subtype_terms` is
    `TermIndex.by_facet['subtype']`: slug -> (uuid, parent_slug)."""
    if not resolved_type:
        return None, False
    zone = f"{title} || {lead[:400]}"
    hits: list[str] = []
    for slug, (_uuid, parent_slug) in subtype_terms.items():
        if parent_slug != resolved_type:
            continue
        label = slug.replace("-", " ")
        for pat in _patterns_for(slug, label):
            if pat.search(zone):
                hits.append(slug)
                break
    if len(hits) == 1:
        return hits[0], True
    return None, False
