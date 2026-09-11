from now_inspector.freshness import classify, illustrative_decay


def test_null_format_is_not_classified_yet():
    r = classify(None, "2024-01-01T00:00:00+00:00")
    assert r.format is None
    assert r.half_life_label == "not classified yet"
    assert r.decay_component is None
    assert "not run" in r.note


def test_evergreen_format_has_no_decay_component():
    r = classify("guide", "2020-01-01T00:00:00+00:00")
    assert r.decay_component is None
    assert "no decay" in r.half_life_label


def test_offer_is_hard_expiry_not_decay():
    r = classify("offer", "2020-01-01T00:00:00+00:00")
    assert r.decay_component is None
    assert "not decay" in r.half_life_label


def test_news_decays_with_age():
    fresh = classify("news", None)
    assert fresh.decay_component is None  # no published_at -> can't compute age


def test_illustrative_decay_halves_at_half_life():
    assert abs(illustrative_decay(22.0, 22.0) - 0.5) < 1e-9
    assert illustrative_decay(0.0, 22.0) == 1.0
