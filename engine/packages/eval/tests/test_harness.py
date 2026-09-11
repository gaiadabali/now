"""Harness-level tests using controllable fake SUTs (not the trivial
random/most-popular baselines) so evaluate_* functions can be checked
against exact, hand-computed expected values.
"""
from now_eval.datasets.facet_labels import FacetLabel
from now_eval.datasets.related_articles import RelatedArticlesQuery
from now_eval.datasets.search_queries import QueryLabel
from now_eval.datasets.type_labels import TypeLabel
from now_eval.harness import (
    evaluate_facet_tagging,
    evaluate_related_articles,
    evaluate_search,
    evaluate_type_classification,
)


class _PerfectRelatedSUT:
    """Always returns exactly the relevant set (padded with junk), in order."""

    def __init__(self, queries: list[RelatedArticlesQuery]):
        self._answers = {q.seed_article_id: list(q.relevant_article_ids) for q in queries}

    def related(self, article_id, candidate_ids, k):
        answer = self._answers.get(article_id, [])
        rest = [c for c in candidate_ids if c not in answer]
        return (answer + rest)[:k]

    def rank(self, query, candidate_ids, k):
        return candidate_ids[:k]

    def tag_facets(self, article_id):
        return set()

    def classify_type(self, article_id):
        return "eat"


def test_evaluate_related_articles_perfect_sut_scores_1():
    queries = [
        RelatedArticlesQuery("wp:1", 1, "s1", 10, "Cat", ("wp:2", "wp:3", "wp:4", "wp:5", "wp:6", "wp:7")),
    ]
    all_ids = [f"wp:{i}" for i in range(1, 20)]
    sut = _PerfectRelatedSUT(queries)
    result = evaluate_related_articles(sut, queries, all_ids, k=6)
    assert result.value == 1.0
    assert result.metric == "precision@6"
    assert result.n == 1


def test_evaluate_related_articles_empty_queries_is_zero_not_crash():
    result = evaluate_related_articles(_PerfectRelatedSUT([]), [], ["wp:1"], k=6)
    assert result.value == 0.0
    assert result.n == 0


class _FixedRankSUT:
    def __init__(self, order: list[str]):
        self._order = order

    def related(self, article_id, candidate_ids, k):
        return self.rank(article_id, candidate_ids, k)

    def rank(self, query, candidate_ids, k):
        ordered = [aid for aid in self._order if aid in candidate_ids]
        return ordered[:k]

    def tag_facets(self, article_id):
        return set()

    def classify_type(self, article_id):
        return "eat"


def test_evaluate_search_hand_computed():
    import math

    import pytest

    # Single query, relevance {a:2, b:1}. SUT ranks [a, b, c].
    # DCG   = (2^2-1)/log2(2) + (2^1-1)/log2(3) + 0 = 3 + 0.630930 = 3.630930
    # IDCG  = same order is already ideal (a has higher relevance) -> IDCG == DCG -> nDCG = 1.0
    expected_dcg = 3 / math.log2(2) + 1 / math.log2(3)
    assert expected_dcg == pytest.approx(3.6309297535714573)

    queries = [QueryLabel(query="q1", source="focus_keyword", relevant=(("a", 2.0), ("b", 1.0)))]
    sut = _FixedRankSUT(["a", "b", "c"])
    result = evaluate_search(sut, queries, ["a", "b", "c"], k=3)
    assert result.value == pytest.approx(1.0)
    assert result.metric == "ndcg@3"


def test_evaluate_search_inverted_ranking_scores_below_1():
    queries = [QueryLabel(query="q1", source="focus_keyword", relevant=(("a", 2.0), ("b", 1.0)))]
    sut = _FixedRankSUT(["b", "a", "c"])  # inverted vs ideal
    result = evaluate_search(sut, queries, ["a", "b", "c"], k=3)
    assert 0.0 < result.value < 1.0


class _FixedFacetSUT:
    def __init__(self, tags: dict[str, set[str]]):
        self._tags = tags

    def related(self, article_id, candidate_ids, k):
        return candidate_ids[:k]

    def rank(self, query, candidate_ids, k):
        return candidate_ids[:k]

    def tag_facets(self, article_id):
        return self._tags.get(article_id, set())

    def classify_type(self, article_id):
        return "eat"


def test_evaluate_facet_tagging_hand_computed():
    labels = [
        FacetLabel("wp:1", 1, "s1", "Rooftop Bar", ("rooftop-bar",)),
        FacetLabel("wp:2", 2, "s2", "Heritage", ("heritage",)),
    ]
    # wp:1 predicted correctly + 1 extra (fp); wp:2 predicted nothing (fn)
    sut = _FixedFacetSUT({"wp:1": {"rooftop-bar", "extra-tag"}, "wp:2": set()})
    result = evaluate_facet_tagging(sut, labels)
    # tp=1, fp=1, fn=1 -> precision=0.5, recall=0.5
    assert result.value == 0.5
    assert result.extra["recall"] == 0.5


class _FixedTypeSUT:
    def __init__(self, types: dict[str, str]):
        self._types = types

    def related(self, article_id, candidate_ids, k):
        return candidate_ids[:k]

    def rank(self, query, candidate_ids, k):
        return candidate_ids[:k]

    def tag_facets(self, article_id):
        return set()

    def classify_type(self, article_id):
        return self._types[article_id]


def test_evaluate_type_classification_hand_computed():
    labels = [
        TypeLabel("wp:1", 1, "s1", "t1", "eat", "Dining News"),
        TypeLabel("wp:2", 2, "s2", "t2", "stay", "Stay Offers"),
        TypeLabel("wp:3", 3, "s3", "t3", "eat", "Dining News"),
        TypeLabel("wp:4", 4, "s4", "t4", "event", "Events"),
    ]
    sut = _FixedTypeSUT({"wp:1": "eat", "wp:2": "editorial", "wp:3": "eat", "wp:4": "event"})
    result = evaluate_type_classification(sut, labels)
    assert result.value == 0.75  # 3 of 4 correct
