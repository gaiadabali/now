"""Travel time between stops.

§15 is explicit about where these numbers come from in production: OSRM
self-hosted, plus Google Distance Matrix **sampled** for traffic
multipliers, precomputed into `engine.travel_matrix` per area cluster --
never a routing call per request. E5.1 builds that. This module is the
*interface* that lets E5.2's solver be built and tested before it exists,
plus the fallback that makes the solver runnable today.

`TravelMatrix` is a Protocol rather than a base class so the E5.1
implementation (a dict loaded from `engine.travel_matrix`) satisfies it
without importing anything from here.

**`HaversineMatrix` is a placeholder and says so at every call site.**
Straight-line distance over a fixed average speed is wrong in Jakarta in
a specific, predictable direction: it under-estimates. §15's own framing
is that "Jakarta traffic is the problem", so an itinerary built on
haversine will be optimistic about how much fits in a day. It is here so
the solver can be exercised end to end, and `is_estimate` is on the
Protocol so callers -- and `validate.py` -- can tell a real matrix from a
guess rather than having to know which one they were handed.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from now_itinerary.models import Stop

EARTH_RADIUS_KM = 6371.0

# Deliberately pessimistic vs. a straight-line "as the crow flies" speed:
# real roads are not straight, and this is the only correction the
# haversine fallback makes for that. Jakarta's actual door-to-door
# average is worse still at peak; see this module's docstring.
DEFAULT_AVERAGE_SPEED_KMH = 18.0
DEFAULT_MINIMUM_MINUTES = 5


@runtime_checkable
class TravelMatrix(Protocol):
    @property
    def is_estimate(self) -> bool:
        """True when these numbers are modelled rather than measured.

        Exposed so a constraint gate can refuse to certify an itinerary
        whose travel budget was only ever checked against a guess.
        """
        ...

    def minutes(self, origin: Stop, destination: Stop) -> int: ...


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class HaversineMatrix:
    """Straight-line distance / average speed. See module docstring --
    this is a stand-in for E5.1, not a routing engine."""

    def __init__(
        self,
        *,
        average_speed_kmh: float = DEFAULT_AVERAGE_SPEED_KMH,
        minimum_minutes: int = DEFAULT_MINIMUM_MINUTES,
    ) -> None:
        if average_speed_kmh <= 0:
            raise ValueError("average_speed_kmh must be positive")
        self._speed = average_speed_kmh
        self._minimum = minimum_minutes

    @property
    def is_estimate(self) -> bool:
        return True

    def minutes(self, origin: Stop, destination: Stop) -> int:
        if origin.place_id == destination.place_id:
            return 0
        km = haversine_km(origin.lat, origin.lng, destination.lat, destination.lng)
        return max(self._minimum, round(km / self._speed * 60))


class PrecomputedMatrix:
    """E5.1's shape: `(origin_place_id, destination_place_id) -> minutes`,
    loaded from `engine.travel_matrix`.

    Falls back to `fallback` for pairs the matrix does not cover, because
    a partially-populated matrix is the normal state during backfill and
    a `KeyError` mid-solve would be a worse answer than an estimate. The
    fallback's use is counted -- `coverage()` reports it -- so "the
    matrix is 100% real" is a checkable claim rather than an assumption.
    """

    def __init__(
        self,
        minutes_by_pair: dict[tuple[int, int], int],
        *,
        fallback: TravelMatrix | None = None,
    ) -> None:
        self._pairs = minutes_by_pair
        self._fallback = fallback or HaversineMatrix()
        self._hits = 0
        self._misses = 0

    @property
    def is_estimate(self) -> bool:
        """An unqualified True until every pair asked for came from the
        table. A matrix that fell back even once produced at least one
        modelled number, and the gate should know."""
        return self._misses > 0

    def minutes(self, origin: Stop, destination: Stop) -> int:
        if origin.place_id == destination.place_id:
            return 0
        found = self._pairs.get((origin.place_id, destination.place_id))
        if found is None:
            # Symmetry is an assumption the table may not hold; try the
            # reverse before giving up on it.
            found = self._pairs.get((destination.place_id, origin.place_id))
        if found is None:
            self._misses += 1
            return self._fallback.minutes(origin, destination)
        self._hits += 1
        return found

    def coverage(self) -> float:
        total = self._hits + self._misses
        return 1.0 if total == 0 else self._hits / total
