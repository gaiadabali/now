from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from now_blender.decay import (
    FALLBACK_DECAY_POLICY,
    DecayEntry,
    DecayPolicy,
    age_days,
    decay_factor,
    freshness_component,
)

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


def test_evergreen_never_decays_no_matter_how_old():
    entry = FALLBACK_DECAY_POLICY.entry_for("guide")
    assert entry.evergreen is True
    old = NOW - timedelta(days=365 * 7)  # a 2019-dated article, per F-something's "48% of archive"
    component = freshness_component("guide", old, FALLBACK_DECAY_POLICY, now=NOW)
    assert component == 1.0


@pytest.mark.parametrize("format_", ["feature", "heritage", "people", "city-guide"])
def test_all_evergreen_formats_never_sink(format_):
    old = NOW - timedelta(days=365 * 10)
    assert freshness_component(format_, old, FALLBACK_DECAY_POLICY, now=NOW) == 1.0


def test_news_decays_fast():
    entry = FALLBACK_DECAY_POLICY.entry_for("news")
    assert entry.half_life_days == 21
    fresh = freshness_component("news", NOW, FALLBACK_DECAY_POLICY, now=NOW)
    at_half_life = freshness_component("news", NOW - timedelta(days=21), FALLBACK_DECAY_POLICY, now=NOW)
    old = freshness_component("news", NOW - timedelta(days=365), FALLBACK_DECAY_POLICY, now=NOW)
    assert fresh == 1.0
    assert at_half_life == pytest.approx(0.5, abs=1e-9)
    assert old < 0.01


def test_news_decays_faster_than_review():
    old = NOW - timedelta(days=180)
    news_score = freshness_component("news", old, FALLBACK_DECAY_POLICY, now=NOW)
    review_score = freshness_component("review", old, FALLBACK_DECAY_POLICY, now=NOW)
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
    assert freshness_component("offer", old, FALLBACK_DECAY_POLICY, now=NOW) == 1.0


def test_none_format_is_not_classified_yet_not_a_default_score():
    # F50: this is the honest, real state of every public.articles row today.
    assert freshness_component(None, NOW, FALLBACK_DECAY_POLICY, now=NOW) is None


def test_unknown_format_falls_back_to_default_entry():
    component = freshness_component("some-future-format", NOW - timedelta(days=365), FALLBACK_DECAY_POLICY, now=NOW)
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
