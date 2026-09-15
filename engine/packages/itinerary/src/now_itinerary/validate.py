"""E5.3 -- the constraint validator. ARCHITECTURE.md §12's gate.

> "Constraint satisfaction is programmatically checkable -- no closed
> venues, travel budget respected, category diversity, price ceiling.
> **Gate at 100%.**"

This module is deliberately an **independent re-derivation**, not a
read-back of the solver's own variables. Checking that CP-SAT satisfied
the constraints CP-SAT was given proves only that CP-SAT works; it cannot
catch the failure that actually matters here, which is the model
*encoding the wrong constraint*. So `validate` re-reads each rule from
`ItineraryRequest` + the raw `Stop` data and checks the produced schedule
against it from scratch. When the two disagree, the bug is real either
way -- which is the point.

Every violation names the rule, the day, and the stop, because a gate
that reports only a count is a gate nobody can act on.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from now_itinerary.models import Itinerary, ItineraryRequest, Mobility, Slot, SlotSpec
from now_itinerary.slots import DEFAULT_SLOT_SPECS
from now_itinerary.travel import TravelMatrix


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str
    day_index: int | None = None
    place_id: int | None = None

    def __str__(self) -> str:
        where = "" if self.day_index is None else f" [day {self.day_index}]"
        return f"{self.rule}{where}: {self.detail}"


@dataclass(frozen=True)
class ValidationReport:
    violations: tuple[Violation, ...]
    unverified_hours: tuple[int, ...] = ()
    travel_was_estimated: bool = False

    @property
    def ok(self) -> bool:
        return not self.violations

    def raise_if_invalid(self) -> None:
        if self.violations:
            joined = "\n  ".join(str(v) for v in self.violations)
            raise ItineraryConstraintError(
                f"{len(self.violations)} constraint violation(s):\n  {joined}"
            )


class ItineraryConstraintError(Exception):
    """The gate failed. §12 makes this a hard CI failure, not a warning."""


def validate(
    itinerary: Itinerary,
    request: ItineraryRequest,
    *,
    travel: TravelMatrix | None = None,
    slot_specs: tuple[SlotSpec, ...] | None = None,
) -> ValidationReport:
    specs = slot_specs or request.slot_specs or DEFAULT_SLOT_SPECS
    spec_by_slot: dict[Slot, SlotSpec] = {s.slot: s for s in specs}
    violations: list[Violation] = []
    unverified: list[int] = []

    seen_place_ids: set[int] = set()
    org_counts: dict[int, int] = defaultdict(int)
    total_price = 0

    if len(itinerary.days) != request.days:
        violations.append(
            Violation("day_count", f"expected {request.days} days, got {len(itinerary.days)}")
        )

    for day in itinerary.days:
        filled_slots = {p.slot for p in day.stops}
        per_type: dict[str, int] = defaultdict(int)

        for spec in specs:
            if spec.required and spec.slot not in filled_slots:
                violations.append(
                    Violation("required_slot", f"{spec.slot.value} is unfilled", day.day_index)
                )

        previous = None
        for planned in day.stops:
            stop = planned.stop
            spec = spec_by_slot.get(planned.slot)
            per_type[stop.type] += 1
            total_price += stop.price_band or 0
            if stop.org_id is not None:
                org_counts[stop.org_id] += 1

            if stop.place_id in seen_place_ids:
                violations.append(
                    Violation(
                        "duplicate_stop",
                        f"{stop.name!r} appears more than once in the trip",
                        day.day_index,
                        stop.place_id,
                    )
                )
            seen_place_ids.add(stop.place_id)

            if spec is None:
                violations.append(
                    Violation(
                        "unknown_slot",
                        f"{planned.slot.value} is not in this site's slot ladder",
                        day.day_index,
                        stop.place_id,
                    )
                )
                continue

            if stop.type not in spec.eligible_types:
                violations.append(
                    Violation(
                        "slot_type",
                        f"{stop.name!r} is type {stop.type!r}, not eligible for "
                        f"{spec.slot.value} ({sorted(spec.eligible_types)})",
                        day.day_index,
                        stop.place_id,
                    )
                )

            # The headline rule: no closed venues.
            intervals = stop.hours_on(day.weekday)
            if intervals:
                if not any(
                    i.covers(planned.arrive_minute, planned.depart_minute) for i in intervals
                ):
                    violations.append(
                        Violation(
                            "closed_venue",
                            f"{stop.name!r} scheduled {planned.arrive_minute}-"
                            f"{planned.depart_minute} but opening hours on weekday "
                            f"{day.weekday} are "
                            f"{[(i.opens, i.closes) for i in intervals]}",
                            day.day_index,
                            stop.place_id,
                        )
                    )
            elif stop.has_hours_data():
                violations.append(
                    Violation(
                        "closed_venue",
                        f"{stop.name!r} is closed on weekday {day.weekday}",
                        day.day_index,
                        stop.place_id,
                    )
                )
            else:
                # Not a violation -- but not a verified pass either. See
                # Stop.hours_on: most places carry no hours data yet, and
                # failing closed on all of them would empty every
                # itinerary. Reported so a caller can decide.
                unverified.append(stop.place_id)

            if planned.depart_minute != planned.arrive_minute + stop.dwell_minutes:
                violations.append(
                    Violation(
                        "dwell",
                        f"{stop.name!r} departs {planned.depart_minute - planned.arrive_minute}min "
                        f"after arrival, expected {stop.dwell_minutes}",
                        day.day_index,
                        stop.place_id,
                    )
                )

            if not (spec.window_start <= planned.arrive_minute <= spec.window_end):
                violations.append(
                    Violation(
                        "slot_window",
                        f"{stop.name!r} arrives {planned.arrive_minute}, outside "
                        f"{spec.slot.value} window {spec.window_start}-{spec.window_end}",
                        day.day_index,
                        stop.place_id,
                    )
                )

            if request.max_price_band is not None and (stop.price_band or 0) > request.max_price_band:
                violations.append(
                    Violation(
                        "price_band",
                        f"{stop.name!r} is band {stop.price_band}, ceiling is "
                        f"{request.max_price_band}",
                        day.day_index,
                        stop.place_id,
                    )
                )

            _check_party(violations, request, day.day_index, stop)

            # Travel feasibility: could the visitor actually get here?
            if previous is not None and travel is not None:
                needed = travel.minutes(previous.stop, stop)
                available = planned.arrive_minute - previous.depart_minute
                if available < needed:
                    violations.append(
                        Violation(
                            "travel_time",
                            f"{available}min between leaving {previous.stop.name!r} and "
                            f"arriving at {stop.name!r}, but the journey takes {needed}min",
                            day.day_index,
                            stop.place_id,
                        )
                    )
            previous = planned

        for type_name, count in per_type.items():
            if count > request.max_per_type_per_day:
                violations.append(
                    Violation(
                        "type_diversity",
                        f"{count} {type_name!r} stops, cap is {request.max_per_type_per_day}",
                        day.day_index,
                    )
                )

        if request.max_travel_minutes_per_day is not None:
            if day.travel_minutes > request.max_travel_minutes_per_day:
                violations.append(
                    Violation(
                        "travel_budget",
                        f"{day.travel_minutes}min travelling, budget is "
                        f"{request.max_travel_minutes_per_day}min",
                        day.day_index,
                    )
                )

    for org_id, count in org_counts.items():
        if count > request.max_per_org:
            violations.append(
                Violation(
                    "org_cap",
                    f"org {org_id} appears {count} times, cap is {request.max_per_org}",
                )
            )

    if request.budget_ceiling is not None and total_price > request.budget_ceiling:
        violations.append(
            Violation(
                "budget",
                f"total price band {total_price} exceeds ceiling {request.budget_ceiling}",
            )
        )

    if request.required_partner_stops > 0:
        placed = sum(1 for p in itinerary.all_stops if p.stop.is_partner)
        if placed < request.required_partner_stops:
            violations.append(
                Violation(
                    "partner_slots",
                    f"{placed} partner stops placed, {request.required_partner_stops} required",
                )
            )

    return ValidationReport(
        violations=tuple(violations),
        unverified_hours=tuple(sorted(set(unverified))),
        travel_was_estimated=bool(travel is not None and travel.is_estimate),
    )


def _check_party(
    violations: list[Violation], request: ItineraryRequest, day_index: int, stop
) -> None:
    party = request.party
    if party.has_children and not stop.kid_friendly:
        violations.append(
            Violation("party_children", f"{stop.name!r} is not kid-friendly", day_index, stop.place_id)
        )
    if party.mobility is Mobility.WHEELCHAIR and stop.wheelchair_accessible is not True:
        violations.append(
            Violation(
                "party_mobility",
                f"{stop.name!r} is not confirmed wheelchair accessible "
                f"(recorded: {stop.wheelchair_accessible!r})",
                day_index,
                stop.place_id,
            )
        )
    if party.halal_only and stop.halal is not True:
        violations.append(
            Violation("party_halal", f"{stop.name!r} is not confirmed halal", day_index, stop.place_id)
        )
    if party.vegetarian_only and stop.vegetarian is not True:
        violations.append(
            Violation(
                "party_vegetarian",
                f"{stop.name!r} is not confirmed vegetarian-friendly",
                day_index,
                stop.place_id,
            )
        )
