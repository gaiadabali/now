"""Hand-computed cases for nDCG. This is the highest-consequence test
file in the package (see metrics/ndcg.py docstring): if these
assertions are wrong, every future search-ranking comparison is
silently meaningless.
"""
import math

import pytest

from now_eval.metrics.ndcg import dcg_at_k, ndcg_at_k, mean_ndcg_at_k


def test_dcg_hand_computed_wikipedia_example():
    # Classic worked example (relevances 3,2,3,0,1,2), exponential-gain
    # DCG = sum (2^rel - 1) / log2(rank + 1):
    #   rank1: (2^3-1)/log2(2) = 7/1        = 7.0
    #   rank2: (2^2-1)/log2(3) = 3/1.584963 = 1.892789...
    #   rank3: (2^3-1)/log2(4) = 7/2        = 3.5
    #   rank4: (2^0-1)/log2(5) = 0/2.321928 = 0.0
    #   rank5: (2^1-1)/log2(6) = 1/2.584963 = 0.386853...
    #   rank6: (2^2-1)/log2(7) = 3/2.807355 = 1.068629...
    rels = [3, 2, 3, 0, 1, 2]
    expected = (
        7.0
        + 3 / math.log2(3)
        + 7 / math.log2(4)
        + 0 / math.log2(5)
        + 1 / math.log2(6)
        + 3 / math.log2(7)
    )
    assert dcg_at_k(rels, 6) == pytest.approx(expected)
    assert dcg_at_k(rels, 6) == pytest.approx(13.848263629272981)


def _bare_dcg(rels: list[float], k: int) -> float:
    """A second, independent implementation of the DCG formula (not
    imported from now_eval.metrics), used only inside these tests so
    the expected values below are computed by a formula anyone reading
    this file can verify by hand -- not hardcoded floats trusted on
    faith, and not merely re-testing the same code against itself."""
    return sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))


def test_ndcg_hand_computed_wikipedia_example_k6():
    # Wikipedia's worked example: relevances 3,2,3,0,1,2.
    # Ideal order sorts them descending: 3,3,2,2,1,0.
    ranked = ["a", "b", "c", "d", "e", "f"]
    relevance = {"a": 3, "b": 2, "c": 3, "d": 0, "e": 1, "f": 2}
    expected_dcg = _bare_dcg([3, 2, 3, 0, 1, 2], 6)
    expected_idcg = _bare_dcg([3, 3, 2, 2, 1, 0], 6)
    assert expected_dcg == pytest.approx(13.848263629272981)  # sanity-pin the bare formula itself
    assert expected_idcg == pytest.approx(14.595390756454924)
    result = ndcg_at_k(ranked, relevance, 6)
    assert result == pytest.approx(expected_dcg / expected_idcg)
    assert result == pytest.approx(0.9488107485678985)


def test_ndcg_hand_computed_wikipedia_example_k3():
    ranked = ["a", "b", "c", "d", "e", "f"]
    relevance = {"a": 3, "b": 2, "c": 3, "d": 0, "e": 1, "f": 2}
    expected_dcg = _bare_dcg([3, 2, 3, 0, 1, 2], 3)
    expected_idcg = _bare_dcg([3, 3, 2], 3)
    result = ndcg_at_k(ranked, relevance, 3)
    assert result == pytest.approx(expected_dcg / expected_idcg)
    assert result == pytest.approx(0.9594535145926796)


def test_ndcg_perfect_ranking_is_1():
    # Ideal order == system order -> nDCG must be exactly 1.0.
    ranked = ["a", "b", "c"]
    relevance = {"a": 3, "b": 2, "c": 1}
    assert ndcg_at_k(ranked, relevance, 3) == pytest.approx(1.0)


def test_ndcg_worst_ranking_is_less_than_1():
    # Completely inverted order must score strictly below 1.
    ranked = ["c", "b", "a"]
    relevance = {"a": 3, "b": 2, "c": 1}
    assert ndcg_at_k(ranked, relevance, 3) < 1.0


def test_ndcg_binary_relevance_hand_computed():
    # Binary relevance, simplest possible non-trivial case:
    # ranked = [relevant, not, not, relevant] with k=4.
    # DCG   = (2^1-1)/log2(2) + 0 + 0 + (2^1-1)/log2(5)
    #       = 1/1 + 1/2.321928 = 1 + 0.430677 = 1.430677
    # IDCG  = ideal order [relevant, relevant, not, not]
    #       = 1/log2(2) + 1/log2(3) = 1 + 0.630930 = 1.630930
    # nDCG  = 1.430677 / 1.630930 = 0.877204...
    ranked = ["r1", "n1", "n2", "r2"]
    relevance = {"r1": 1, "r2": 1}
    expected_dcg = 1 / math.log2(2) + 1 / math.log2(5)
    expected_idcg = 1 / math.log2(2) + 1 / math.log2(3)
    assert dcg_at_k([1, 0, 0, 1], 4) == pytest.approx(expected_dcg)
    assert ndcg_at_k(ranked, relevance, 4) == pytest.approx(expected_dcg / expected_idcg)


def test_ndcg_no_relevant_docs_returns_zero_not_nan():
    ranked = ["a", "b", "c"]
    relevance: dict[str, float] = {}
    assert ndcg_at_k(ranked, relevance, 3) == 0.0


def test_ndcg_missing_ids_in_relevance_treated_as_zero():
    ranked = ["unknown1", "a", "unknown2"]
    relevance = {"a": 2}
    # DCG = 0/log2(2) + (2^2-1)/log2(3) + 0/log2(4) = 3/1.584963 = 1.892789
    # IDCG = 3/log2(2) = 3
    result = ndcg_at_k(ranked, relevance, 3)
    assert result == pytest.approx((3 / math.log2(3)) / 3.0)


def test_dcg_rejects_nonpositive_k():
    with pytest.raises(ValueError):
        dcg_at_k([1, 2], 0)
    with pytest.raises(ValueError):
        ndcg_at_k(["a"], {"a": 1}, -1)


def test_mean_ndcg_averages_across_queries_including_zero_idcg_queries():
    # Query 1: perfect ranking -> 1.0. Query 2: no relevant docs -> 0.0.
    # Mean must be 0.5, not 1.0 (i.e. the zero-relevance query must not
    # be silently dropped from the average).
    rankings = [["a"], ["x"]]
    relevances = [{"a": 1}, {}]
    assert mean_ndcg_at_k(rankings, relevances, 1) == pytest.approx(0.5)
