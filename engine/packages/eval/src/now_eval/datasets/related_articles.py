"""Related-articles labelled set (§17: precision@6 vs ~200
editor-labelled pairs).

No "related posts" plugin data exists in the archive (no YARPP tables,
no manual curation -- confirmed by grep over the extraction reports).
So "editor-labelled" here means what the task brief means by it: the
editor's own `_yoast_wpseo_primary_category` choice, which is a
deliberate single-category decision made by a human per article (not
the default/multi WP category assignment), used as the relatedness
signal. Two articles that share an editor-chosen primary category are
treated as "related"; nothing outside that category is.

This is a real limitation, stated plainly: primary-category overlap is
coarser than genuine "these two specific articles are related" judgment
a person would give if asked directly. It is, however, an actual
editorial signal at zero cost, exactly per the task brief, and it does
discriminate (see the trivial-baseline result in BASELINE.json: a
same-category-aware baseline scores far above random). A follow-up for
whoever builds the real related-articles surface (rails, E3.5+): once
it exists, spend a small editorial pass hand-labelling a "these are/are
not related" sample and replace or supplement this set -- do not treat
it as a permanent substitute for genuine pairwise judgment.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .sources import Article, load_category_priors_by_term_id, load_articles
from .split import is_eval

SAMPLE_SIZE = 200
MIN_CATEGORY_SIZE = 8  # so precision@6 = 1.0 is achievable (>=6 other members)


@dataclass(frozen=True)
class RelatedArticlesQuery:
    seed_article_id: str
    seed_wp_id: int
    seed_slug: str
    primary_category_id: int
    primary_category_name: str
    relevant_article_ids: tuple[str, ...]


def build_related_articles_labels(
    articles_path: Path | None = None,
    taxonomy_path: Path | None = None,
    *,
    sample_size: int = SAMPLE_SIZE,
    min_category_size: int = MIN_CATEGORY_SIZE,
    seed: str = "now-eval-related-v1",
) -> list[RelatedArticlesQuery]:
    priors_by_id = load_category_priors_by_term_id(taxonomy_path)
    articles = load_articles(articles_path)

    by_category: dict[int, list[Article]] = {}
    for article in articles:
        cat_id = article.primary_category_id
        if cat_id is None:
            continue
        prior = priors_by_id.get(cat_id)
        if prior is None or prior.is_print_issue:
            # Print-issue "categories" (34 of them) are magazine-issue
            # groupings, not topics -- excluded per taxonomy-mapping.md §0/§B.
            continue
        by_category.setdefault(cat_id, []).append(article)

    candidates: list[tuple[Article, int]] = []
    for cat_id, members in by_category.items():
        if len(members) < min_category_size:
            continue
        for article in members:
            if is_eval(article.wp_id):
                candidates.append((article, cat_id))

    ranked = sorted(
        candidates,
        key=lambda pair: hashlib.sha256(f"{seed}:{pair[0].wp_id}".encode()).hexdigest(),
    )

    queries: list[RelatedArticlesQuery] = []
    for article, cat_id in ranked[:sample_size]:
        members = by_category[cat_id]
        relevant = tuple(sorted(m.article_id for m in members if m.wp_id != article.wp_id))
        prior = priors_by_id[cat_id]
        queries.append(
            RelatedArticlesQuery(
                seed_article_id=article.article_id,
                seed_wp_id=article.wp_id,
                seed_slug=article.slug,
                primary_category_id=cat_id,
                primary_category_name=prior.name,
                relevant_article_ids=relevant,
            )
        )
    return queries
