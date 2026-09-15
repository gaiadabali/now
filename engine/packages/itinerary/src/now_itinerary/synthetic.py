"""Deterministic synthetic stops, for testing the solver without a database.

`now_filters.synthetic` exists for the same reason and this mirrors its
role: E5.2's constraints are the kind that need *many* scenarios to test
honestly -- a venue that closes early, a party with a wheelchair user, a
budget one band too tight -- and building each of those from real
`public.places` rows would make the suite both slow and dependent on
whatever the archive happens to contain today.

Seeded and fully deterministic: the same seed produces the same stops, so
a failing case is reproducible from its seed alone.
"""

from __future__ import annotations

import random

from now_itinerary.models import OpeningHours, Stop

# Roughly central Jakarta, so haversine distances land in a realistic
# range rather than producing 0-minute or 5-hour journeys.
CENTER_LAT = -6.2088
CENTER_LNG = 106.8456
SPREAD_DEG = 0.045  # ~5km

TYPE_POOL = ("eat", "drink", "do", "culture", "shop", "wellness")

ALL_DAY = (OpeningHours(opens=7 * 60, closes=23 * 60),)


def make_stop(
    place_id: int,
    *,
    type: str = "eat",  # noqa: A002 -- mirrors the model field name
    name: str | None = None,
    lat: float = CENTER_LAT,
    lng: float = CENTER_LNG,
    hours: tuple[OpeningHours, ...] | None = None,
    weekdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6),
    **kwargs,
) -> Stop:
    """One stop with sensible defaults; override exactly what a test is about."""
    hours = ALL_DAY if hours is None else hours
    return Stop(
        place_id=place_id,
        name=name or f"{type}-{place_id}",
        type=type,
        lat=lat,
        lng=lng,
        hours_by_weekday={wd: hours for wd in weekdays},
        **kwargs,
    )


def make_stops(
    count: int,
    *,
    seed: int = 1234,
    types: tuple[str, ...] = TYPE_POOL,
    spread_deg: float = SPREAD_DEG,
    with_hours: bool = True,
) -> tuple[Stop, ...]:
    """A varied, deterministic candidate pool.

    Types cycle rather than being drawn randomly so a caller asking for 12
    stops across 6 types reliably gets 2 of each -- a random draw would
    occasionally produce zero `eat` candidates and turn an unrelated test
    into a flaky one.
    """
    rng = random.Random(seed)
    stops: list[Stop] = []
    for i in range(count):
        kind = types[i % len(types)]
        stops.append(
            make_stop(
                place_id=1000 + i,
                type=kind,
                lat=CENTER_LAT + rng.uniform(-spread_deg, spread_deg),
                lng=CENTER_LNG + rng.uniform(-spread_deg, spread_deg),
                hours=ALL_DAY if with_hours else (),
                weekdays=(0, 1, 2, 3, 4, 5, 6) if with_hours else (),
                price_band=rng.randint(1, 4),
                dwell_minutes=rng.choice((45, 60, 90)),
                score=round(rng.uniform(0.1, 1.0), 3),
                org_id=None,
            )
        )
    if not with_hours:
        # `hours_by_weekday={}` is the "no hours data" case, which is
        # distinct from "closed" -- see Stop.hours_on.
        stops = [
            Stop(**{**s.__dict__, "hours_by_weekday": {}}) for s in stops
        ]
    return tuple(stops)
