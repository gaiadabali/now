"""Facet-tagging labelled set (§17: precision/recall vs held-out Yoast
labels, >=0.85 gate before auto-apply).

Ground truth: `_yoast_wpseo_focuskw`, the editor's own free-text topic
label for the article (per the task brief: "the editor's own topic
label"). Normalized to a slug (lower-case, non-alnum -> '-') so it is
directly comparable to the slug-shaped facet vocabulary in
`engine/packages/taxonomy` (e.g. "Rooftop Bar" -> "rooftop-bar") rather
than doing free-text similarity matching, which would make the metric
fuzzy and hard to gate on.

**Known limitation, stated plainly:** a focus keyword is an SEO
keyphrase, not always a member of the §4 controlled facet vocabulary
(vibe/cuisine/occasion/audience/amenities/price_band/topic) -- many are
proper nouns ("Clarissa Goenawan", an author's name) that a real facet
tagger would never emit and should not be penalized for missing. This
harness reports precision/recall as specified regardless, since that is
what the task and ARCHITECTURE.md §17 ask for, but whoever consumes the
number for E2.2 should read PROVENANCE.md's caveat before treating 0.85
as achievable on 1:1 focus-keyword recall -- a real facet tagger's
recall against *this specific* held-out set has a natural ceiling below
1.0 for reasons that have nothing to do with tagging quality (see
`docs/facet-label-quality.md`-equivalent note in PROVENANCE.md).

Held out per `split.is_eval` -- E2.2 must not train or tune weights
against these specific rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .sources import iter_articles
from .split import is_eval


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return slug.strip("-")


@dataclass(frozen=True)
class FacetLabel:
    article_id: str
    wp_id: int
    slug: str
    focus_keyword_raw: str
    facet_labels: tuple[str, ...]


def build_facet_labels(articles_path: Path | None = None) -> list[FacetLabel]:
    out: list[FacetLabel] = []
    for article in iter_articles(articles_path):
        if not is_eval(article.wp_id):
            continue
        if not article.focus_keyword:
            continue
        facet_slug = slugify(article.focus_keyword)
        if not facet_slug:
            continue
        out.append(
            FacetLabel(
                article_id=article.article_id,
                wp_id=article.wp_id,
                slug=article.slug,
                focus_keyword_raw=article.focus_keyword,
                facet_labels=(facet_slug,),
            )
        )
    out.sort(key=lambda fl: fl.wp_id)
    return out
