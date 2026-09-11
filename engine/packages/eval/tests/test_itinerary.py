from datetime import date

import pytest

from now_eval.metrics.itinerary import (
    Itinerary,
    OpeningHours,
    PartyConstraints,
    Stop,
    check_batch,
    check_itinerary,
)

DAY1 = date(2026, 10, 1)
DAY2 = date(2026, 10, 2)


def _open_all_day(weekday: int) -> OpeningHours:
    return OpeningHours(windows=((weekday, 0, 1440),))


def test_fully_valid_itinerary_has_zero_violations():
    party = PartyConstraints(
        budget_ceiling=1_000_000,
        max_repeat_per_type_per_day=2,
        trip_start=DAY1,
        trip_end=DAY2,
    )
    stops = (
        Stop(
            "hotel1", DAY1, 480, 540, "stay", price=0,
            hours=_open_all_day(DAY1.weekday()),
        ),
        Stop(
            "cafe1", DAY1, 600, 660, "eat", price=100_000,
            travel_minutes_from_previous=30,
            hours=_open_all_day(DAY1.weekday()),
        ),
        Stop(
            "museum1", DAY1, 720, 840, "do", price=50_000,
            travel_minutes_from_previous=20,
            hours=_open_all_day(DAY1.weekday()),
        ),
    )
    itinerary = Itinerary(stops)
    report = check_itinerary(itinerary, party)
    assert report.is_satisfied
    assert report.violations == ()


def test_closed_venue_is_caught():
    # Venue only open on weekday 0 (Monday); stop is on DAY1 which is a
    # Thursday (weekday 3) -> must violate venue_closed.
    assert DAY1.weekday() != 0
    party = PartyConstraints()
    stop = Stop("restaurant1", DAY1, 600, 660, "eat", hours=_open_all_day(0))
    report = check_itinerary(Itinerary((stop,)), party)
    assert not report.is_satisfied
    assert "venue_closed" in report.violation_types()


def test_closed_specific_date_is_caught():
    hours = OpeningHours(windows=((DAY1.weekday(), 0, 1440),), closed_dates=frozenset({DAY1}))
    stop = Stop("bar1", DAY1, 600, 660, "drink", hours=hours)
    report = check_itinerary(Itinerary((stop,)), PartyConstraints())
    assert "venue_closed" in report.violation_types()


def test_insufficient_travel_time_is_caught():
    # stop2 starts 10 minutes after stop1 ends, but travel takes 30.
    stop1 = Stop("a", DAY1, 600, 660, "eat")
    stop2 = Stop("b", DAY1, 670, 700, "do", travel_minutes_from_previous=30)
    report = check_itinerary(Itinerary((stop1, stop2)), PartyConstraints())
    assert not report.is_satisfied
    assert "travel_time_violated" in report.violation_types()


def test_sufficient_travel_time_passes():
    stop1 = Stop("a", DAY1, 600, 660, "eat")
    stop2 = Stop("b", DAY1, 690, 720, "do", travel_minutes_from_previous=30)
    report = check_itinerary(Itinerary((stop1, stop2)), PartyConstraints())
    assert "travel_time_violated" not in report.violation_types()


def test_budget_ceiling_exceeded_is_caught():
    stops = (
        Stop("a", DAY1, 600, 660, "eat", price=700_000),
        Stop("b", DAY1, 700, 760, "do", price=500_000),
    )
    party = PartyConstraints(budget_ceiling=1_000_000)
    report = check_itinerary(Itinerary(stops), party)
    assert "budget_exceeded" in report.violation_types()


def test_budget_within_ceiling_passes():
    stops = (Stop("a", DAY1, 600, 660, "eat", price=400_000),)
    party = PartyConstraints(budget_ceiling=1_000_000)
    report = check_itinerary(Itinerary(stops), party)
    assert "budget_exceeded" not in report.violation_types()


def test_category_diversity_violation_is_caught():
    stops = tuple(
        Stop(f"eat{i}", DAY1, 600 + i * 90, 650 + i * 90, "eat") for i in range(3)
    )
    party = PartyConstraints(max_repeat_per_type_per_day=2)
    report = check_itinerary(Itinerary(stops), party)
    assert "category_diversity_violated" in report.violation_types()


def test_category_diversity_within_limit_passes():
    stops = tuple(
        Stop(f"eat{i}", DAY1, 600 + i * 90, 650 + i * 90, "eat") for i in range(2)
    )
    party = PartyConstraints(max_repeat_per_type_per_day=2)
    report = check_itinerary(Itinerary(stops), party)
    assert "category_diversity_violated" not in report.violation_types()


def test_outside_trip_window_is_caught():
    stop = Stop("a", date(2026, 11, 1), 600, 660, "eat")
    party = PartyConstraints(trip_start=DAY1, trip_end=DAY2)
    report = check_itinerary(Itinerary((stop,)), party)
    assert "outside_trip_window" in report.violation_types()


def test_kids_constraint_is_caught():
    stop = Stop("bar1", DAY1, 600, 660, "drink", kid_friendly=False)
    party = PartyConstraints(kids=True)
    report = check_itinerary(Itinerary((stop,)), party)
    assert "not_kid_friendly" in report.violation_types()


def test_halal_constraint_only_applies_to_eat():
    # A non-halal bar shouldn't trip the halal check (only 'eat' stops do).
    stop = Stop("bar1", DAY1, 600, 660, "drink", halal=False)
    party = PartyConstraints(halal=True)
    report = check_itinerary(Itinerary((stop,)), party)
    assert "not_halal" not in report.violation_types()


def test_halal_constraint_applies_to_eat():
    stop = Stop("restaurant1", DAY1, 600, 660, "eat", halal=False)
    party = PartyConstraints(halal=True)
    report = check_itinerary(Itinerary((stop,)), party)
    assert "not_halal" in report.violation_types()


def test_vegetarian_constraint_is_caught():
    stop = Stop("restaurant1", DAY1, 600, 660, "eat", vegetarian_friendly=False)
    party = PartyConstraints(vegetarian=True)
    report = check_itinerary(Itinerary((stop,)), party)
    assert "not_vegetarian_friendly" in report.violation_types()


def test_accessibility_constraint_is_caught():
    stop = Stop("museum1", DAY1, 600, 660, "do", wheelchair_accessible=False)
    party = PartyConstraints(accessibility=True)
    report = check_itinerary(Itinerary((stop,)), party)
    assert "not_accessible" in report.violation_types()


def test_stop_rejects_end_before_start():
    with pytest.raises(ValueError):
        Stop("a", DAY1, 700, 600, "eat")


def test_batch_all_satisfied_is_100_percent_gate():
    good = Itinerary((Stop("a", DAY1, 600, 660, "eat"),))
    party = PartyConstraints()
    batch = check_batch([good, good], [party, party])
    assert batch.satisfaction_rate == 1.0
    assert batch.all_satisfied is True


def test_batch_one_violation_fails_the_hard_gate():
    good = Itinerary((Stop("a", DAY1, 600, 660, "eat"),))
    bad = Itinerary(
        (Stop("b", DAY1, 600, 660, "eat", price=2_000_000),)
    )
    party = PartyConstraints(budget_ceiling=1_000_000)
    batch = check_batch([good, bad], [party, party])
    assert batch.satisfaction_rate == 0.5
    # Hard fail: even 50% satisfaction must not be reported as passing.
    assert batch.all_satisfied is False


def test_check_batch_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        check_batch([Itinerary(())], [PartyConstraints(), PartyConstraints()])
