import pytest

from now_eval.metrics.precision import (
    precision_at_k,
    recall_at_k,
    average_precision_at_k,
    mean_precision_at_k,
)


def test_precision_at_k_hand_computed():
    # top 6 = [r,r,n,r,n,n] -> 3 relevant of 6
    ranked = ["r1", "r2", "n1", "r3", "n2", "n3"]
    relevant = {"r1", "r2", "r3", "r4"}  # r4 not retrieved at all
    assert precision_at_k(ranked, relevant, 6) == pytest.approx(3 / 6)


def test_precision_at_k_denominator_is_k_not_len_retrieved():
    # Related-articles rail only fills 4 of 6 slots, all correct.
    # Precision must be 4/6, not 4/4 -- an under-filled rail is penalized.
    ranked = ["r1", "r2", "r3", "r4"]
    relevant = {"r1", "r2", "r3", "r4"}
    assert precision_at_k(ranked, relevant, 6) == pytest.approx(4 / 6)


def test_precision_at_k_perfect_and_zero():
    assert precision_at_k(["r1", "r2"], {"r1", "r2"}, 2) == 1.0
    assert precision_at_k(["n1", "n2"], {"r1", "r2"}, 2) == 0.0


def test_precision_at_k_rejects_nonpositive_k():
    with pytest.raises(ValueError):
        precision_at_k(["a"], {"a"}, 0)


def test_recall_at_k_hand_computed():
    ranked = ["r1", "n1", "r2", "n2"]
    relevant = {"r1", "r2", "r3"}  # 2 of 3 relevant docs retrieved in top 4
    assert recall_at_k(ranked, relevant, 4) == pytest.approx(2 / 3)


def test_recall_at_k_no_relevant_docs_returns_zero():
    assert recall_at_k(["a", "b"], set(), 2) == 0.0


def test_average_precision_at_k_hand_computed():
    # ranked = [r, n, r, r] , relevant={a,b,c} (3 total)
    # hits at rank1 (r) -> precision 1/1=1.0
    # rank3 (r)          -> precision 2/3=0.6667
    # rank4 (r)          -> precision 3/4=0.75
    # AP = (1.0 + 0.6667 + 0.75) / min(3,4) = 2.41667/3 = 0.805556
    ranked = ["a", "x", "b", "c"]
    relevant = {"a", "b", "c"}
    expected = (1.0 + 2 / 3 + 3 / 4) / 3
    assert average_precision_at_k(ranked, relevant, 4) == pytest.approx(expected)


def test_average_precision_no_hits_is_zero():
    assert average_precision_at_k(["x", "y"], {"a"}, 2) == 0.0


def test_mean_precision_at_k_averages_across_queries():
    rankings = [["r1", "n1"], ["n2", "n3"]]
    relevants = [{"r1"}, {"r2"}]
    # query1 precision@2 = 1/2, query2 precision@2 = 0/2 -> mean = 0.25
    assert mean_precision_at_k(rankings, relevants, 2) == pytest.approx(0.25)
