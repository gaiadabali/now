"""Contextual filters (Sec.8.B) -- pure Python, no DB. `SessionState`
inputs are all caller-resolved (see contextual.py docstring), so these
are unit tests of the predicate logic in isolation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from now_filters.contextual import (
    ALREADY_READ_DECAY_DAYS,
    already_read_weight,
    apply_contextual_filters,
    is_hard_excluded_by_session,
    is_open_at,
    satisfies_party_constraints,
    within_trip_window,
)
from now_filters.models import Candidate, SessionState

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)  # a Wednesday


def place(**kw) -> Candidate:
    base = dict(entity_type="place", entity_id=1)
    base.update(kw)
    return Candidate(**base)


def test_already_read_decays_linearly_back_to_full_weight():
    c = place(entity_id=1)
    session = SessionState(already_read={c.key: NOW - timedelta(days=1)}, now=NOW)
    w1 = already_read_weight(c, session)
    session7 = SessionState(already_read={c.key: NOW - timedelta(days=7)}, now=NOW)
    w7 = already_read_weight(c, session7)
    session20 = SessionState(already_read={c.key: NOW - timedelta(days=20)}, now=NOW)
    w20 = already_read_weight(c, session20)
    assert w1 < w7 < w20 == 1.0
    assert w20 == 1.0
    assert 0.0 <= w1 <= 1.0


def test_already_read_never_hard_excludes():
    """Sec.18 open decision #4: decay, not permanent suppression --
    contextual.py's `already_read_weight` must never appear as a hard
    exclusion path; `apply_contextual_filters` must keep such candidates
    in `survivors`, only recording a low weight."""
    c = place(entity_id=1)
    session = SessionState(already_read={c.key: NOW}, now=NOW)  # read this exact instant
    result = apply_contextual_filters([c], session)
    assert c in result.survivors
    assert result.weights[c.key] == 0.0


def test_session_shown_and_itinerary_are_hard_excluded():
    shown = place(entity_id=1)
    in_itin = place(entity_id=2)
    fresh = place(entity_id=3)
    session = SessionState(already_shown_this_session={shown.key}, already_in_itinerary={in_itin.key}, now=NOW)
    assert is_hard_excluded_by_session(shown, session)
    assert is_hard_excluded_by_session(in_itin, session)
    assert not is_hard_excluded_by_session(fresh, session)
    result = apply_contextual_filters([shown, in_itin, fresh], session)
    assert [c.entity_id for c in result.survivors] == [3]


def test_open_at_respects_hours_including_overnight_wraparound():
    c = place(hours=(("wed", "18:00", "02:00"),))
    assert is_open_at(c, datetime(2026, 9, 9, 23, 0, tzinfo=timezone.utc)) is True  # wed 23:00
    assert is_open_at(c, datetime(2026, 9, 10, 1, 0, tzinfo=timezone.utc)) is True  # thu 01:00, still wed's overnight window
    assert is_open_at(c, datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)) is False  # wed 10:00, before opening


def test_open_at_missing_hours_defaults_open():
    c = place(hours=())
    assert is_open_at(c, NOW) is True


def test_trip_window_constrains_events_not_places():
    trip_start = NOW
    trip_end = NOW + timedelta(days=3)
    session = SessionState(trip_start=trip_start, trip_end=trip_end)
    in_window = place(entity_id=1, ends_at=NOW + timedelta(days=1))
    out_of_window = place(entity_id=2, ends_at=NOW + timedelta(days=10))
    a_place_not_an_event = place(entity_id=3, ends_at=None)
    assert within_trip_window(in_window, session) is True
    assert within_trip_window(out_of_window, session) is False
    assert within_trip_window(a_place_not_an_event, session) is True


def test_party_constraints_amenities_and_budget():
    accessible_cheap = place(amenities=frozenset({"wheelchair-accessible"}), price_band="budget")
    inaccessible = place(amenities=frozenset(), price_band="budget")
    expensive = place(amenities=frozenset({"wheelchair-accessible"}), price_band="luxury")

    session = SessionState(party_accessibility=True, party_budget_ceiling="moderate")
    assert satisfies_party_constraints(accessible_cheap, session) is True
    assert satisfies_party_constraints(inaccessible, session) is False
    assert satisfies_party_constraints(expensive, session) is False


def test_decay_window_constant_matches_architecture_default():
    assert ALREADY_READ_DECAY_DAYS == 14.0
