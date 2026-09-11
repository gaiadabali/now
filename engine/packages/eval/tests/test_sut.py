import pytest

from now_eval.sut import TrivialMostPopularSUT, TrivialRandomSUT


def test_random_sut_is_deterministic_given_seed():
    sut1 = TrivialRandomSUT(seed=42)
    sut2 = TrivialRandomSUT(seed=42)
    candidates = [f"a{i}" for i in range(20)]
    assert sut1.related("q", candidates, 6) == sut2.related("q", candidates, 6)
    assert sut1.classify_type("q") == sut2.classify_type("q")


def test_random_sut_different_seeds_differ():
    sut1 = TrivialRandomSUT(seed=1)
    sut2 = TrivialRandomSUT(seed=2)
    candidates = [f"a{i}" for i in range(30)]
    assert sut1.related("q", candidates, 10) != sut2.related("q", candidates, 10)


def test_random_sut_respects_k():
    sut = TrivialRandomSUT(seed=0)
    candidates = [f"a{i}" for i in range(50)]
    assert len(sut.related("q", candidates, 6)) == 6
    assert len(sut.rank("query text", candidates, 10)) == 10


def test_random_sut_never_returns_more_than_available():
    sut = TrivialRandomSUT(seed=0)
    candidates = ["a1", "a2"]
    assert len(sut.related("q", candidates, 6)) == 2


def test_most_popular_sut_requires_fit_before_classify():
    sut = TrivialMostPopularSUT()
    with pytest.raises(RuntimeError):
        sut.classify_type("a1")


def test_most_popular_sut_predicts_the_mode():
    sut = TrivialMostPopularSUT()
    sut.fit_type({"a": "eat", "b": "eat", "c": "stay"})
    assert sut.classify_type("anything") == "eat"


def test_most_popular_sut_rejects_empty_fit():
    sut = TrivialMostPopularSUT()
    with pytest.raises(ValueError):
        sut.fit_type({})


def test_most_popular_sut_related_uses_popularity_order():
    sut = TrivialMostPopularSUT().fit_popularity_order(["c", "a", "b"])
    result = sut.related("seed", ["a", "b", "c", "d"], 3)
    assert result == ["c", "a", "b"]


def test_most_popular_sut_falls_back_for_unranked_candidates():
    sut = TrivialMostPopularSUT().fit_popularity_order(["b"])
    result = sut.related("seed", ["a", "b", "c"], 3)
    assert result[0] == "b"
    assert set(result) == {"a", "b", "c"}
