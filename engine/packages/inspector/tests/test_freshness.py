from now_blender.decay import FALLBACK_DECAY_POLICY
from now_inspector.freshness import classify, illustrative_decay


def test_null_format_is_not_classified_yet():
    r = classify(None, "2024-01-01T00:00:00+00:00")
    assert r.format is None
    assert r.half_life_label == "not classified yet"
    assert r.decay_component is None
    assert "not run" in r.note


def test_evergreen_format_has_no_decay_component():
    # Must pass TRUSTED provenance: since F133 an untrusted `guide` does not
    # get to claim "evergreen, no decay" -- that claim is precisely what is
    # not trusted, and the real blend applies the neutral default curve to it
    # (see now_blender.decay.freshness_component). Evergreen semantics are
    # only reachable once the format value itself is believed.
    r = classify("guide", "2020-01-01T00:00:00+00:00", format_confidence=0.95, format_source="editor")
    assert r.decay_component is None
    assert "no decay" in r.half_life_label


def test_offer_is_hard_expiry_not_decay():
    # Trusted provenance, same reason as the evergreen case above.
    r = classify("offer", "2020-01-01T00:00:00+00:00", format_confidence=0.95, format_source="editor")
    assert r.decay_component is None
    assert "not decay" in r.half_life_label


def test_news_decays_with_age():
    fresh = classify("news", None)
    assert fresh.decay_component is None  # no published_at -> can't compute age


def test_illustrative_decay_halves_at_half_life():
    assert abs(illustrative_decay(22.0, 22.0) - 0.5) < 1e-9
    assert illustrative_decay(0.0, 22.0) == 1.0


# --------------------------------------------------------------------------
# F124/F125 (T2 decay trust gate) -- reused from now_blender.decay, not
# reimplemented; these tests are about the Inspector's OWN wiring (does it
# surface withheld_reason, does it stop showing a decay_component once
# withheld), not the gate's own logic (see now_blender's test_decay.py).
# --------------------------------------------------------------------------


def test_trusted_value_shows_no_withheld_reason_and_a_real_component():
    r = classify("news", "2026-08-19T00:00:00+00:00", format_confidence=0.95, format_source="editor")
    assert r.withheld_reason is None
    assert r.decay_component is not None


def test_untrusted_value_falls_back_to_the_neutral_default_curve():
    # F133: renamed and re-pointed. This used to assert `decay_component is
    # None` / "WITHHELD", which matched the first implementation -- but that
    # withheld freshness from 100% of classified articles, so the gate now
    # falls back to the neutral default curve. The Inspector must state what
    # the blend ACTUALLY does; showing "withheld" while freshness is really
    # contributing would send a reader hunting a bug that is not there.
    r = classify("news", "2026-08-19T00:00:00+00:00", format_confidence=0.58, format_source="inferred")
    assert r.withheld_reason is not None
    assert "0.58" in r.withheld_reason
    assert "0.85" in r.withheld_reason
    # Freshness IS applied -- on the default curve, never the claimed one.
    assert r.decay_component is not None
    assert "neutral" in r.half_life_label
    assert "not trusted" in r.withheld_reason


def test_editor_source_is_trusted_even_at_low_confidence():
    r = classify("news", "2026-08-19T00:00:00+00:00", format_confidence=0.10, format_source="editor")
    assert r.withheld_reason is None
    assert r.decay_component is not None


def test_null_format_has_no_withheld_reason_default_note_still_applies():
    r = classify(None, "2026-08-19T00:00:00+00:00")
    assert r.withheld_reason is None
    assert "not run" in r.note


def test_default_trust_policy_matches_the_package_fallback():
    # classify()'s default `trust_policy` (used when no platform connection
    # is wired -- see now_inspector.service) is the same 0.85 default the
    # real ranking path falls back to, not a second invented number.
    r_untrusted = classify("news", "2026-08-19T00:00:00+00:00", format_confidence=0.80, format_source="ai")
    r_trusted = classify(
        "news", "2026-08-19T00:00:00+00:00", format_confidence=0.80, format_source="ai",
        trust_policy=FALLBACK_DECAY_POLICY,
    )
    assert r_untrusted.withheld_reason == r_trusted.withheld_reason
    assert r_untrusted.withheld_reason is not None  # 0.80 < 0.85
