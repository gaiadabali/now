from now_classifier.confidence import (
    AUTO_APPLY_AT_OR_ABOVE,
    CATEGORY_FIXED_CONFIDENCE,
    CUE_ABSTAIN_FALLBACK,
    CUE_CONFIDENT,
    CUE_FIRED,
    band,
)


def test_gate_is_085():
    assert AUTO_APPLY_AT_OR_ABOVE == 0.85


def test_category_high_confidence_clears_gate():
    assert CATEGORY_FIXED_CONFIDENCE["high"] >= AUTO_APPLY_AT_OR_ABOVE


def test_category_medium_and_low_never_auto_apply_alone():
    assert CATEGORY_FIXED_CONFIDENCE["medium"] < AUTO_APPLY_AT_OR_ABOVE
    assert CATEGORY_FIXED_CONFIDENCE["low"] < AUTO_APPLY_AT_OR_ABOVE


def test_cue_confident_clears_gate_but_cue_fired_does_not():
    assert CUE_CONFIDENT >= AUTO_APPLY_AT_OR_ABOVE
    assert CUE_FIRED < AUTO_APPLY_AT_OR_ABOVE


def test_cue_abstain_fallback_never_auto_applies():
    assert CUE_ABSTAIN_FALLBACK < AUTO_APPLY_AT_OR_ABOVE


def test_band_boundaries():
    assert band(0.95) == "high"
    assert band(0.85) == "high"
    assert band(0.84) == "medium"
    assert band(0.6) == "medium"
    assert band(0.59) == "low"
    assert band(0.0) == "low"
