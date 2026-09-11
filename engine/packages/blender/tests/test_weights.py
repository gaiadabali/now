from __future__ import annotations

from now_blender.weights import BlendWeights, DEFAULT_WEIGHTS


def test_default_weights_sum_to_one():
    total = sum(DEFAULT_WEIGHTS.as_dict().values())
    assert abs(total - 1.0) < 1e-9


def test_as_dict_round_trips_through_from_dict():
    weights = BlendWeights(w_sem=0.4, w_cf=0.1, w_fresh=0.1, w_qual=0.2, w_geo=0.1, w_promo=0.1)
    restored = BlendWeights.from_dict(weights.as_dict())
    assert restored == weights


def test_from_dict_ignores_unknown_keys_and_fills_defaults():
    restored = BlendWeights.from_dict({"w_sem": 0.9, "unrelated_key": "ignored"})
    assert restored.w_sem == 0.9
    assert restored.w_qual == DEFAULT_WEIGHTS.w_qual  # untouched fields keep the dataclass default
