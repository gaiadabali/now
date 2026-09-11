from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from now_blender.decay import (
    DEFAULT_MIN_FORMAT_CONFIDENCE,
    FALLBACK_DECAY_POLICY,
    DecayEntry,
    DecayPolicy,
    age_days,
    decay_factor,
    describe_format_trust,
    freshness_component,
    is_format_trusted,
)

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)

# A trivially-trusted (confidence, source) pair -- used on every pre-existing
# test below that is about the DECAY CURVE, not the F124/F125 trust gate
# itself (that gate has its own dedicated tests further down). Keeps those
# tests exercising exactly what they always tested.
TRUSTED = {"format_confidence": 1.0, "format_source": "editor"}


def test_evergreen_never_decays_no_matter_how_old():
    entry = FALLBACK_DECAY_POLICY.entry_for("guide")
    assert entry.evergreen is True
    old = NOW - timedelta(days=365 * 7)  # a 2019-dated article, per F-something's "48% of archive"
    component = freshness_component("guide", old, FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED)
    assert component == 1.0


@pytest.mark.parametrize("format_", ["feature", "heritage", "people", "city-guide"])
def test_all_evergreen_formats_never_sink(format_):
    old = NOW - timedelta(days=365 * 10)
    assert freshness_component(format_, old, FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED) == 1.0


def test_news_decays_fast():
    entry = FALLBACK_DECAY_POLICY.entry_for("news")
    assert entry.half_life_days == 21
    fresh = freshness_component("news", NOW, FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED)
    at_half_life = freshness_component("news", NOW - timedelta(days=21), FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED)
    old = freshness_component("news", NOW - timedelta(days=365), FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED)
    assert fresh == 1.0
    assert at_half_life == pytest.approx(0.5, abs=1e-9)
    assert old < 0.01


def test_news_decays_faster_than_review():
    old = NOW - timedelta(days=180)
    news_score = freshness_component("news", old, FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED)
    review_score = freshness_component("review", old, FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED)
    assert news_score < review_score


def test_offer_has_no_decay_component_pre_expiry():
    # Hard expiry is a filters.py concern (event/offer expiry hard filter,
    # ARCHITECTURE.md Sec.8.A) -- decay.py never penalizes what has
    # already survived that gate or has no gate at all.
    entry = FALLBACK_DECAY_POLICY.entry_for("offer")
    assert entry.half_life_days is None
    assert entry.evergreen is False
    assert entry.hard_expiry == "campaign.ends_at"
    old = NOW - timedelta(days=1000)
    assert freshness_component("offer", old, FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED) == 1.0


def test_none_format_is_not_classified_yet_not_a_default_score():
    # F50: this is the honest, real state of every public.articles row today.
    # confidence/source are irrelevant when format_ itself is None -- passed
    # here only because the parameters are required, not optional (see the
    # trust-gate tests below for why: no silent "caller forgot" escape hatch).
    assert freshness_component(None, NOW, FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED) is None
    assert freshness_component(None, NOW, FALLBACK_DECAY_POLICY, now=NOW, format_confidence=None, format_source=None) is None


def test_unknown_format_falls_back_to_default_entry():
    component = freshness_component(
        "some-future-format", NOW - timedelta(days=365), FALLBACK_DECAY_POLICY, now=NOW, **TRUSTED
    )
    assert component == pytest.approx(0.5, abs=1e-9)  # default half_life_days=365


def test_missing_published_at_is_none_not_zero():
    entry = DecayEntry(half_life_days=21, evergreen=False)
    assert decay_factor(entry, None) is None


def test_age_days_handles_naive_and_aware_datetimes():
    naive = NOW.replace(tzinfo=None) - timedelta(days=10)
    aware = NOW - timedelta(days=10)
    assert age_days(naive, now=NOW) == pytest.approx(age_days(aware, now=NOW))


def test_from_dict_matches_the_seeded_json_shape():
    # Exactly the shape read back from now_platform.engine.sites.ranking_weights['decay']
    # (verified directly against the running platform DB).
    raw = {
        "version": 1,
        "unit": "days",
        "min_format_confidence": 0.85,
        "default": {"half_life_days": 365, "evergreen": False},
        "formats": {
            "news": {"evergreen": False, "half_life_days": 21, "spec_range": "14-30 days"},
            "guide": {"evergreen": True, "half_life_days": None},
        },
    }
    policy = DecayPolicy.from_dict(raw, source="test")
    assert policy.entry_for("news").half_life_days == 21
    assert policy.entry_for("guide").evergreen is True
    assert policy.entry_for("unlisted-format").half_life_days == 365  # falls back to `default`
    assert policy.min_format_confidence == 0.85


def test_from_dict_defaults_min_format_confidence_when_absent():
    # An older-than-this-ticket site row, or a test fixture that doesn't set
    # it -- the gate degrades to the documented default, never to "no gate".
    raw = {"default": {"half_life_days": 365, "evergreen": False}, "formats": {}}
    policy = DecayPolicy.from_dict(raw, source="test")
    assert policy.min_format_confidence == DEFAULT_MIN_FORMAT_CONFIDENCE


# --------------------------------------------------------------------------
# F124/F125 (PROGRESS.md T2) -- the decay TRUST gate itself.
# --------------------------------------------------------------------------


def test_trusted_high_confidence_value_lets_freshness_apply():
    # Above the site's min_format_confidence and source is the ordinary
    # classifier source ('ai') -- trusted on confidence alone.
    component = freshness_component(
        "news", NOW - timedelta(days=21), FALLBACK_DECAY_POLICY, now=NOW,
        format_confidence=0.90, format_source="ai",
    )
    assert component == pytest.approx(0.5, abs=1e-9)
    assert describe_format_trust("news", 0.90, "ai", FALLBACK_DECAY_POLICY) is None


def test_untrusted_value_uses_the_neutral_default_curve_not_its_own(): 
    # F124's measured numbers put format's routed bands at 0.40-0.72, all
    # below the 0.85 gate. F133 changed what happens next: rather than
    # dropping freshness entirely (which withheld it from 100% of classified
    # articles and left the engine with no recency signal at all), the
    # untrusted value falls back to the NEUTRAL default curve.
    #
    # The distinction being asserted: `published_at` is not in doubt, only
    # WHICH half-life applies. So the score must be the 365d default curve's
    # value, NOT the 21d "news" curve it claims, and NOT None.
    component = freshness_component(
        "news", NOW - timedelta(days=21), FALLBACK_DECAY_POLICY, now=NOW,
        format_confidence=0.56, format_source="inferred",
    )
    assert component is not None, "F133: an untrusted format must still decay, on the default curve"
    expected_default = decay_factor(FALLBACK_DECAY_POLICY.default, 21.0)
    assert component == pytest.approx(expected_default)
    # ...and emphatically not the curve it was labelled with: at 21 days the
    # `news` curve (21d half-life) reads 0.5, the default (365d) ~0.96.
    news_curve = decay_factor(FALLBACK_DECAY_POLICY.formats["news"], 21.0)
    assert component != pytest.approx(news_curve)
    reason = describe_format_trust("news", 0.56, "inferred", FALLBACK_DECAY_POLICY)
    assert reason is not None
    assert "0.56" in reason and "0.85" in reason and "inferred" in reason


def test_source_editor_is_always_trusted_regardless_of_confidence():
    # A human decision (now_classifier.db's own no-clobber convention) is
    # trusted even at a confidence that would otherwise fail the gate.
    component = freshness_component(
        "news", NOW - timedelta(days=21), FALLBACK_DECAY_POLICY, now=NOW,
        format_confidence=0.10, format_source="editor",
    )
    assert component == pytest.approx(0.5, abs=1e-9)
    assert describe_format_trust("news", 0.10, "editor", FALLBACK_DECAY_POLICY) is None
    assert is_format_trusted(0.10, "editor", FALLBACK_DECAY_POLICY) is True


def test_unknown_confidence_and_source_fails_closed():
    # No entity_terms row matched at all (e.g. format_term_ids resolved to
    # nothing, or a legacy value with no recorded provenance) -- this must
    # NOT default to "trust it", since an unverifiable value is exactly the
    # case this ticket exists to stop trusting.
    # "Fails closed" still means "do not trust the claimed format" -- since
    # F133 that is expressed as the neutral default curve rather than no
    # freshness, but it must still NOT be the `news` curve.
    component = freshness_component(
        "news", NOW - timedelta(days=21), FALLBACK_DECAY_POLICY, now=NOW,
        format_confidence=None, format_source=None,
    )
    assert component == pytest.approx(decay_factor(FALLBACK_DECAY_POLICY.default, 21.0))
    assert component != pytest.approx(decay_factor(FALLBACK_DECAY_POLICY.formats["news"], 21.0))
    reason = describe_format_trust("news", None, None, FALLBACK_DECAY_POLICY)
    assert reason is not None
    assert "unknown" in reason


def test_confidence_exactly_at_threshold_is_trusted():
    assert is_format_trusted(0.85, "ai", FALLBACK_DECAY_POLICY) is True
    assert is_format_trusted(0.849999, "ai", FALLBACK_DECAY_POLICY) is False


def test_describe_format_trust_is_none_when_format_itself_is_none():
    # The ordinary "not classified" case already has its own static
    # explanation in blend.py -- the trust gate has nothing extra to say.
    assert describe_format_trust(None, None, None, FALLBACK_DECAY_POLICY) is None


def test_null_format_behaviour_is_unchanged_by_the_trust_gate():
    # F50/acceptance criterion: format IS NULL must behave exactly as
    # before this ticket, regardless of what confidence/source say.
    for confidence, source in [(None, None), (0.99, "editor"), (0.10, "ai")]:
        assert freshness_component(
            None, NOW, FALLBACK_DECAY_POLICY, now=NOW, format_confidence=confidence, format_source=source
        ) is None
