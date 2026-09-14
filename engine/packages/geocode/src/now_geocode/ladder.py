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
    cacheable: bool = True
    """May `state.py` record this outcome as FINAL (never re-attempt)?

    False for outcomes that describe *this run's configuration* rather
    than the world. The case that matters: `--provider none` is the
    documented zero-cost first run, and it returns "no provider
    configured" for every addressed candidate. Cached as final — which
    is what `final=outcome.retryable_error is None` did — those 141 rows
    become permanent negatives, and the next run *with* a real provider
    silently resolves nothing (`from cache: 203, provider calls: 0`)
    until someone deletes the state file. The documented happy path
    poisoned the real one.

    A genuine zero-result from a provider that actually answered stays
    cacheable: that is a real stable negative and is the whole point of
    the cache."""


def location_context(candidate: PlaceCandidate) -> str | None:
    """The candidate's own administrative envelope, coarsest-last:
    "Seminyak, Bali, Indonesia". Shared by rungs 2 and 3 so they cannot
    disagree about what "where" means for the same row."""

    return ", ".join(filter(None, [candidate.city, candidate.province, candidate.country])) or None


_WHY_RUNG_2_IS_BARE = """
Rung 2 sends `candidate.address` with NO city/province appended. This
looks like an oversight — rung 3 *does* qualify its query — and it is
not. It was tried, measured against all 127 addressed candidates on a
self-hosted Nominatim, and reverted:

    strategy                venue-level  street  area  zero
    A  bare                          14      31     5    77   <- kept
    B  + city + province              5      29     4    89
    C  + province only                5      34     4    84
    D  province, then bare            11      35     4    77

Qualifying *lost* two thirds of the venue-level hits. The cause is that
this corpus's `city` field holds a colloquial tourist-area name, not an
administrative unit: rows say "Seminyak" or "Canggu", while OSM files
those streets under Kerobokan Kelod / Kuta Utara / Badung. Nominatim
requires every token to reconcile against its hierarchy, so an
administratively-wrong city turns a working query into zero results:

    "Jl. Pura Mertasari"                 -> Jalan Pura Mertasari V (highway)
    "Jl. Pura Mertasari, Seminyak, Bali" -> ZERO RESULTS
    "Jl. Pura Mertasari, Bali"           -> Jalan Pura Mertasari V (highway)

Strategy D cannot rescue it either: the qualified query often returns a
*worse* match rather than nothing, so the bare fallback never fires.

Adding city context is therefore only safe once `city` holds a real
administrative unit. Until then, bare wins, and the street-level results
and duplicate centroids it produces are a data problem (addresses
without house numbers), not a query-construction one.
"""


# A geocode this weak is a region, not a venue. Measured on the real
# corpus: `osm_area` (0.30) results were things like "Bali", "Ubud" and
# "Nusa Dua" — a province and two tourist areas — each shipping as a
# RESOLVED place with a real-looking coordinate at a regional centroid.
# ARCHITECTURE.md §7 Row 2 does a hard-radius `ST_DWithin` against these
# points, so a city centroid wearing a venue row is not a near-miss: it
# puts a "nearby" venue kilometres from where the reader is standing.
#
# Provider-neutral on purpose. It catches OSM's `osm_area` (0.30) and
# `osm_locality` (0.45) and Google's `APPROXIMATE` (0.35) with one rule,
# rather than enumerating each provider's vocabulary. Street-level
# results (0.65) stay above it: coarse, but genuinely on the right
# street. Rung-3 name hits land exactly on the floor (0.50) and are kept.
#
# Rejection is not a drop. Per `quality.py`'s contract the row still
# ships with its coordinate and a flag, so a human can audit it — it is
# simply not `resolved`, so nothing downstream treats it as a venue.
VENUE_CONFIDENCE_FLOOR = 0.50


# How specific a result is, independent of which rung or provider
# produced it. Confidence cannot answer this: a rung-3 OSM name hit is
# capped at 0.50 while a rung-2 street hit scores 0.65, so ranking by
# confidence would always prefer the street — the exact inversion that
# left 33 rows on street points and collapsed 15 onto shared coordinates.
# A venue match beats a street match for a venue, whatever its
# confidence, so the comparison has to be on granularity.
_SPECIFICITY = {
    # venue-level — a mapped place, not a line or a polygon
    "osm_poi": 4, "osm_building": 4, "ROOFTOP": 4, "place_search": 4,
    "mappress_poi": 4, "google_map_acf": 4, "manual_override": 5,
    "RANGE_INTERPOLATED": 3,
    "osm_street": 2, "GEOMETRIC_CENTER": 2,
    "osm_locality": 1,
    "osm_area": 0, "APPROXIMATE": 0,
}
VENUE_SPECIFICITY = 4


def specificity(location_type: str | None) -> int:
    """Rank a `location_type` by how precisely it identifies a venue.
    Unknown vocabularies sit just under street level: better than a
    region centroid, not trusted as a venue."""

    return _SPECIFICITY.get(location_type or "", 1)


def _apply_override(candidate: PlaceCandidate, ov) -> LadderOutcome:
    """Rung 0. See `overrides.py` for the action semantics."""

    if ov.action == "override":
        return LadderOutcome(
            rung=Rung.MANUAL_OVERRIDE,
            status=Status.REJECTED if not in_indonesia_bbox(ov.lat, ov.lng) else Status.RESOLVED,
            lat=ov.lat,
            lng=ov.lng,
            google_place_id=None,
            confidence=ov.confidence,
            location_type="manual_override",
            flags=[] if in_indonesia_bbox(ov.lat, ov.lng) else ["out_of_bounds"],
            review_reason=None,
        )
    if ov.action == "merge_into":
        # Kept, not vanished: the duplicate stays auditable and the output
        # row count stays stable for downstream consumers.
        return LadderOutcome(
            rung=Rung.MANUAL_OVERRIDE,
            status=Status.REJECTED,
            lat=None,
            lng=None,
            google_place_id=None,
            confidence=0.0,
            location_type=None,
            flags=["merged_duplicate"],
            review_reason=f"duplicate of place_key {ov.merge_into_place_key}: {ov.note}",
        )
    # drop — a wrong coordinate removed, the place itself retained.
    return _unresolved(candidate, f"manual override: {ov.note}")


def resolve_candidate(
    candidate: PlaceCandidate,
    provider: GeocodeProvider | None,
    *,
    allow_synthetic: bool = False,
    venue_confidence_floor: float = VENUE_CONFIDENCE_FLOOR,
    overrides: dict | None = None,
    challenge_coarse_rung2: bool = True,
) -> LadderOutcome:
    # Rung 0 — a human checked this one. Outranks everything below,
    # including the free seed, because that is what it is for.
    if overrides:
        ov = overrides.get(candidate.key)
        if ov is not None:
            return _apply_override(candidate, ov)

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
        # Not cacheable: this says the run had no provider, not that the
        # place cannot be found. See LadderOutcome.cacheable.
        return _unresolved(
            candidate, "no existing coordinates and no provider configured", cacheable=False
        )

    # Rung 2 — structured address, sent BARE. See `_WHY_RUNG_2_IS_BARE`.
    rung2: LadderOutcome | None = None
    if candidate.address:
        try:
            result = provider.geocode_address(candidate.address)
        except RetryableProviderError as exc:
            return _retryable(candidate, "address_geocode", exc)
        if result is not None:
            rung2 = _from_provider_result(
                Rung.ADDRESS_GEOCODE, candidate, result, allow_synthetic, venue_confidence_floor
            )
            # A venue-level hit is as good as this ladder gets — take it.
            # Anything coarser is allowed to be challenged below, because
            # a street is not an answer to "where is this venue".
            if not challenge_coarse_rung2 or specificity(rung2.location_type) >= VENUE_SPECIFICITY:
                return rung2

    # Rung 3 — name + city/province context.
    #
    # Reached in two ways: rung 2 found nothing, or rung 2 found something
    # too coarse to be the venue. The second case used to be impossible —
    # the ladder returned on rung 2's first success — and that is why 33
    # rows sat on street points while a name search would have found the
    # building. Eight of the eleven corrections in
    # jakarta/site/place-overrides.md came from exactly this query, run by
    # hand after the fact.
    context = location_context(candidate)
    try:
        result = provider.find_place(candidate.name, context)
    except RetryableProviderError as exc:
        if rung2 is not None:
            # A transient failure on the challenge must not discard a
            # result we already legitimately hold.
            return rung2
        return _retryable(candidate, "name_place_search", exc)
    if result is not None:
        rung3 = _from_provider_result(
            Rung.NAME_PLACE_SEARCH, candidate, result, allow_synthetic, venue_confidence_floor
        )
        if rung2 is None:
            return rung3
        return _more_specific(rung2, rung3)
    if rung2 is not None:
        return rung2

    # Rung 4 — nothing found anywhere. Review queue, not a guess.
    return _unresolved(candidate, "no free coordinate, address geocode and name search both returned zero results")


def _more_specific(rung2: LadderOutcome, rung3: LadderOutcome) -> LadderOutcome:
    """Pick between a coarse address hit and a name hit.

    Granularity first, confidence only as a tie-break — see `_SPECIFICITY`
    for why confidence alone gets this backwards. A rejected outcome (out
    of bounds, or below the venue floor) never wins over a resolved one,
    however specific it claims to be."""

    r2_ok = rung2.status is not Status.REJECTED
    r3_ok = rung3.status is not Status.REJECTED
    if r2_ok != r3_ok:
        return rung2 if r2_ok else rung3

    s2, s3 = specificity(rung2.location_type), specificity(rung3.location_type)
    if s3 != s2:
        return rung3 if s3 > s2 else rung2
    return rung3 if rung3.confidence > rung2.confidence else rung2


def _from_provider_result(
    rung: Rung,
    candidate: PlaceCandidate,
    result: ProviderResult,
    allow_synthetic: bool,
    venue_confidence_floor: float = VENUE_CONFIDENCE_FLOOR,
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
    review_reason: str | None = None
    status = Status.RESOLVED_SYNTHETIC if result.is_synthetic else Status.RESOLVED
    if not in_indonesia_bbox(result.lat, result.lng):
        flags.append("out_of_bounds")
        status = Status.REJECTED
    elif not result.is_synthetic and result.confidence < venue_confidence_floor:
        # Region-level hit — see VENUE_CONFIDENCE_FLOOR. Synthetic points
        # are exempt: OfflineProvider's confidences (0.30/0.42) are
        # arbitrary exercise values, and their trustworthiness is already
        # governed by `is_synthetic` + `allow_synthetic` above. Applying a
        # real-world quality floor to fake data would only break the
        # dry-run self-test without protecting any real deliverable.
        flags.append("below_venue_confidence_floor")
        status = Status.REJECTED
        review_reason = (
            f"{result.location_type or 'result'} at confidence {result.confidence:.2f} is below the "
            f"{venue_confidence_floor:.2f} venue floor — this is a region centroid, not the venue"
        )
    return LadderOutcome(
        rung=rung,
        status=status,
        lat=result.lat,
        lng=result.lng,
        google_place_id=result.google_place_id,
        confidence=result.confidence,
        location_type=result.location_type,
        flags=flags,
        review_reason=review_reason,
    )


def _unresolved(candidate: PlaceCandidate, reason: str, *, cacheable: bool = True) -> LadderOutcome:
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
        cacheable=cacheable,
    )


def _retryable(candidate: PlaceCandidate, at_rung: str, exc: Exception) -> LadderOutcome:
    outcome = _unresolved(candidate, f"retryable provider error at {at_rung}: {exc}")
    outcome.retryable_error = str(exc)
    return outcome
