"""Search labelled query set (§17: nDCG@10 vs labelled query set, seed
from GSC).

**GSC caveat, per the task brief: do not assume access.** Hansel has
not confirmed Google Search Console is verified for the domain. This
module is built so a GSC export "drops in cleanly"
(`load_gsc_queries`), fully implemented and unit-tested against a
synthetic fixture (`tests/fixtures/gsc_export_sample.csv`) shaped like
a real Search Console "Queries x Pages" export -- but it has never run
against real GSC data, because none is available yet. That is stated
here, not implied away.

Until GSC access is confirmed, `build_provisional_query_set` is the
query set the CI gate actually runs against. It is a **weaker proxy**
than real query -> click data, and this is why:

- A focus keyword is what the editor *hoped* the article would rank
  for, not a query a reader actually typed and clicked through on.
- A title is even weaker: nobody types a 12-word headline into a search
  box. It is included only because the task brief explicitly asks for
  "titles and focus keywords" -- treat title-sourced queries as the
  lower-confidence half of this set (`source="title"`, vs
  `source="focus_keyword"`), and prefer focus-keyword queries in any
  read of the aggregate score.
- Relevance grades here are structural (the source article = grade 3,
  same-primary-category peers = grade 1, everything else = 0), not
  behavioural. A real query set built from GSC would grade relevance
  by actual clicks/impressions, which is a fundamentally different
  (and better) signal this proxy cannot approximate.

Once GSC access exists: run `load_gsc_queries`, diff its per-query
relevant-doc sets against `build_provisional_query_set`'s, and replace
this module's CI-gate role with the GSC-derived set. Do not blend them
silently -- report both until the provisional set is retired.
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .sources import Article, load_articles, load_category_priors_by_term_id
from .split import is_eval

SAMPLE_SIZE = 200
TITLE_QUERY_MAX_WORDS = 6  # keeps title-derived "queries" query-shaped, not headline-shaped


@dataclass(frozen=True)
class QueryLabel:
    query: str
    source: str  # "focus_keyword" | "title" | "gsc"
    relevant: tuple[tuple[str, float], ...]  # (article_id, graded_relevance)

    def relevance_map(self) -> dict[str, float]:
        return dict(self.relevant)


def _peer_relevance(article: Article, priors_by_id, by_category: dict[int, list[Article]]) -> dict[str, float]:
    relevance = {article.article_id: 3.0}
    cat_id = article.primary_category_id
    if cat_id is not None:
        prior = priors_by_id.get(cat_id)
        if prior is not None and not prior.is_print_issue:
            for peer in by_category.get(cat_id, ()):
                if peer.wp_id != article.wp_id:
                    relevance.setdefault(peer.article_id, 1.0)
    return relevance


def build_provisional_query_set(
    articles_path: Path | None = None,
    taxonomy_path: Path | None = None,
    *,
    sample_size: int = SAMPLE_SIZE,
    seed: str = "now-eval-search-v1",
) -> list[QueryLabel]:
    articles = load_articles(articles_path)
    priors_by_id = load_category_priors_by_term_id(taxonomy_path)

    by_category: dict[int, list[Article]] = {}
    for a in articles:
        if a.primary_category_id is not None:
            by_category.setdefault(a.primary_category_id, []).append(a)

    focus_candidates = [a for a in articles if is_eval(a.wp_id) and a.focus_keyword]
    title_candidates = [
        a
        for a in articles
        if is_eval(a.wp_id) and a.title and len(a.title.split()) <= TITLE_QUERY_MAX_WORDS
    ]

    def ranked(candidates: list[Article], salt: str) -> list[Article]:
        return sorted(
            candidates,
            key=lambda a: hashlib.sha256(f"{seed}:{salt}:{a.wp_id}".encode()).hexdigest(),
        )

    half = sample_size // 2
    queries: list[QueryLabel] = []
    seen_wp_ids: set[int] = set()

    for a in ranked(focus_candidates, "focus")[:half]:
        queries.append(
            QueryLabel(
                query=a.focus_keyword,  # type: ignore[arg-type]
                source="focus_keyword",
                relevant=tuple(_peer_relevance(a, priors_by_id, by_category).items()),
            )
        )
        seen_wp_ids.add(a.wp_id)

    remaining = sample_size - len(queries)
    for a in ranked(title_candidates, "title"):
        if len(queries) - half >= remaining:
            break
        if a.wp_id in seen_wp_ids:
            continue
        queries.append(
            QueryLabel(
                query=a.title,
                source="title",
                relevant=tuple(_peer_relevance(a, priors_by_id, by_category).items()),
            )
        )
        seen_wp_ids.add(a.wp_id)

    return queries


# --- GSC import (functional, untested against real GSC data -- see module docstring) ---


def _build_url_to_article_id(permalink_map_path: Path) -> dict[str, str]:
    import json

    mapping: dict[str, str] = {}
    with open(permalink_map_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            path = row["legacy_url"].rstrip("/")
            mapping[path] = f"wp:{row['wp_id']}"
    return mapping


def load_gsc_queries(
    csv_path: Path,
    permalink_map_path: Path,
    *,
    min_clicks: int = 1,
) -> list[QueryLabel]:
    """Parse a Google Search Console "Queries" export (columns: Query,
    Page, Clicks, Impressions, CTR, Position -- the standard GSC UI/API
    export shape) into graded QueryLabels.

    Grading: relevance grade = min(3, 1 + floor(log2(1 + clicks))) for
    any (query, page) pair with clicks >= min_clicks; pairs below that
    are omitted (impressions-only, no evidence of relevance) rather
    than graded 0, since 0 already means "not judged" elsewhere in this
    harness -- omission and explicit-zero must not collide.
    """
    import math

    url_to_id = _build_url_to_article_id(permalink_map_path)
    by_query: dict[str, dict[str, float]] = {}

    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            clicks = int(float(row.get("Clicks", 0) or 0))
            if clicks < min_clicks:
                continue
            query = row["Query"].strip()
            page = row["Page"].strip()
            path = urlparse(page).path.rstrip("/")
            article_id = url_to_id.get(path)
            if article_id is None:
                continue
            grade = min(3.0, 1 + math.floor(math.log2(1 + clicks)))
            by_query.setdefault(query, {})[article_id] = grade

    return [
        QueryLabel(query=q, source="gsc", relevant=tuple(rel.items()))
        for q, rel in sorted(by_query.items())
    ]
