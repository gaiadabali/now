"""Geo + compatibility helpers for the blend's `w_geo` term and the
Sec.10 feature vector's `geo_distance`/`same_area`/`price_compat`/
`type_compat` fields.

All of these are **subject-relative**: "how close is this candidate to
the article/place the rail is being built for". Plain keyword search
(what `reranker.py` exercises end-to-end today) has no subject -- a
query string is not a place on a map -- so every function here is `None`
whenever `subject` is `None` or lacks the needed field, which is exactly
the state `now_blender.reranker.BlenderReranker.rerank()`'s
query-based call path is in. These functions exist, fully implemented
and unit-tested, so Row 1 (E3.5) and Row 2 (E3.6) -- which DO have a
subject place/article -- can call them directly rather than
re-implementing haversine distance or price-band ordering a second time.
"""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0

# ARCHITECTURE.md Sec.5 `places.price_band` enum, ordered cheapest to
# most expensive -- ordinal distance between two bands is how far apart
# they are on this scale, not a categorical match/no-match.
PRICE_BAND_ORDER: tuple[str, ...] = ("budget", "moderate", "upscale", "luxury")

DEFAULT_GEO_PROXIMITY_SCALE_M = 3000.0  # ARCHITECTURE.md Sec.6.5: Jakarta rails widen 2km->5km->15km


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def geo_distance_m(
    subject_lat: float | None, subject_lng: float | None, candidate_lat: float | None, candidate_lng: float | None
) -> float | None:
    if subject_lat is None or subject_lng is None or candidate_lat is None or candidate_lng is None:
        return None
    return haversine_m(subject_lat, subject_lng, candidate_lat, candidate_lng)


def geo_proximity_component(distance_m: float | None, *, scale_m: float = DEFAULT_GEO_PROXIMITY_SCALE_M) -> float | None:
    """The blend's `w_geo` input: 1.0 at zero distance, decaying
    exponentially with `scale_m` (default 3km, the midpoint of Row 2's
    own 2km/5km fallback-ladder rungs -- ARCHITECTURE.md Sec.8.F) --
    `None` (not 0.0) when distance itself is unknown, same "missing is
    not the same as worst-case" rule `decay.decay_factor` follows for
    freshness."""
    if distance_m is None:
        return None
    return math.exp(-distance_m / scale_m)


def same_area(subject_area_term: str | None, candidate_area_term: str | None) -> bool | None:
    if subject_area_term is None or candidate_area_term is None:
        return None
    return subject_area_term == candidate_area_term


def price_compat(subject_price_band: str | None, candidate_price_band: str | None) -> float | None:
    """1.0 for an identical band, decaying linearly with ordinal
    distance on `PRICE_BAND_ORDER` (e.g. budget vs. luxury, 3 steps
    apart, scores 0.0) -- ARCHITECTURE.md Sec.7 Row 1's cold-start
    formula names `price_band_proximity` as one of four multiplied
    factors; this is that factor, exposed standalone for the Sec.10
    feature vector's own `price_compat` field."""
    if subject_price_band not in PRICE_BAND_ORDER or candidate_price_band not in PRICE_BAND_ORDER:
        return None
    i = PRICE_BAND_ORDER.index(subject_price_band)
    j = PRICE_BAND_ORDER.index(candidate_price_band)
    span = len(PRICE_BAND_ORDER) - 1
    return 1.0 - abs(i - j) / span
