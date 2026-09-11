"""Type-classification labelled set (§17: accuracy vs reviewed sample,
>=0.95 gate -- gates competitor exclusion, §8.A).

**Known limitation, stated plainly per the task's own instruction: this
is NOT a human-reviewed sample yet.** No classifier and no editorial
review pass exists (E2.1 is not built). What this module produces
instead is the strongest defensible proxy available today: articles
whose WP category maps to an L1 `type` at HIGH confidence *and* is not
flagged `per_article` in taxonomy-mapping.json (E1.4) -- i.e. categories
where the human editor's own filing decision is, per the architect's
review, essentially unambiguous evidence of L1 type (e.g. every article
filed under "Dining News" is a restaurant). See PROVENANCE.md for the
exact list of qualifying categories and their coverage gaps (no
drink/wellness/shop representation -- no HIGH-confidence,
category-certain WP category maps to those three L1 types in the
current corpus).

Before this metric is trusted as a real production gate, an editor
should spot-check a sample of these 200 (or replace them with a true
per-article reviewed sample) -- flagged as a follow-up for E2.1 in the
final report, not silently glossed over.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .sources import Article, CategoryPrior, iter_articles, load_category_priors
from .split import split_for

SAMPLE_SIZE = 200
MAX_PER_TYPE = 60


@dataclass(frozen=True)
class TypeLabel:
    article_id: str
    wp_id: int
    slug: str
    title: str
    type: str
    source_category: str
    label_provenance: str = "category_prior_high_confidence_not_human_reviewed"


def _qualifying_categories(priors: dict[str, CategoryPrior]) -> dict[str, str]:
    """category name -> L1 type, restricted to HIGH-confidence,
    category-certain (not per-article) priors."""
    return {name: p.type_ for name, p in priors.items() if p.type_is_category_certain and p.type_}


def build_type_labels(
    articles_path: Path | None = None,
    taxonomy_path: Path | None = None,
    *,
    sample_size: int = SAMPLE_SIZE,
    max_per_type: int = MAX_PER_TYPE,
    seed: str = "now-eval-type-labels-v1",
    split: str = "eval",
) -> list[TypeLabel]:
    """`split="eval"` (default) is the held-out CI-gate set E2.1 must
    never train against. `split="train"` draws from the complementary
    partition using the same category-prior logic -- used only to fit
    the most-popular baseline (sut.TrivialMostPopularSUT.fit_type) so
    that even the trivial baseline respects the hold-out it exists to
    validate, never to compute a reported metric."""
    if split not in ("eval", "train"):
        raise ValueError(f"split must be 'eval' or 'train', got {split!r}")
    priors = load_category_priors(taxonomy_path)
    qualifying = _qualifying_categories(priors)

    by_type: dict[str, list[Article]] = {}
    for article in iter_articles(articles_path):
        if split_for(article.wp_id) != split:
            continue
        matched_types = {qualifying[c] for c in article.categories if c in qualifying}
        if len(matched_types) != 1:
            # Zero matches (nothing to label) or >1 disagreeing matches
            # (ambiguous multi-category article) -- both excluded rather
            # than guessed at.
            continue
        (the_type,) = matched_types
        # Record which category matched for provenance (first match is fine --
        # matched_types has exactly one distinct type by construction above).
        source_category = next(c for c in article.categories if qualifying.get(c) == the_type)
        by_type.setdefault(the_type, []).append((article, source_category))  # type: ignore[arg-type]

    # Deterministic per-type sampling: sort candidates by a stable hash
    # of wp_id (not by list order, which is corpus insertion order and
    # would bias toward whichever type happens to appear first in the
    # file) and take up to max_per_type from each.
    ranked_by_type: dict[str, list[tuple[Article, str]]] = {}
    for the_type, pairs in by_type.items():
        ranked_by_type[the_type] = sorted(
            pairs,
            key=lambda pair: hashlib.sha256(f"{seed}:{pair[0].wp_id}".encode()).hexdigest(),
        )[:max_per_type]

    # Trim to sample_size by repeatedly shrinking the *currently
    # largest* type group by one, so a small group (e.g. `stay` with
    # only 45 candidates) is never squeezed out to make room for an
    # over-represented one (e.g. `eat`) -- stratification is preserved
    # rather than a flat global sample that would just mirror the
    # corpus's existing category skew.
    total = sum(len(v) for v in ranked_by_type.values())
    while total > sample_size:
        largest_type = max(ranked_by_type, key=lambda t: len(ranked_by_type[t]))
        ranked_by_type[largest_type].pop()
        total -= 1

    selected: list[TypeLabel] = []
    for the_type, pairs in sorted(ranked_by_type.items()):
        for article, source_category in pairs:
            selected.append(
                TypeLabel(
                    article_id=article.article_id,
                    wp_id=article.wp_id,
                    slug=article.slug,
                    title=article.title,
                    type=the_type,
                    source_category=source_category,
                )
            )
    return selected
