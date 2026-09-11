"""Itinerary constraint-satisfaction checker (ARCHITECTURE.md §12, §8.B).

The OR-Tools CP-SAT solver itself is E5 scope and does not exist yet.
This module is the *spec*, expressed as code: the checkable contract any
solver output must satisfy, plus a battery of tests that prove each rule
actually catches the failure mode it claims to. §17 gates this at
**100%, hard fail** — one violating itinerary in a batch fails the
build, there is no partial-credit threshold.

Design note: constraints here are independent, composable functions
rather than one monolithic check, so E5 can import this module directly
in its own solver's post-generation validation pass instead of
re-implementing constraint logic — "spec + tests" is meant literally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class OpeningHours:
    """Weekly recurring hours plus specific closed dates.

    `windows`: list of (weekday, open_minute, close_minute).
    weekday follows date.weekday() (0=Monday .. 6=Sunday). Minutes are
    minutes-since-midnight in the venue's local time. A venue open past
    midnight should be modelled with close_minute > 1440 (e.g. a bar
    open 18:00-02:00 -> (weekday, 1080, 1560)) — the checker does not
    attempt to split it across two calendar days.
    """

    windows: tuple[tuple[int, int, int], ...] = ()
    closed_dates: frozenset[date] = field(default_factory=frozenset)

    def is_open(self, day: date, start_minute: int, end_minute: int) -> bool:
        if day in self.closed_dates:
            return False
        weekday = day.weekday()
        return any(
            wd == weekday and open_m <= start_minute and end_minute <= close_m
            for wd, open_m, close_m in self.windows
        )


@dataclass(frozen=True)
class Stop:
    place_id: str
    day: date
    start_minute: int
    end_minute: int
    category: str  # L1 type per ARCHITECTURE.md §4 type tree
    price: float = 0.0
    travel_minutes_from_previous: int = 0
    hours: OpeningHours | None = None  # None = hours unknown, not checked
    kid_friendly: bool = True
    halal: bool = True
    vegetarian_friendly: bool = True
    wheelchair_accessible: bool = True

    def __post_init__(self) -> None:
        if self.end_minute <= self.start_minute:
            raise ValueError(
                f"stop {self.place_id}: end_minute ({self.end_minute}) must be "
                f"after start_minute ({self.start_minute})"
            )


@dataclass(frozen=True)
class PartyConstraints:
    kids: bool = False
    halal: bool = False
    vegetarian: bool = False
    accessibility: bool = False
    budget_ceiling: float | None = None
    max_repeat_per_type_per_day: int = 2
    trip_start: date | None = None
    trip_end: date | None = None


@dataclass(frozen=True)
class Itinerary:
    stops: tuple[Stop, ...]


@dataclass(frozen=True)
class ConstraintViolation:
    constraint: str
    place_id: str | None
    detail: str


@dataclass(frozen=True)
class ItineraryReport:
    violations: tuple[ConstraintViolation, ...]

    @property
    def is_satisfied(self) -> bool:
        return len(self.violations) == 0

    def violation_types(self) -> set[str]:
        return {v.constraint for v in self.violations}


def _check_open(itinerary: Itinerary) -> list[ConstraintViolation]:
    violations = []
    for stop in itinerary.stops:
        if stop.hours is None:
            continue
        if not stop.hours.is_open(stop.day, stop.start_minute, stop.end_minute):
            violations.append(
                ConstraintViolation(
                    "venue_closed",
                    stop.place_id,
                    f"{stop.place_id} not open on {stop.day} "
                    f"{stop.start_minute}-{stop.end_minute}",
                )
            )
    return violations


def _check_travel_time(itinerary: Itinerary) -> list[ConstraintViolation]:
    violations = []
    by_day: dict[date, list[Stop]] = {}
    for stop in itinerary.stops:
        by_day.setdefault(stop.day, []).append(stop)
    for day, stops in by_day.items():
        ordered = sorted(stops, key=lambda s: s.start_minute)
        for prev, cur in zip(ordered, ordered[1:]):
            earliest_possible_start = prev.end_minute + cur.travel_minutes_from_previous
            if cur.start_minute < earliest_possible_start:
                violations.append(
                    ConstraintViolation(
                        "travel_time_violated",
                        cur.place_id,
                        f"{cur.place_id} starts at {cur.start_minute} on {day} but "
                        f"{prev.place_id} ends at {prev.end_minute} and travel takes "
                        f"{cur.travel_minutes_from_previous}min "
                        f"(earliest possible start {earliest_possible_start})",
                    )
                )
    return violations


def _check_budget(itinerary: Itinerary, party: PartyConstraints) -> list[ConstraintViolation]:
    if party.budget_ceiling is None:
        return []
    total = sum(stop.price for stop in itinerary.stops)
    if total > party.budget_ceiling:
        return [
            ConstraintViolation(
                "budget_exceeded",
                None,
                f"total {total} exceeds ceiling {party.budget_ceiling}",
            )
        ]
    return []


def _check_category_diversity(itinerary: Itinerary, party: PartyConstraints) -> list[ConstraintViolation]:
    violations = []
    by_day: dict[date, dict[str, int]] = {}
    for stop in itinerary.stops:
        counts = by_day.setdefault(stop.day, {})
        counts[stop.category] = counts.get(stop.category, 0) + 1
    for day, counts in by_day.items():
        for category, count in counts.items():
            if count > party.max_repeat_per_type_per_day:
                violations.append(
                    ConstraintViolation(
                        "category_diversity_violated",
                        None,
                        f"{count}x '{category}' on {day} exceeds max "
                        f"{party.max_repeat_per_type_per_day}",
                    )
                )
    return violations


def _check_date_window(itinerary: Itinerary, party: PartyConstraints) -> list[ConstraintViolation]:
    if party.trip_start is None and party.trip_end is None:
        return []
    violations = []
    for stop in itinerary.stops:
        if party.trip_start is not None and stop.day < party.trip_start:
            violations.append(
                ConstraintViolation(
                    "outside_trip_window", stop.place_id, f"{stop.day} before trip_start {party.trip_start}"
                )
            )
        elif party.trip_end is not None and stop.day > party.trip_end:
            violations.append(
                ConstraintViolation(
                    "outside_trip_window", stop.place_id, f"{stop.day} after trip_end {party.trip_end}"
                )
            )
    return violations


def _check_party_fit(itinerary: Itinerary, party: PartyConstraints) -> list[ConstraintViolation]:
    violations = []
    for stop in itinerary.stops:
        if party.kids and not stop.kid_friendly:
            violations.append(
                ConstraintViolation("not_kid_friendly", stop.place_id, f"{stop.place_id} is not kid_friendly")
            )
        if party.accessibility and not stop.wheelchair_accessible:
            violations.append(
                ConstraintViolation(
                    "not_accessible", stop.place_id, f"{stop.place_id} is not wheelchair_accessible"
                )
            )
        if stop.category == "eat":
            if party.halal and not stop.halal:
                violations.append(
                    ConstraintViolation("not_halal", stop.place_id, f"{stop.place_id} is not halal")
                )
            if party.vegetarian and not stop.vegetarian_friendly:
                violations.append(
                    ConstraintViolation(
                        "not_vegetarian_friendly", stop.place_id, f"{stop.place_id} is not vegetarian_friendly"
                    )
                )
    return violations


ALL_CHECKS = (
    _check_open,
    _check_travel_time,
)
ALL_PARTY_CHECKS = (
    _check_budget,
    _check_category_diversity,
    _check_date_window,
    _check_party_fit,
)


def check_itinerary(itinerary: Itinerary, party: PartyConstraints) -> ItineraryReport:
    """Run every constraint against one itinerary and return the full
    violation list (empty => fully satisfied)."""
    violations: list[ConstraintViolation] = []
    for check in ALL_CHECKS:
        violations.extend(check(itinerary))
    for check in ALL_PARTY_CHECKS:
        violations.extend(check(itinerary, party))
    return ItineraryReport(tuple(violations))


@dataclass(frozen=True)
class BatchResult:
    reports: tuple[ItineraryReport, ...]

    @property
    def satisfaction_rate(self) -> float:
        if not self.reports:
            raise ValueError("no itineraries to evaluate")
        satisfied = sum(1 for r in self.reports if r.is_satisfied)
        return satisfied / len(self.reports)

    @property
    def all_satisfied(self) -> bool:
        """The §17 gate: 100%, hard fail. Any single violating
        itinerary in the batch fails the whole gate."""
        return all(r.is_satisfied for r in self.reports)


def check_batch(
    itineraries: list[Itinerary], parties: list[PartyConstraints]
) -> BatchResult:
    if len(itineraries) != len(parties):
        raise ValueError("itineraries and parties must be the same length (one party per itinerary)")
    return BatchResult(tuple(check_itinerary(it, p) for it, p in zip(itineraries, parties)))
