"""E5.2/E5.3 -- the solver and the gate.

Every test here ends by running `validate()` over the produced itinerary,
because §12's acceptance criterion is not "the solver returned something"
but **100% constraint satisfaction**. `validate` re-derives each rule from
the request rather than reading the solver's variables back (see its
docstring), so a test passing means two independent implementations agree
-- which is the only version of this check worth having.
"""

from __future__ import annotations

import pytest

from now_itinerary.models import (
    ItineraryRequest,
    Mobility,
    OpeningHours,
    Party,
    Slot,
)
from now_itinerary.solver import InfeasibleItineraryError, solve
from now_itinerary.synthetic import make_stop, make_stops
from now_itinerary.travel import HaversineMatrix
from now_itinerary.validate import validate


def _request(**kwargs) -> ItineraryRequest:
    kwargs.setdefault("stops", make_stops(36))
    kwargs.setdefault("days", 2)
    return ItineraryRequest(**kwargs)


def _solve_and_validate(request, travel=None):
    travel = travel or HaversineMatrix()
    itinerary = solve(request, travel=travel)
    report = validate(itinerary, request, travel=travel)
    report.raise_if_invalid()
    return itinerary, report


def test_produces_a_valid_itinerary():
    itinerary, report = _solve_and_validate(_request())
    assert report.ok
    assert len(itinerary.days) == 2
    assert itinerary.all_stops, "solver returned an itinerary with no stops at all"


def test_required_meals_are_always_filled():
    """Lunch and dinner are `required=True`; a day without a meal is a bug
    report, not a preference."""
    itinerary, _ = _solve_and_validate(_request(days=3))
    for day in itinerary.days:
        filled = {p.slot for p in day.stops}
        assert Slot.LUNCH in filled, f"day {day.day_index} has no lunch"
        assert Slot.DINNER in filled, f"day {day.day_index} has no dinner"


def test_breakfast_is_reachable_under_the_default_cap():
    """Regression: the ladder has three `eat` slots, so a per-type cap of 2
    drops breakfast every day -- and drops it *silently*, since breakfast
    is the only optional one of the three. The default must leave room for
    all three meals."""
    itinerary, _ = _solve_and_validate(
        ItineraryRequest(stops=make_stops(60, seed=42), days=2)
    )
    for day in itinerary.days:
        filled = {p.slot for p in day.stops}
        assert Slot.BREAKFAST in filled, f"day {day.day_index} lost breakfast to the diversity cap"


def test_no_stop_repeats_across_the_trip():
    itinerary, _ = _solve_and_validate(_request(days=3))
    ids = [p.stop.place_id for p in itinerary.all_stops]
    assert len(ids) == len(set(ids))


def test_closed_venues_are_never_scheduled():
    """The headline rule. A pool where every `eat` shuts at 14:00 must
    either avoid dinner or be reported infeasible -- never scheduled."""
    morning_only = (OpeningHours(opens=7 * 60, closes=14 * 60),)
    stops = [
        make_stop(i, type="eat", hours=morning_only) for i in range(1, 9)
    ] + [make_stop(i, type="do") for i in range(20, 28)]

    with pytest.raises(InfeasibleItineraryError) as excinfo:
        solve(ItineraryRequest(stops=tuple(stops), days=1))
    assert "dinner" in str(excinfo.value).lower()


def test_a_venue_closed_on_one_weekday_is_avoided_that_day():
    open_except_monday = {wd: (OpeningHours(7 * 60, 23 * 60),) for wd in (1, 2, 3, 4, 5, 6)}
    closed_monday = make_stop(50, type="eat", name="Shut On Monday")
    closed_monday = type(closed_monday)(
        **{**closed_monday.__dict__, "hours_by_weekday": open_except_monday, "score": 99.0}
    )
    pool = (closed_monday, *make_stops(24, seed=7))

    # start_weekday=0 is Monday, so day 0 must not use it despite its
    # overwhelming score.
    itinerary, _ = _solve_and_validate(
        ItineraryRequest(stops=pool, days=2, start_weekday=0)
    )
    day0_ids = {p.stop.place_id for p in itinerary.days[0].stops}
    assert 50 not in day0_ids


def test_dwell_must_fit_inside_the_slot_window():
    """A 4-hour lunch cannot fit a 2.5-hour lunch window."""
    stops = tuple(
        make_stop(i, type="eat", dwell_minutes=240) for i in range(1, 6)
    ) + make_stops(12, seed=3, types=("do", "culture"))
    with pytest.raises(InfeasibleItineraryError):
        solve(ItineraryRequest(stops=stops, days=1))


def test_travel_time_is_respected_between_consecutive_stops():
    """Two stops 40km apart cannot both be visited in adjacent slots
    unless the schedule leaves time for the journey."""
    far_apart = (
        make_stop(1, type="eat", lat=-6.20, lng=106.80),
        make_stop(2, type="eat", lat=-6.55, lng=107.20),  # ~50km away
        *make_stops(18, seed=11),
    )
    travel = HaversineMatrix()
    itinerary, report = _solve_and_validate(
        ItineraryRequest(stops=far_apart, days=1), travel=travel
    )
    for day in itinerary.days:
        previous = None
        for planned in day.stops:
            if previous is not None:
                needed = travel.minutes(previous.stop, planned.stop)
                assert planned.arrive_minute - previous.depart_minute >= needed
            previous = planned


def test_budget_ceiling_is_respected():
    itinerary, _ = _solve_and_validate(_request(days=1, budget_ceiling=6))
    assert itinerary.total_price_band <= 6


def test_per_stop_price_ceiling_excludes_expensive_venues():
    itinerary, _ = _solve_and_validate(_request(days=2, max_price_band=2))
    assert all((p.stop.price_band or 0) <= 2 for p in itinerary.all_stops)


def test_type_diversity_cap_holds_per_day():
    """Cap of 2, not 1: lunch and dinner are both required and both accept
    only `eat`, so every day needs two `eat` stops no matter what the
    candidate pool looks like."""
    itinerary, _ = _solve_and_validate(_request(days=2, max_per_type_per_day=2))
    for day in itinerary.days:
        counts: dict[str, int] = {}
        for planned in day.stops:
            counts[planned.stop.type] = counts.get(planned.stop.type, 0) + 1
        assert max(counts.values()) <= 2


def test_cap_below_the_required_meal_count_is_diagnosed_not_just_infeasible():
    """`max_per_type_per_day=1` is unsatisfiable for ANY pool, because the
    ladder requires two `eat` slots a day. The caller deserves to be told
    that, not handed a bare INFEASIBLE."""
    with pytest.raises(InfeasibleItineraryError) as excinfo:
        solve(_request(days=1, max_per_type_per_day=1))
    message = str(excinfo.value)
    assert "max_per_type_per_day" in message
    assert "'eat'" in message


def test_org_cap_prevents_the_marriott_problem():
    """'max 1 per org matters: marriott.com appears 63x in the archive.'

    The chain outscores everything, so without the cap it would take every
    meal slot. The independent `eat` pool is sized to actually cover the
    trip once the chain is capped -- otherwise this would test infeasibility
    rather than the cap.
    """
    chain = tuple(
        make_stop(200 + i, type="eat", org_id=77, score=99.0) for i in range(6)
    )
    independents = tuple(make_stop(250 + i, type="eat") for i in range(8))
    itinerary, _ = _solve_and_validate(
        ItineraryRequest(
            stops=chain + independents + make_stops(24, seed=5), days=3, max_per_org=1
        )
    )
    chain_count = sum(1 for p in itinerary.all_stops if p.stop.org_id == 77)
    assert chain_count <= 1


def test_insufficient_distinct_stops_is_diagnosed():
    """Required slots need distinct stops. A pool too small for the trip
    length should say so, naming the shortfall."""
    thin = tuple(make_stop(700 + i, type="eat") for i in range(3))
    with pytest.raises(InfeasibleItineraryError) as excinfo:
        solve(ItineraryRequest(stops=thin + make_stops(12, seed=31), days=4))
    assert "distinct" in str(excinfo.value)


def test_partner_stops_are_guaranteed():
    partners = tuple(
        make_stop(300 + i, type="eat", is_partner=True, score=0.01) for i in range(3)
    )
    request = ItineraryRequest(
        stops=partners + make_stops(24, seed=9),
        days=2,
        required_partner_stops=2,
    )
    itinerary, _ = _solve_and_validate(request)
    placed = sum(1 for p in itinerary.all_stops if p.stop.is_partner)
    assert placed >= 2, "guaranteed partner slots were not honoured despite a terrible score"


def test_impossible_partner_requirement_is_reported_not_silently_dropped():
    request = ItineraryRequest(stops=make_stops(24), days=1, required_partner_stops=5)
    with pytest.raises(InfeasibleItineraryError) as excinfo:
        solve(request)
    assert "partner" in str(excinfo.value).lower()


def test_party_with_children_avoids_adults_only_venues():
    adults_only = tuple(
        make_stop(400 + i, type="eat", kid_friendly=False, score=99.0) for i in range(4)
    )
    request = ItineraryRequest(
        stops=adults_only + make_stops(24, seed=13),
        days=2,
        party=Party(adults=2, children=2),
    )
    itinerary, _ = _solve_and_validate(request)
    assert all(p.stop.kid_friendly for p in itinerary.all_stops)


def test_wheelchair_requirement_excludes_unknown_accessibility():
    """Unknown is not yes. Promising step-free access on missing data is
    the error that ends a day out."""
    accessible = tuple(
        make_stop(500 + i, type=t, wheelchair_accessible=True)
        for i, t in enumerate(("eat", "eat", "eat", "do", "culture", "drink"))
    )
    unknown = make_stops(18, seed=17)  # wheelchair_accessible defaults to None
    request = ItineraryRequest(
        stops=accessible + unknown,
        days=1,
        party=Party(mobility=Mobility.WHEELCHAIR),
    )
    itinerary, _ = _solve_and_validate(request)
    assert all(p.stop.wheelchair_accessible is True for p in itinerary.all_stops)


def test_halal_requirement_excludes_unconfirmed():
    halal = tuple(
        make_stop(600 + i, type=t, halal=True)
        for i, t in enumerate(("eat", "eat", "eat", "do", "culture", "drink"))
    )
    request = ItineraryRequest(
        stops=halal + make_stops(18, seed=19),
        days=1,
        party=Party(halal_only=True),
    )
    itinerary, _ = _solve_and_validate(request)
    assert all(p.stop.halal is True for p in itinerary.all_stops)


def test_stops_without_hours_data_are_allowed_but_reported():
    """Most places carry no hours yet; failing closed on all of them would
    empty every itinerary. They must be flagged, not silently blessed."""
    request = ItineraryRequest(stops=make_stops(24, with_hours=False), days=1)
    itinerary, report = _solve_and_validate(request)
    assert report.ok
    assert report.unverified_hours, "unverified hours were not reported"


def test_estimated_travel_is_flagged_on_the_report():
    """A gate should be able to refuse to certify a trip whose travel
    budget was only ever checked against a guess."""
    _, report = _solve_and_validate(_request(days=1))
    assert report.travel_was_estimated is True


def test_repeated_solves_are_equally_good_and_all_valid():
    """Repeated solves may return *different* optimal itineraries.

    That is accepted (see `solver.SOLVER_WORKERS`): the two ways to force
    identical output each cost more than the problem -- an objective
    tie-break pushes coefficients off CP-SAT's performance cliff, and a
    single worker measured 25x slower without reaching optimality. A
    shared itinerary is stable because E5.4 *persists* it, not because a
    re-solve would reproduce it.

    So what is pinned here is the property that actually matters: every
    solve is valid, and they are all equally good.
    """
    request = _request(days=2)
    travel = HaversineMatrix()
    scores = set()
    for _ in range(4):
        itinerary = solve(request, travel=travel)
        validate(itinerary, request, travel=travel).raise_if_invalid()
        scores.add(round(sum(p.stop.score for p in itinerary.all_stops), 6))
    assert len(scores) == 1, f"solves differed in quality, not just in choice: {scores}"


def test_higher_scoring_stops_are_preferred():
    boring = make_stops(24, seed=23)
    star = make_stop(999, type="eat", score=99.0)
    itinerary, _ = _solve_and_validate(
        ItineraryRequest(stops=(star, *boring), days=1)
    )
    assert 999 in {p.stop.place_id for p in itinerary.all_stops}


def test_zero_days_is_rejected():
    with pytest.raises(InfeasibleItineraryError):
        solve(ItineraryRequest(stops=make_stops(12), days=0))


def test_empty_candidate_pool_is_rejected():
    with pytest.raises(InfeasibleItineraryError):
        solve(ItineraryRequest(stops=(), days=1))
