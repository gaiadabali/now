from now_geocode.ladder import resolve_candidate
from now_geocode.models import ProviderResult, PlaceCandidate, Rung, Status
from now_geocode.providers.base import RetryableProviderError


def _candidate(**kwargs) -> PlaceCandidate:
    base = dict(
        key="k",
        name="Test Place",
        address=None,
        city=None,
        province=None,
        country=None,
        existing_lat=None,
        existing_lng=None,
        existing_google_place_id=None,
    )
    base.update(kwargs)
    return PlaceCandidate(**base)


class StubProvider:
    name = "stub"

    def __init__(self, address_result=None, place_result=None, raise_on_address=None, raise_on_place=None):
        self.address_result = address_result
        self.place_result = place_result
        self.raise_on_address = raise_on_address
        self.raise_on_place = raise_on_place
        self.address_calls = []
        self.place_calls = []

    def geocode_address(self, address):
        self.address_calls.append(address)
        if self.raise_on_address:
            raise self.raise_on_address
        return self.address_result

    def find_place(self, name, context):
        self.place_calls.append((name, context))
        if self.raise_on_place:
            raise self.raise_on_place
        return self.place_result


def test_rung1_existing_coordinates_never_calls_provider():
    c = _candidate(existing_lat=-6.2, existing_lng=106.8)
    provider = StubProvider()
    outcome = resolve_candidate(c, provider)
    assert outcome.rung == Rung.EXISTING_COORDINATES
    assert outcome.status == Status.RESOLVED
    assert provider.address_calls == []
    assert provider.place_calls == []


def test_rung1_out_of_bbox_is_rejected_not_dropped():
    c = _candidate(existing_lat=52.37, existing_lng=4.90)  # Amsterdam
    outcome = resolve_candidate(c, None)
    assert outcome.status == Status.REJECTED
    assert "out_of_bounds" in outcome.flags
    assert outcome.lat == 52.37  # preserved for audit, not blanked


def test_rung2_address_geocode_used_when_no_existing_coords():
    result = ProviderResult(
        lat=-6.26, lng=106.81, formatted_address="x", google_place_id="p1",
        location_type="ROOFTOP", confidence=0.95, provider="stub",
    )
    provider = StubProvider(address_result=result)
    c = _candidate(address="Jl. Kemang Raya")
    outcome = resolve_candidate(c, provider)
    assert outcome.rung == Rung.ADDRESS_GEOCODE
    assert outcome.status == Status.RESOLVED
    assert provider.place_calls == []  # never fell through to rung 3


def test_rung3_used_when_no_address_or_address_geocode_empty():
    result = ProviderResult(
        lat=-8.68, lng=115.15, formatted_address=None, google_place_id=None,
        location_type="place_search", confidence=0.6, provider="stub",
    )
    provider = StubProvider(address_result=None, place_result=result)
    c = _candidate(name="Some Venue", address="An address that yields nothing")
    outcome = resolve_candidate(c, provider)
    assert outcome.rung == Rung.NAME_PLACE_SEARCH
    assert outcome.status == Status.RESOLVED
    assert provider.address_calls == ["An address that yields nothing"]


def test_rung4_unresolved_when_nothing_found_never_fabricates():
    provider = StubProvider(address_result=None, place_result=None)
    c = _candidate(name="Ghost Venue", address="Nowhere")
    outcome = resolve_candidate(c, provider)
    assert outcome.rung == Rung.UNRESOLVED
    assert outcome.status == Status.UNRESOLVED
    assert outcome.lat is None and outcome.lng is None


def test_no_provider_and_no_existing_coords_is_unresolved():
    c = _candidate(name="X", address="Y")
    outcome = resolve_candidate(c, None)
    assert outcome.status == Status.UNRESOLVED


def test_retryable_error_at_rung2_does_not_fabricate_or_crash():
    provider = StubProvider(raise_on_address=RetryableProviderError("rate limited"))
    c = _candidate(address="Somewhere")
    outcome = resolve_candidate(c, provider)
    assert outcome.status == Status.UNRESOLVED
    assert outcome.retryable_error is not None


def test_synthetic_result_suppressed_by_default():
    synthetic = ProviderResult(
        lat=-6.2, lng=106.8, formatted_address=None, google_place_id=None,
        location_type="offline_stub_address", confidence=0.42, provider="offline",
        is_synthetic=True,
    )
    provider = StubProvider(address_result=synthetic)
    c = _candidate(address="Somewhere")
    outcome = resolve_candidate(c, provider, allow_synthetic=False)
    assert outcome.status == Status.UNRESOLVED
    assert outcome.lat is None


def test_synthetic_result_allowed_in_dry_run_mode():
    synthetic = ProviderResult(
        lat=-6.2, lng=106.8, formatted_address=None, google_place_id=None,
        location_type="offline_stub_address", confidence=0.42, provider="offline",
        is_synthetic=True,
    )
    provider = StubProvider(address_result=synthetic)
    c = _candidate(address="Somewhere")
    outcome = resolve_candidate(c, provider, allow_synthetic=True)
    assert outcome.status == Status.RESOLVED_SYNTHETIC
    assert outcome.lat == -6.2
