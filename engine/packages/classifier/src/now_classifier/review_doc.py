"""Loads `<city>/site/taxonomy-review.json` -- the 27-answer, per-category
resolved proposal pack that is THE authority for this ticket -- and resolves
D10 (`rules.prior_resolution`: yoast_primary -> deepest_child ->
parent_container) to pick one category per article.

Nothing here recomputes what the evidence pack already decided per category
(the `proposal` field). This module only ever: (1) loads that pack, and
(2) picks WHICH category's proposal applies to a given article when it
carries more than one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from now_taxonomy_evidence.sources import Article, Category, find_repo_root


@dataclass
class CategoryResolution:
    term_id: int
    name: str
    slug: str
    container: bool
    confidence: str  # "high" | "medium" | "low"
    reasoning: str
    proposal: dict[str, Any]  # type, subtype, format, location, per_article, facets, series_key
    decisions: list[str]

    @property
    def per_article(self) -> set[str]:
        return set(self.proposal.get("per_article") or [])


@dataclass
class ReviewDoc:
    city: str
    rules: dict[str, Any]
    by_term_id: dict[int, CategoryResolution]
    raw: dict[str, Any]


def load_review_doc(city: str, root: Path | None = None) -> ReviewDoc:
    root = root or find_repo_root()
    path = root / city / "site" / "taxonomy-review.json"
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    by_term_id: dict[int, CategoryResolution] = {}
    for c in doc["categories"]:
        tid = c.get("term_id")
        if tid is None:
            continue  # no join key -> cannot be resolved to a WP category; handled as "no prior" upstream
        by_term_id[tid] = CategoryResolution(
            term_id=tid,
            name=c["name"],
            slug=c.get("slug") or "",
            container=bool(c.get("container")),
            confidence=c.get("confidence") or "low",
            reasoning=c.get("reasoning") or "",
            proposal=c.get("proposal") or {},
            decisions=list(c.get("decisions") or []),
        )
    return ReviewDoc(city=city, rules=doc["rules"], by_term_id=by_term_id, raw=doc)


@dataclass
class D10Result:
    resolution: CategoryResolution | None
    method: str  # "yoast_primary" | "deepest_child" | "parent_container" | "none"
    ambiguous: bool = False  # True when deepest_child had >1 non-container candidate and a tiebreak was needed


def resolve_article_category(
    article: Article,
    categories_by_name: dict[str, Category],
    review: ReviewDoc,
) -> D10Result:
    """D10: yoast_primary -> deepest_child -> parent_container.

    `categories_by_name` is `now_taxonomy_evidence.sources.load_categories`'s
    output -- gives each of the article's category NAMES a WP term_id and
    parent_name, which is what "deepest child" (has a parent among the
    article's own category set, i.e. is not a bare container) needs.
    """
    # 1. yoast_primary
    if article.primary_category_id is not None:
        res = review.by_term_id.get(article.primary_category_id)
        if res is not None:
            return D10Result(res, "yoast_primary")

    # Map the article's category names to (Category, CategoryResolution) pairs
    # that the review pack actually has an opinion on.
    candidates: list[tuple[Category, CategoryResolution]] = []
    for name in article.categories:
        cat = categories_by_name.get(name)
        if cat is None or cat.term_id is None:
            continue
        res = review.by_term_id.get(cat.term_id)
        if res is not None:
            candidates.append((cat, res))

    if not candidates:
        return D10Result(None, "none")

    # 2. deepest_child: prefer non-container categories.
    non_container = [(cat, res) for cat, res in candidates if not res.container]
    pool = non_container or candidates  # if every candidate is a container, fall through to tier 3 pool
    ambiguous = False
    if len(pool) == 1:
        chosen = pool[0]
    elif non_container and len(non_container) > 1:
        # A category is "deepest" if no OTHER candidate in the pool is its
        # parent (i.e. it is not itself the parent container of a sibling
        # candidate). If several remain after that filter, the rules do not
        # further disambiguate (this is exactly the small residual tiebreak
        # the ticket describes as 23 Jakarta / 130 Bali articles) -- fall
        # back to the rarest (smallest published count) category as the
        # most specific, deterministic choice, and flag it as ambiguous so
        # the coverage report can count it honestly.
        names_in_pool = {cat.name for cat, _ in non_container}
        deepest = [(cat, res) for cat, res in non_container if cat.parent_name not in names_in_pool
                   or cat.parent_name == cat.name]
        deepest = deepest or non_container
        if len(deepest) == 1:
            chosen = deepest[0]
        else:
            ambiguous = True
            chosen = min(deepest, key=lambda cr: (cr[0].published or 10**9, cr[0].name))
    else:
        chosen = pool[0]

    if not chosen[1].container:
        return D10Result(chosen[1], "deepest_child", ambiguous)

    # 3. parent_container: every candidate was a container -- use one anyway
    # (a weak prior, per the pack's own framing), deterministically.
    chosen = min(candidates, key=lambda cr: (cr[0].published or 10**9, cr[0].name))
    return D10Result(chosen[1], "parent_container")


def resolve_all_category_fixed_locations(
    article: Article,
    categories_by_name: dict[str, Category],
    review: ReviewDoc,
) -> list[tuple[str, str, str]]:
    """Every one of the article's OWN categories (not just the single one
    D10 picks) that fixes a location -- returns `(slug, confidence_label,
    category_name)` triples.

    D10 picks exactly ONE category to resolve type/subtype/format, because
    those are single-valued facets and "pick one" is the only sensible
    semantics. `location` is different: it is multi-cardinality
    (`rules.location`), and a real article is routinely filed under more
    than one category at once, each carrying its own independently-decided
    fixed location. If D10's own tiering (yoast_primary -> deepest_child ->
    parent_container) happens to pick a co-filed category that does NOT fix
    a location (most often a parent container, since containers rarely fix
    per-article facts) -- to drive type/subtype/format, a *different*
    co-filed category's fixed location must still not be lost.

    F104 (confirmed live, Jakarta wp_ids 87586/88356/90002/91372/93158,
    "Amber Lombok Beach Resort"): `article.categories == ["Bali Updates"]`,
    which fixes `location=bali`. But `article.primary_category_id` (Yoast's
    own primary-category pick) pointed at term_id 2754, "Explore Indonesia"
    -- a PARENT CONTAINER of "Bali Updates" that is not itself in the
    article's own (already container-filtered) `categories` list, and whose
    own proposal fixes no location at all (`location: null, per_article:
    ["location"]`). D10's yoast_primary tier correctly used "Explore
    Indonesia" for type/subtype/format per its own rule (the pack's answer
    for that category IS the right call there), but the old `classify_article`
    only ever consulted the SINGLE D10-winning category for a fixed
    location, so "Bali Updates" fixing `location=bali` was never even
    considered. A plain title match on "lombok" then became the article's
    *only* location decision -- not applied, not gated, not queued: nothing
    downstream could detect the loss. Collecting every co-filed category's
    fixed location here (not just D10's) closes that gap; `classify_article`
    unions each of these into its multi-valued location candidates
    alongside the D10 winner's own (which this list also naturally
    includes, since it iterates every category the article carries).
    """
    out: list[tuple[str, str, str]] = []
    seen_slugs: set[str] = set()
    for name in article.categories:
        cat = categories_by_name.get(name)
        if cat is None or cat.term_id is None:
            continue
        res = review.by_term_id.get(cat.term_id)
        if res is None:
            continue
        loc = res.proposal.get("location")
        if not loc or loc == "per-article":
            continue
        if loc in seen_slugs:
            continue
        seen_slugs.add(loc)
        out.append((loc, res.confidence, res.name))
    return out
