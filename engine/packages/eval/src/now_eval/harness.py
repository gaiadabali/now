"""Orchestrates: load labelled sets -> run a SUT against each surface ->
compute the §17 metric -> return one report. This is the thing both
`now-eval run` (local/dev) and the CI workflow (`now-eval check`) call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .datasets.facet_labels import FacetLabel, build_facet_labels
from .datasets.related_articles import RelatedArticlesQuery, build_related_articles_labels
from .datasets.search_queries import QueryLabel, build_provisional_query_set
from .datasets.sources import Article, load_articles
from .datasets.type_labels import TypeLabel, build_type_labels
from .metrics.classification import accuracy, multilabel_precision_recall
from .metrics.ndcg import mean_ndcg_at_k
from .metrics.precision import mean_precision_at_k
from .sut import SystemUnderTest

RELATED_K = 6
SEARCH_K = 10


@dataclass
class SurfaceResult:
    surface: str
    metric: str
    value: float
    n: int
    extra: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "surface": self.surface,
            "metric": self.metric,
            "value": self.value,
            "n": self.n,
            "extra": self.extra,
        }


def evaluate_related_articles(
    sut: SystemUnderTest,
    queries: list[RelatedArticlesQuery],
    all_article_ids: list[str],
    k: int = RELATED_K,
) -> SurfaceResult:
    rankings = []
    relevants = []
    for q in queries:
        candidates = [aid for aid in all_article_ids if aid != q.seed_article_id]
        rankings.append(sut.related(q.seed_article_id, candidates, k))
        relevants.append(q.relevant_article_ids)
    value = mean_precision_at_k(rankings, relevants, k) if queries else 0.0
    return SurfaceResult("related_articles", f"precision@{k}", value, len(queries))


def evaluate_search(
    sut: SystemUnderTest,
    queries: list[QueryLabel],
    all_article_ids: list[str],
    k: int = SEARCH_K,
) -> SurfaceResult:
    rankings = []
    relevances = []
    for q in queries:
        rankings.append(sut.rank(q.query, list(all_article_ids), k))
        relevances.append(q.relevance_map())
    value = mean_ndcg_at_k(rankings, relevances, k) if queries else 0.0
    return SurfaceResult("search", f"ndcg@{k}", value, len(queries))


def evaluate_facet_tagging(sut: SystemUnderTest, labels: list[FacetLabel]) -> SurfaceResult:
    predicted = {label.article_id: sut.tag_facets(label.article_id) for label in labels}
    true = {label.article_id: set(label.facet_labels) for label in labels}
    precision, recall = multilabel_precision_recall(predicted, true)
    return SurfaceResult("facet_tagging", "precision", precision, len(labels), extra={"recall": recall})


def evaluate_type_classification(sut: SystemUnderTest, labels: list[TypeLabel]) -> SurfaceResult:
    predictions = {label.article_id: sut.classify_type(label.article_id) for label in labels}
    truth = {label.article_id: label.type for label in labels}
    value = accuracy(predictions, truth) if labels else 0.0
    return SurfaceResult("type_classification", "accuracy", value, len(labels))


@dataclass
class HarnessReport:
    results: dict[str, SurfaceResult]

    def as_dict(self) -> dict:
        return {name: r.as_dict() for name, r in self.results.items()}


def run_harness(
    sut: SystemUnderTest,
    *,
    articles_path: Path | None = None,
    taxonomy_path: Path | None = None,
) -> HarnessReport:
    all_articles: list[Article] = load_articles(articles_path)
    all_article_ids = [a.article_id for a in all_articles]

    related_queries = build_related_articles_labels(articles_path, taxonomy_path)
    search_queries = build_provisional_query_set(articles_path, taxonomy_path)
    facet_labels = build_facet_labels(articles_path)
    type_labels = build_type_labels(articles_path, taxonomy_path)

    results = {
        "related_articles": evaluate_related_articles(sut, related_queries, all_article_ids),
        "search": evaluate_search(sut, search_queries, all_article_ids),
        "facet_tagging": evaluate_facet_tagging(sut, facet_labels),
        "type_classification": evaluate_type_classification(sut, type_labels),
    }
    return HarnessReport(results)
