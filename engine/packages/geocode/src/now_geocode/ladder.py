"""The strict source ladder (ARCHITECTURE.md E2.5 deliverable #1):

    1. existing coordinates (geo.jsonl)          free, use first
    2. structured address (venues.jsonl)         -> geocode
    3. venue name + city context                 -> Places text search
    4. unresolved                                -> review queue, NOT a guess

Every rung either produces a real, attributable result or falls through
— nothing here ever invents a coordinate. `resolve_candidate` is the one
function that walks the ladder for one `PlaceCandidate`; `pipeline.py`
calls it per candidate and layers area-assignment and quality gates on
top of whatever it returns.

**Resumability note**: on a `RetryableProviderError` at any rung, the
whole candidate is marked not-final in the state store and the *entire*
ladder is re-walked next run (including re-checking the free rung-1
coordinates, which is instant, and potentially re-issuing a rung-2 call
that had actually already succeeded before a later rung's transient
failure). That's a deliberate simplicity/cost tradeoff: retryable errors
are expected to be rare batch hiccups, not the common case, so
re-attempting a whole candidate is cheap in aggregate versus the
complexity of caching partial per-rung state.
"""

from __future__ import annotations

from dataclasses import dataclass

from now_geocode.models import PlaceCandidate, ProviderResult, Rung, Status
from now_geocode.providers.base import GeocodeProvider, RetryableProviderError
from now_geocode.quality import in_indonesia_bbox


@dataclass
class LadderOutcome:
    rung: Rung
    status: Status
    lat: float | None
    lng: float | None
    google_place_id: str | None
    confidence: float
    location_type: str | None
    flags: list[str]
    review_reason: str | None
    retryable_error: str | None = None  # set only when the ladder had to abort early


def resolve_candidate(
    candidate: PlaceCandidate,
    provider: GeocodeProvider | None,
    *,
    allow_synthetic: bool = False,
) -> LadderOutcome:
    # Rung 1 — existing coordinates, free, already resolved upstream.
    if candidate.existing_lat is not None and candidate.existing_lng is not None:
        flags: list[str] = []
        status = Status.RESOLVED
        if not in_indonesia_bbox(candidate.existing_lat, candidate.existing_lng):
            flags.append("out_of_bounds")
            status = Status.REJECTED
        return LadderOutcome(
            rung=Rung.EXISTING_COORDINATES,
            status=status,
            lat=candidate.existing_lat,
            lng=candidate.existing_lng,
            google_place_id=candidate.existing_google_place_id,
            confidence=0.95 if candidate.existing_google_place_id else 0.85,
            location_type="mappress_poi" if candidate.existing_google_place_id is None else "google_map_acf",
            flags=flags,
            review_reason=None,
        )

    if provider is None:
        return _unresolved(candidate, "no existing coordinates and no provider configured")

    # Rung 2 — structured address.
    if candidate.address:
        try:
            result = provider.geocode_address(candidate.address)
        except RetryableProviderError as exc:
            return _retryable(candidate, "address_geocode", exc)
        if result is not None:
            return _from_provider_result(Rung.ADDRESS_GEOCODE, candidate, result, allow_synthetic)

    # Rung 3 — name + city/province context.
    context = ", ".join(filter(None, [candidate.city, candidate.province, candidate.country])) or None
    try:
        result = provider.find_place(candidate.name, context)
    except RetryableProviderError as exc:
        return _retryable(candidate, "name_place_search", exc)
    if result is not None:
        return _from_provider_result(Rung.NAME_PLACE_SEARCH, candidate, result, allow_synthetic)

    # Rung 4 — nothing found anywhere. Review queue, not a guess.
    return _unresolved(candidate, "no free coordinate, address geocode and name search both returned zero results")


def _from_provider_result(
    rung: Rung, candidate: PlaceCandidate, result: ProviderResult, allow_synthetic: bool
) -> LadderOutcome:
    if result.is_synthetic and not allow_synthetic:
        # An offline/dry-run provider result must never masquerade as a
        # real resolution in the actual deliverable — see providers/offline.py.
        return _unresolved(
            candidate,
            f"offline/dry-run provider produced a synthetic point at rung {rung.value}; "
            "suppressed because allow_synthetic=False (the real-deliverable default)",
        )
    flags: list[str] = []
    status = Status.RESOLVED_SYNTHETIC if result.is_synthetic else Status.RESOLVED
    if not in_indonesia_bbox(result.lat, result.lng):
        flags.append("out_of_bounds")
        status = Status.REJECTED
    return LadderOutcome(
        rung=rung,
        status=status,
        lat=result.lat,
        lng=result.lng,
        google_place_id=result.google_place_id,
        confidence=result.confidence,
        location_type=result.location_type,
        flags=flags,
        review_reason=None,
    )


def _unresolved(candidate: PlaceCandidate, reason: str) -> LadderOutcome:
    return LadderOutcome(
        rung=Rung.UNRESOLVED,
        status=Status.UNRESOLVED,
        lat=None,
        lng=None,
        google_place_id=None,
        confidence=0.0,
        location_type=None,
        flags=[],
        review_reason=reason,
    )


def _retryable(candidate: PlaceCandidate, at_rung: str, exc: Exception) -> LadderOutcome:
    outcome = _unresolved(candidate, f"retryable provider error at {at_rung}: {exc}")
    outcome.retryable_error = str(exc)
    return outcome
