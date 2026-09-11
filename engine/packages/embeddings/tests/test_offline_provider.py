import math

from now_embeddings.providers.offline import OfflineProvider


def test_deterministic_across_calls():
    p = OfflineProvider()
    v1 = p.embed_batch(["A rooftop bar in Senopati"])[0]
    v2 = p.embed_batch(["A rooftop bar in Senopati"])[0]
    assert v1 == v2


def test_different_input_different_vector():
    p = OfflineProvider()
    v1 = p.embed_batch(["hotel"])[0]
    v2 = p.embed_batch(["restaurant"])[0]
    assert v1 != v2


def test_declared_dimension_matches_output():
    p = OfflineProvider()
    vecs = p.embed_batch(["one", "two", "three"])
    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == p.dim == 384


def test_unit_norm():
    p = OfflineProvider()
    v = p.embed_batch(["some text"])[0]
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-9


def test_empty_batch():
    p = OfflineProvider()
    assert p.embed_batch([]) == []


def test_model_name_is_unmistakably_fake():
    assert "offline" in OfflineProvider.name
