"""E5.2 -- the CP-SAT itinerary solver (ARCHITECTURE.md §12).

**Why a constraint solver and not an LLM.** §1 principle 4: "Deterministic
engine decides, LLM narrates." An itinerary is a VRP with time windows,
and its constraints are the kind a language model cannot be made to
respect reliably -- a venue's closing time, a travel budget, a price
ceiling. The value of CP-SAT here is not that it finds a *better*
itinerary; it is that "no closed venues, travel budget respected,
category diversity, price ceiling" becomes **programmatically checkable**
(`now_itinerary.validate`), which is why §12 can gate at 100%.

**What the model decides:** which stop fills each (day, slot), and when
the visitor arrives. It does not decide the *order* within a day -- the
slot ladder already fixes that (breakfast precedes lunch precedes
dinner), so there is no travelling-salesman freedom left to optimise.
What remains is a scheduling problem: arrival times that respect opening
hours, dwell, and travel from the previous stop.

**Eligibility is structural, not penalised.** A stop that cannot legally
fill a slot -- wrong type, closed at that hour, violates a party
constraint, over the per-stop price ceiling -- simply has no variable
created for that (day, slot). Hard constraints that cannot be violated
because the variable does not exist are cheaper to solve and impossible
to accidentally weaken later, which is the same reasoning §8.G applies
to pushing selective filters into SQL.

**Model size is bounded by `MAX_CANDIDATES_PER_SLOT`.** Travel
feasibility needs a constraint per (stop, stop) pair across consecutive
slots, which is quadratic; without a cap, a few hundred candidates per
slot would put millions of implications in the model. Taking the
best-scoring N per slot is the same "re-rank the top ~40" move §7 makes
for rails, and for the same reason.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from now_itinerary.models import (
    Day,
    Itinerary,
    ItineraryRequest,
    Mobility,
    OpeningHours,
    PlannedStop,
    Slot,
    SlotSpec,
    Stop,
)
from now_itinerary.slots import DEFAULT_SLOT_SPECS
from now_itinerary.travel import HaversineMatrix, TravelMatrix

MAX_CANDIDATES_PER_SLOT = 40
DEFAULT_MAX_SOLVE_SECONDS = 10.0

# Objective weight. Score is scaled to integers (CP-SAT is integral).
SCORE_SCALE = 1000

# **Repeated solves of one request can return different itineraries, and
# that is accepted deliberately.** Measured: 5 solves of one 1,000-stop
# request returned 2 distinct trips -- both optimal, tied on objective.
#
# Two fixes were tried and both cost more than the problem:
#
# ① A rank tie-break in the objective's low-order digits. Requires
#    multiplying every real weight by enough headroom (~1e6) to outrank
#    the tie-break sum, which pushed coefficients to ~1e9 and walked
#    straight off CP-SAT's large-coefficient performance cliff -- a
#    400-stop solve went from ~1s to hitting the 10s limit without
#    proving optimality.
# ② `num_search_workers = 1` + fixed seed. Removes the inter-worker
#    timing race, but measured 150 stops / 3 days at **10.2s FEASIBLE**
#    against **413ms OPTIMAL** on 8 workers -- 25x slower, and no longer
#    even optimal. And a solve that hits its time limit is nondeterministic
#    for timing reasons anyway, so this buys determinism only while it
#    happens to finish early.
#
# What makes a shared itinerary stable is **persistence, not
# reproducibility**: E5.4 writes the solved trip to `engine.itineraries`
# and shares it by token, so a link shows the stored day out, never a
# re-solve. The property worth testing is therefore that repeated solves
# are all valid and equally good -- not that they are identical. The seed
# is still pinned because it costs nothing and narrows the variance.
SOLVER_WORKERS = 8
SOLVER_RANDOM_SEED = 20260914


class InfeasibleItineraryError(Exception):
    """No assignment satisfies the hard constraints.

    Carries `reason` rather than only CP-SAT's status string, because
    "INFEASIBLE" tells a caller nothing actionable -- and the common
    causes (a required slot with no eligible stop, a budget below the
    cheapest possible trip) are all diagnosable before the solver runs.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class _Eligibility:
    """One stop's feasible arrival window for one (day, slot)."""

    stop: Stop
    earliest_arrival: int
    latest_arrival: int


def _best_interval_for_window(
    intervals: tuple[OpeningHours, ...], window_start: int, window_end: int
) -> OpeningHours | None:
    """The opening interval overlapping a slot window the most.

    Venues with split service (lunch then dinner) have two intervals, but
    a slot window is narrow enough that only one of them realistically
    overlaps it -- a 12:00-14:30 lunch window does not reach an 18:00
    dinner service. Picking the best-overlapping interval rather than
    modelling a choice between them keeps the model linear; the case it
    gives up on (a single slot window straddling both halves of a split
    service) cannot occur with the default ladder.
    """
    best: OpeningHours | None = None
    best_overlap = 0
    for interval in intervals:
        overlap = min(window_end, interval.closes) - max(window_start, interval.opens)
        if overlap > best_overlap:
            best, best_overlap = interval, overlap
    return best


def _party_allows(stop: Stop, request: ItineraryRequest) -> bool:
    """§8.B's party constraints.

    Unknown is not the same as yes. `wheelchair_accessible=None` means
    nobody recorded it, and promising step-free access on missing data is
    exactly the kind of error that ends a day out -- so an accessibility
    requirement excludes unknowns. `halal`/`vegetarian` are treated the
    same way, and for the same reason.
    """
    party = request.party
    if party.has_children and not stop.kid_friendly:
        return False
    if party.mobility is Mobility.WHEELCHAIR and stop.wheelchair_accessible is not True:
        return False
    if party.halal_only and stop.halal is not True:
        return False
    if party.vegetarian_only and stop.vegetarian is not True:
        return False
    return True


def _eligible_stops(
    request: ItineraryRequest, spec: SlotSpec, day_index: int
) -> list[_Eligibility]:
    """Stops that may legally fill this (day, slot), best-scoring first."""
    weekday = request.weekday_for_day(day_index)
    out: list[_Eligibility] = []

    for stop in request.stops:
        if stop.type not in spec.eligible_types:
            continue
        if not _party_allows(stop, request):
            continue
        if request.max_price_band is not None and (stop.price_band or 0) > request.max_price_band:
            continue

        # Latest possible arrival that still leaves room to finish inside
        # the slot window.
        latest = spec.window_end - stop.dwell_minutes
        earliest = spec.window_start
        if latest < earliest:
            continue  # dwell does not fit the slot at all

        intervals = stop.hours_on(weekday)
        if intervals:
            interval = _best_interval_for_window(intervals, spec.window_start, spec.window_end)
            if interval is None:
                continue  # closed during this slot
            earliest = max(earliest, interval.opens)
            latest = min(latest, interval.closes - stop.dwell_minutes)
            if latest < earliest:
                continue
        elif stop.has_hours_data():
            continue  # hours are known, and say closed this weekday

        out.append(_Eligibility(stop=stop, earliest_arrival=earliest, latest_arrival=latest))

    out.sort(key=lambda e: e.stop.score, reverse=True)
    return out[:MAX_CANDIDATES_PER_SLOT]


def _precheck(
    request: ItineraryRequest,
    specs: tuple[SlotSpec, ...],
    eligibility: dict[tuple[int, Slot], list[_Eligibility]],
) -> None:
    """Catch the over-constrained cases CP-SAT can only call `INFEASIBLE`.

    A bare "INFEASIBLE" is useless to a caller: it does not say whether
    the trip is too long, the budget too tight, or the diversity cap
    simply incompatible with the slot ladder. These two checks cover the
    conflicts that are arithmetic rather than combinatorial, so they can
    be named exactly.

    The first one is not hypothetical. The default ladder marks *both*
    lunch and dinner `required`, and both accept only `eat` -- so
    `max_per_type_per_day=1` is unsatisfiable by construction, for every
    possible candidate pool. Discovering that by exhausting a search tree
    and reporting a generic failure would be a bad answer to a question
    with an obvious one.
    """
    required_by_type: dict[str, int] = defaultdict(int)
    for spec in specs:
        if not spec.required:
            continue
        # Only a single-type slot creates unavoidable demand; a slot that
        # accepts three types can satisfy itself in three ways.
        if len(spec.eligible_types) == 1:
            required_by_type[next(iter(spec.eligible_types))] += 1

    for type_name, needed_per_day in required_by_type.items():
        if needed_per_day > request.max_per_type_per_day:
            raise InfeasibleItineraryError(
                f"the slot ladder requires {needed_per_day} {type_name!r} stops per day "
                f"(the required slots accepting only {type_name!r}), but "
                f"max_per_type_per_day is {request.max_per_type_per_day}. No candidate pool "
                f"can satisfy both -- raise the cap to at least {needed_per_day}, or make one "
                f"of those slots optional."
            )

    # Supply check: required slots need DISTINCT stops (no stop repeats in
    # a trip), and the org cap shrinks how many of a chain's venues count.
    for type_name, needed_per_day in required_by_type.items():
        demand = needed_per_day * request.days
        eligible: dict[int, Stop] = {}
        for (_day, slot), options in eligibility.items():
            spec = next((s for s in specs if s.slot is slot), None)
            if spec is None or not spec.required or spec.eligible_types != {type_name}:
                continue
            for option in options:
                eligible[option.stop.place_id] = option.stop

        by_org: dict[int, int] = defaultdict(int)
        unaffiliated = 0
        for stop in eligible.values():
            if stop.org_id is None:
                unaffiliated += 1
            else:
                by_org[stop.org_id] += 1
        supply = unaffiliated + sum(min(request.max_per_org, n) for n in by_org.values())

        if supply < demand:
            raise InfeasibleItineraryError(
                f"{demand} distinct {type_name!r} stops are needed to fill the required slots "
                f"across {request.days} day(s), but only {supply} are usable "
                f"({len(eligible)} eligible, reduced by max_per_org={request.max_per_org}). "
                f"Widen the candidate pool, shorten the trip, or raise max_per_org."
            )


def solve(
    request: ItineraryRequest,
    *,
    travel: TravelMatrix | None = None,
    max_solve_seconds: float = DEFAULT_MAX_SOLVE_SECONDS,
) -> Itinerary:
    """Builds and solves the assignment+scheduling model.

    Raises `InfeasibleItineraryError` when no itinerary satisfies the
    hard constraints -- never returns a partially-valid one. §12's gate
    is 100% constraint satisfaction, so "here is an itinerary that breaks
    one rule" is not a useful answer; a caller that wants a smaller trip
    should relax a constraint and ask again.
    """
    travel = travel or HaversineMatrix()
    specs = request.slot_specs or DEFAULT_SLOT_SPECS
    if request.days < 1:
        raise InfeasibleItineraryError("days must be at least 1")

    model = cp_model.CpModel()
    started = time.perf_counter()

    # x[(day, slot, place_id)] -- stop fills this slot on this day.
    x: dict[tuple[int, Slot, int], cp_model.IntVar] = {}
    # arrive[(day, slot)] -- arrival time, meaningful only when the slot is used.
    arrive: dict[tuple[int, Slot], cp_model.IntVar] = {}
    used: dict[tuple[int, Slot], cp_model.IntVar] = {}
    eligibility: dict[tuple[int, Slot], list[_Eligibility]] = {}
    stops_by_id: dict[int, Stop] = {s.place_id: s for s in request.stops}

    for day_index in range(request.days):
        for spec in specs:
            key = (day_index, spec.slot)
            options = _eligible_stops(request, spec, day_index)
            eligibility[key] = options

            if spec.required and not options:
                raise InfeasibleItineraryError(
                    f"day {day_index} {spec.slot.value}: required slot has no eligible stop "
                    f"(no candidate is type {sorted(spec.eligible_types)}, open in "
                    f"{spec.window_start}-{spec.window_end}, and allowed by the party constraints)"
                )

            slot_used = model.NewBoolVar(f"used_d{day_index}_{spec.slot.value}")
            used[key] = slot_used
            arrival = model.NewIntVar(
                spec.window_start, spec.window_end, f"arrive_d{day_index}_{spec.slot.value}"
            )
            arrive[key] = arrival

            for option in options:
                var = model.NewBoolVar(f"x_d{day_index}_{spec.slot.value}_p{option.stop.place_id}")
                x[(day_index, spec.slot, option.stop.place_id)] = var
                # Arrival must sit inside this stop's own feasible window.
                model.Add(arrival >= option.earliest_arrival).OnlyEnforceIf(var)
                model.Add(arrival <= option.latest_arrival).OnlyEnforceIf(var)

            slot_vars = [x[(day_index, spec.slot, o.stop.place_id)] for o in options]
            # A slot holds at most one stop, and is "used" exactly when it holds one.
            model.Add(sum(slot_vars) == slot_used)
            if spec.required:
                model.Add(slot_used == 1)

    if not x:
        raise InfeasibleItineraryError("no stop is eligible for any slot on any day")

    _precheck(request, specs, eligibility)

    # No stop appears twice in the whole trip. Seeing the same restaurant
    # on day 1 and day 3 is the single most obvious way an itinerary
    # looks machine-generated.
    for place_id in stops_by_id:
        appearances = [v for (_, _, pid), v in x.items() if pid == place_id]
        if len(appearances) > 1:
            model.Add(sum(appearances) <= 1)

    # §8.D diversity, per day.
    for day_index in range(request.days):
        by_type: dict[str, list[cp_model.IntVar]] = defaultdict(list)
        for (d, _slot, pid), var in x.items():
            if d == day_index:
                by_type[stops_by_id[pid].type].append(var)
        for type_vars in by_type.values():
            if len(type_vars) > request.max_per_type_per_day:
                model.Add(sum(type_vars) <= request.max_per_type_per_day)

    # "max 1 per org" across the trip -- marriott.com appears 63x in the archive.
    by_org: dict[int, list[cp_model.IntVar]] = defaultdict(list)
    for (_d, _slot, pid), var in x.items():
        org_id = stops_by_id[pid].org_id
        if org_id is not None:
            by_org[org_id].append(var)
    for org_vars in by_org.values():
        if len(org_vars) > request.max_per_org:
            model.Add(sum(org_vars) <= request.max_per_org)

    if request.budget_ceiling is not None:
        model.Add(
            sum(
                (stops_by_id[pid].price_band or 0) * var
                for (_d, _slot, pid), var in x.items()
            )
            <= request.budget_ceiling
        )

    if request.required_partner_stops > 0:
        partner_vars = [v for (_d, _s, pid), v in x.items() if stops_by_id[pid].is_partner]
        if len(partner_vars) < request.required_partner_stops:
            raise InfeasibleItineraryError(
                f"{request.required_partner_stops} partner stops required but only "
                f"{len(partner_vars)} partner placements are eligible anywhere in the trip"
            )
        model.Add(sum(partner_vars) >= request.required_partner_stops)

    # Travel feasibility between consecutive slots on the same day: you
    # cannot arrive somewhere before you have left the previous stop and
    # driven there. Enforced pairwise, only when both slots are used.
    ordered = sorted(specs, key=lambda s: s.slot.order)
    travel_terms: list[tuple[cp_model.IntVar, int]] = []
    for day_index in range(request.days):
        for earlier, later in zip(ordered, ordered[1:]):
            a_key, b_key = (day_index, earlier.slot), (day_index, later.slot)
            # Times never run backwards within a day, used or not.
            model.Add(arrive[b_key] >= arrive[a_key])
            for a_opt in eligibility[a_key]:
                a_var = x[(day_index, earlier.slot, a_opt.stop.place_id)]
                for b_opt in eligibility[b_key]:
                    if a_opt.stop.place_id == b_opt.stop.place_id:
                        continue
                    b_var = x[(day_index, later.slot, b_opt.stop.place_id)]
                    leg = travel.minutes(a_opt.stop, b_opt.stop)
                    model.Add(
                        arrive[b_key] >= arrive[a_key] + a_opt.stop.dwell_minutes + leg
                    ).OnlyEnforceIf([a_var, b_var])

    # Objective: relevance, less a penalty for a day that sprawls. The
    # penalty is a proxy -- real travel depends on the pair chosen, which
    # is quadratic -- so it uses each stop's distance from its day's other
    # candidates only through the schedule constraints above. What is
    # linear and safe to optimise here is the score itself; travel is kept
    # feasible by constraint, and kept *small* by the day-end pressure of
    # the slot windows.
    objective = [
        (int(stops_by_id[pid].score * SCORE_SCALE), var) for (_d, _s, pid), var in x.items()
    ]
    # Prefer an interest-matching stop, all else equal.
    if request.interest_types:
        for (_d, _s, pid), var in x.items():
            if stops_by_id[pid].type in request.interest_types:
                objective.append((SCORE_SCALE // 2, var))
    model.Maximize(sum(weight * var for weight, var in objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_solve_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = SOLVER_RANDOM_SEED
    status = solver.Solve(model)
    elapsed = time.perf_counter() - started

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise InfeasibleItineraryError(
            f"solver returned {solver.StatusName(status)}: no assignment satisfies every "
            f"hard constraint (required slots, diversity caps, budget, travel feasibility)"
        )

    return _extract(
        request, specs, solver, x, arrive, stops_by_id, travel,
        status_name=solver.StatusName(status), elapsed=elapsed,
    )


def _extract(
    request: ItineraryRequest,
    specs: tuple[SlotSpec, ...],
    solver: cp_model.CpSolver,
    x: dict[tuple[int, Slot, int], cp_model.IntVar],
    arrive: dict[tuple[int, Slot], cp_model.IntVar],
    stops_by_id: dict[int, Stop],
    travel: TravelMatrix,
    *,
    status_name: str,
    elapsed: float,
) -> Itinerary:
    ordered = sorted(specs, key=lambda s: s.slot.order)
    days: list[Day] = []
    unfilled: list[tuple[int, Slot]] = []

    for day_index in range(request.days):
        planned: list[PlannedStop] = []
        previous: Stop | None = None
        for spec in ordered:
            chosen_id = next(
                (
                    pid
                    for (d, slot, pid), var in x.items()
                    if d == day_index and slot is spec.slot and solver.Value(var)
                ),
                None,
            )
            if chosen_id is None:
                unfilled.append((day_index, spec.slot))
                continue
            stop = stops_by_id[chosen_id]
            arrival = solver.Value(arrive[(day_index, spec.slot)])
            leg = travel.minutes(previous, stop) if previous is not None else 0
            planned.append(
                PlannedStop(
                    stop=stop,
                    day_index=day_index,
                    slot=spec.slot,
                    arrive_minute=arrival,
                    depart_minute=arrival + stop.dwell_minutes,
                    travel_minutes_from_previous=leg,
                    sequence_index=len(planned),
                )
            )
            previous = stop
        days.append(
            Day(
                day_index=day_index,
                weekday=request.weekday_for_day(day_index),
                stops=tuple(planned),
            )
        )

    return Itinerary(
        days=tuple(days),
        unfilled_slots=tuple(unfilled),
        solver_status=status_name,
        solve_seconds=elapsed,
    )
