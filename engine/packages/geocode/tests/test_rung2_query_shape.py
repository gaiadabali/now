"""Rung 2 must send the address BARE.

This is a counter-intuitive behaviour with a measured justification —
see `ladder._WHY_RUNG_2_IS_BARE`. Appending the row's city/province is
the obvious "fix" and it loses two thirds of the venue-level hits,
because this corpus's `city` is a colloquial area name ("Seminyak")
while OSM files those streets under a different administrative unit
("Kerobokan Kelod"), and Nominatim returns zero when a token cannot be
reconciled.

These tests exist so that the next person to have that idea sees it
fail loudly with a pointer to the numbers, rather than shipping a
silent regression."""

from __future__ import annotations

from now_geocode.ladder import location_context, resolve_candidate
from now_geocode.models import PlaceCandidate, ProviderResult


def candidate(**kw) -> PlaceCandidate:
    base = dict(
        key="k", name="A Venue", address=None, city=None, province=None, country=None,
        existing_lat=None, existing_lng=None, existing_google_place_id=None,
    )
    base.update(kw)
    return PlaceCandidate(**base)


class RecordingProvider:
    """Captures exactly what each rung asked for."""

    name = "recording"

    def __init__(self, address_result=None, place_result=None):
        self.address_queries: list[str] = []
        self.place_calls: list[tuple] = []
        self._address_result = address_result
        self._place_result = place_result

    def geocode_address(self, address):
        self.address_queries.append(address)
        return self._address_result

    def find_place(self, name, context):
        self.place_calls.append((name, context))
        return self._place_result


def a_result() -> ProviderResult:
    return ProviderResult(
        lat=-8.68, lng=115.15, formatted_address="x", google_place_id=None,
        location_type="osm_poi", confidence=0.9, provider="recording",
    )


def test_rung_2_sends_the_address_unmodified():
    provider = RecordingProvider(address_result=a_result())
    c = candidate(address="Jl. Pura Mertasari", city="Seminyak", province="Bali", country="Indonesia")

    resolve_candidate(c, provider)

    assert provider.address_queries == ["Jl. Pura Mertasari"], (
        "rung 2 must send the bare address; appending city/province was measured "
        "and lost two thirds of venue-level hits — see ladder._WHY_RUNG_2_IS_BARE"
    )


def test_rung_2_query_carries_no_city_or_province_tokens():
    provider = RecordingProvider(address_result=a_result())
    c = candidate(address="Jalan Raya", city="Ubud", province="Bali", country="Indonesia")

    resolve_candidate(c, provider)

    sent = provider.address_queries[0].lower()
    for leaked in ("ubud", "bali", "indonesia"):
        assert leaked not in sent


def test_rung_3_still_does_qualify_with_context():
    """Rung 3 asks for a *name*, not an address, and there the context
    genuinely helps — the asymmetry is deliberate, not an oversight."""
    provider = RecordingProvider(address_result=None, place_result=a_result())
    c = candidate(address="Jalan Raya", city="Ubud", province="Bali", country="Indonesia")

    resolve_candidate(c, provider)

    name, context = provider.place_calls[0]
    assert name == "A Venue"
    assert context == "Ubud, Bali, Indonesia"


def test_location_context_is_the_shared_definition_of_where():
    c = candidate(city="Seminyak", province="Bali", country="Indonesia")
    assert location_context(c) == "Seminyak, Bali, Indonesia"


def test_location_context_is_none_when_nothing_is_known():
    assert location_context(candidate()) is None


# --------------------------------------------------------------------------
# The venue confidence floor — region centroids must not ship as resolved
# --------------------------------------------------------------------------


def result_at(confidence: float, location_type: str, *, synthetic: bool = False) -> ProviderResult:
    return ProviderResult(
        lat=-8.4557, lng=115.1889, formatted_address="Bali", google_place_id=None,
        location_type=location_type, confidence=confidence, provider="recording",
        is_synthetic=synthetic,
    )


def test_region_centroid_is_rejected_not_resolved():
    """"Bali" resolving to a province centroid at 0.30 must not reach
    Row 2's hard-radius query as if it were a venue."""
    from now_geocode.models import Status

    provider = RecordingProvider(address_result=result_at(0.30, "osm_area"))
    outcome = resolve_candidate(candidate(address="Bali"), provider)

    assert outcome.status == Status.REJECTED
    assert "below_venue_confidence_floor" in outcome.flags
    assert outcome.review_reason and "region centroid" in outcome.review_reason


def test_rejected_row_keeps_its_coordinate_for_audit():
    """quality.py's contract: rejection flags, it does not silently drop."""
    provider = RecordingProvider(address_result=result_at(0.30, "osm_area"))
    outcome = resolve_candidate(candidate(address="Bali"), provider)
    assert (outcome.lat, outcome.lng) == (-8.4557, 115.1889)


def test_street_level_survives_the_floor():
    """Coarse but on the right street — still useful, must not be culled."""
    from now_geocode.models import Status

    provider = RecordingProvider(address_result=result_at(0.65, "osm_street"))
    outcome = resolve_candidate(candidate(address="Jl. Kemang Raya"), provider)
    assert outcome.status == Status.RESOLVED


def test_name_search_hit_sits_exactly_on_the_floor_and_is_kept():
    """Rung-3 OSM hits are capped at 0.50; an exclusive comparison would
    silently discard every one of them."""
    from now_geocode.models import Status

    provider = RecordingProvider(address_result=None, place_result=result_at(0.50, "osm_poi"))
    outcome = resolve_candidate(candidate(address="x"), provider)
    assert outcome.status == Status.RESOLVED


def test_synthetic_results_are_exempt_from_the_floor():
    """OfflineProvider's 0.30/0.42 are arbitrary exercise values; the
    floor is about real geocodes and must not break the dry-run path."""
    from now_geocode.models import Status

    provider = RecordingProvider(address_result=result_at(0.30, "offline_stub", synthetic=True))
    outcome = resolve_candidate(candidate(address="x"), provider, allow_synthetic=True)
    assert outcome.status == Status.RESOLVED_SYNTHETIC


def test_floor_is_overridable():
    from now_geocode.models import Status

    provider = RecordingProvider(address_result=result_at(0.30, "osm_area"))
    outcome = resolve_candidate(candidate(address="Bali"), provider, venue_confidence_floor=0.0)
    assert outcome.status == Status.RESOLVED


# --------------------------------------------------------------------------
# State-cache finality — a no-provider run must not poison the cache
# --------------------------------------------------------------------------


def test_no_provider_outcome_is_not_cacheable():
    """`--provider none` is the documented zero-cost first run. If its
    "no provider configured" outcome is cached as final, every later run
    WITH a provider is a silent no-op until the state file is deleted —
    the documented happy path poisoning the real one."""
    outcome = resolve_candidate(candidate(address="Jl. Anywhere"), None)
    assert outcome.cacheable is False


def test_genuine_zero_result_stays_cacheable():
    """A provider that actually answered "nothing here" IS a stable
    negative — caching it is the whole point of the cache."""
    provider = RecordingProvider(address_result=None, place_result=None)
    outcome = resolve_candidate(candidate(address="Jl. Anywhere"), provider)
    assert outcome.cacheable is True


def test_resolved_outcome_stays_cacheable():
    provider = RecordingProvider(address_result=result_at(0.90, "osm_poi"))
    assert resolve_candidate(candidate(address="x"), provider).cacheable is True


def test_pipeline_does_not_persist_a_no_provider_run_as_final(tmp_path):
    """End-to-end: run with no provider, then with one, against the same
    state file. The second run must actually call the provider."""
    from now_geocode.pipeline import run
    from now_geocode.state import StateStore

    venues = [{"wp_id": 1, "name": "Somewhere", "status": "publish", "address": "Jl. Anywhere"}]
    state_path = tmp_path / "s.jsonl"

    run(venues, [], provider=None, state=StateStore(state_path))

    provider = RecordingProvider(address_result=result_at(0.90, "osm_poi"))
    places, _ = run(venues, [], provider=provider, state=StateStore(state_path))

    assert provider.address_queries, "a no-provider run must not suppress the real run"
    assert places[0].status.value == "resolved"
