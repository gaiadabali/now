"""The itinerary domain vocabulary (ARCHITECTURE.md §12).

Plain frozen dataclasses with no SQLAlchemy and no DB import, for the same
reason `now_search.models` is dependency-free: the solver is the part of
this system most worth testing exhaustively, and it can only be tested
exhaustively if a fixture can build a hundred scenarios without a
Postgres container. The adapter that turns `public.places` rows into
`Stop`s lives in `now_itinerary.candidates`, which is the only module
here that knows a database exists.

**Times are minutes-since-midnight local**, not `datetime`. A stop is
open "18:00-23:00" as a property of the venue, not of a date, and
slot windows are compared against opening hours far more often than
against a calendar. `now_itinerary.timeutil` converts at the edges.
Minutes past midnight also means a venue open until 02:00 is `1560`
(> 1440), which keeps "closes after midnight" an ordinary number
comparison rather than a special case -- see `OpeningHours`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Slot(str, Enum):
    """§12 step 3's ladder: breakfast → morning → lunch → afternoon →
    dinner → night. Ordered, and the order is the day's shape -- `Day`
    stores stops keyed by slot, so "lunch before dinner" is structural
    rather than something the solver has to be told."""

    BREAKFAST = "breakfast"
    MORNING = "morning"
    LUNCH = "lunch"
    AFTERNOON = "afternoon"
    DINNER = "dinner"
    NIGHT = "night"

    @property
    def order(self) -> int:
        return SLOT_ORDER[self]


SLOT_ORDER: dict[Slot, int] = {slot: i for i, slot in enumerate(Slot)}


class Mobility(str, Enum):
    FULL = "full"
    LIMITED = "limited"
    WHEELCHAIR = "wheelchair"


@dataclass(frozen=True)
class OpeningHours:
    """One open interval, in minutes since local midnight.

    `closes` may exceed 1440 for a venue that shuts after midnight (a bar
    open 18:00-02:00 is `opens=1080, closes=1560`). Callers must not
    normalise that back into 0-1439: the whole point is that
    `opens <= t <= closes` stays a plain comparison.
    """

    opens: int
    closes: int

    def covers(self, start: int, end: int) -> bool:
        """True when [start, end] fits entirely inside this interval.

        Entirely, not partially: a stop the visitor cannot finish before
        closing time is not a stop, and §12's gate ("no closed venues")
        is checked against exactly this.
        """
        return self.opens <= start and end <= self.closes


@dataclass(frozen=True)
class Stop:
    """A candidate place the solver may or may not choose.

    `score` is whatever upstream relevance the caller computed --
    `now_blender`'s output for this user, a popularity prior at cold
    start, or a flat 1.0 when the caller only cares about feasibility.
    The solver maximises it; it never computes it.
    """

    place_id: int
    name: str
    type: str  # L1 type (§4): eat, drink, stay, do, shop, wellness, culture...
    lat: float
    lng: float
    area_term: str | None = None
    price_band: int | None = None  # 1-4 ($ .. $$$$); None = unpriced/unknown
    dwell_minutes: int = 60
    hours_by_weekday: dict[int, tuple[OpeningHours, ...]] = field(default_factory=dict)
    score: float = 1.0
    org_id: int | None = None
    is_partner: bool = False
    kid_friendly: bool = True
    wheelchair_accessible: bool | None = None  # None = unknown, which is NOT a promise
    halal: bool | None = None
    vegetarian: bool | None = None

    def hours_on(self, weekday: int) -> tuple[OpeningHours, ...]:
        """Open intervals for a weekday (0=Monday), or `()` for closed.

        A stop with **no hours data at all** is treated as open (`()` only
        ever means "closed that day" when the weekday key exists). That
        asymmetry is deliberate and is the one place this module trades
        strictness for coverage: 24 of Jakarta's places carry hours today,
        so failing closed on missing data would empty every itinerary.
        `validate.py` reports such stops as `unverified_hours` rather than
        silently blessing them -- the gate can then be run in either mode.
        """
        if not self.hours_by_weekday:
            return ()
        return self.hours_by_weekday.get(weekday, ())

    def has_hours_data(self) -> bool:
        return bool(self.hours_by_weekday)


@dataclass(frozen=True)
class Party:
    """Who is travelling. §8.B's contextual constraints, as data.

    Every field defaults to the permissive value, so a caller that knows
    nothing about the party gets "no party constraints" rather than an
    accidentally empty itinerary.
    """

    adults: int = 2
    children: int = 0
    mobility: Mobility = Mobility.FULL
    halal_only: bool = False
    vegetarian_only: bool = False

    @property
    def has_children(self) -> bool:
        return self.children > 0


@dataclass(frozen=True)
class SlotSpec:
    """One slot's time window and which L1 types may fill it.

    Data, not code, because "dinner is 18:00-21:00 and wants an `eat`"
    is a per-site editorial judgement -- a Bali itinerary's night slot
    runs later than Jakarta's. `slots.DEFAULT_SLOT_SPECS` is the
    starting point; `sites.itinerary_slots` overrides it without a
    deploy, exactly as `sites.ranking_weights` does for the blender.
    """

    slot: Slot
    window_start: int
    window_end: int
    eligible_types: frozenset[str]
    required: bool = False

    def __post_init__(self) -> None:
        if self.window_end <= self.window_start:
            raise ValueError(f"{self.slot}: window_end must be after window_start")


@dataclass(frozen=True)
class ItineraryRequest:
    """§12 step 1's inputs."""

    stops: tuple[Stop, ...]
    days: int
    start_weekday: int = 0  # 0=Monday; day i falls on (start_weekday + i) % 7
    party: Party = field(default_factory=Party)
    slot_specs: tuple[SlotSpec, ...] = ()
    budget_ceiling: int | None = None  # sum of price_band across the whole trip
    max_price_band: int | None = None  # per-stop ceiling
    max_travel_minutes_per_day: int | None = None
    # §8.D's diversity cap, applied per day. **3, not 2** -- the default
    # ladder has three `eat` slots (breakfast, lunch, dinner), so a cap of
    # 2 does not read as "less repetitive", it reads as "no breakfast,
    # ever". Measured: with cap=2 the solver fills 10 of 12 slots across
    # two days and drops breakfast on both, silently, because breakfast is
    # the only optional one of the three. A cap below the number of
    # required same-type slots is rejected outright by `solver._precheck`;
    # this default is what keeps the *optional* meal reachable.
    max_per_type_per_day: int = 3
    max_per_org: int = 1  # "marriott.com appears 63x in the archive"
    required_partner_stops: int = 0
    interest_types: frozenset[str] = frozenset()

    def weekday_for_day(self, day_index: int) -> int:
        return (self.start_weekday + day_index) % 7


@dataclass(frozen=True)
class PlannedStop:
    stop: Stop
    day_index: int
    slot: Slot
    arrive_minute: int
    depart_minute: int
    travel_minutes_from_previous: int = 0
    sequence_index: int = 0


@dataclass(frozen=True)
class Day:
    day_index: int
    weekday: int
    stops: tuple[PlannedStop, ...]

    @property
    def travel_minutes(self) -> int:
        return sum(s.travel_minutes_from_previous for s in self.stops)


@dataclass(frozen=True)
class Itinerary:
    days: tuple[Day, ...]
    unfilled_slots: tuple[tuple[int, Slot], ...] = ()
    solver_status: str = ""
    solve_seconds: float = 0.0

    @property
    def all_stops(self) -> tuple[PlannedStop, ...]:
        return tuple(s for day in self.days for s in day.stops)

    @property
    def total_price_band(self) -> int:
        return sum(s.stop.price_band or 0 for s in self.all_stops)
