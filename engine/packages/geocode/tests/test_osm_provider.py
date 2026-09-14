"""Unit tests for the OSM providers, replayed against recorded fixture
JSON under tests/fixtures/osm/ — zero network access, zero API key.
Mirrors tests/test_google_provider.py's fake-session approach, with two
additions the OSM providers need and Google's does not: HTTP status
codes (Nominatim signals rate limiting with 429, not a JSON status
field) and an injected clock/sleep so the 1 req/s throttle is asserted
without a test that actually waits."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from now_geocode.providers.base import ProviderConfigError, ProviderError, RetryableProviderError
from now_geocode.providers.osm import (
    NAME_SEARCH_CONFIDENCE,
    NominatimProvider,
    PhotonProvider,
    classify_granularity,
    name_agrees,
)

FIXTURES = Path(__file__).parent / "fixtures" / "osm"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload, status_code: int = 200, raise_on_json: bool = False):
        self._payload = payload
        self.status_code = status_code
        self._raise_on_json = raise_on_json

    def json(self):
        if self._raise_on_json:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Records every .get() call; returns a queued response per URL."""

    def __init__(self, payload, status_code: int = 200, raise_on_json: bool = False):
        self.payload = payload
        self.status_code = status_code
        self.raise_on_json = raise_on_json
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout, "headers": headers})
        return FakeResponse(self.payload, self.status_code, self.raise_on_json)


def nominatim(fixture: str | None = None, *, payload=None, status_code: int = 200):
    session = FakeSession(_load(fixture) if fixture else payload, status_code)
    # min_interval_s=0 keeps the throttle out of the way of behaviour tests;
    # the throttle has its own dedicated tests below.
    return NominatimProvider(session=session, min_interval_s=0.0), session


def photon(fixture: str | None = None, *, payload=None, status_code: int = 200):
    session = FakeSession(_load(fixture) if fixture else payload, status_code)
    return PhotonProvider(session=session, min_interval_s=0.0), session


# --------------------------------------------------------------------------
# Nominatim — rung 2 (structured address)
# --------------------------------------------------------------------------


def test_nominatim_geocode_address_poi():
    provider, _ = nominatim("nominatim_address_poi.json")
    result = provider.geocode_address("Grand Indonesia Shopping Town, Jakarta")
    assert result is not None
    assert (result.lat, result.lng) == (-6.1957601, 106.8214547)
    assert result.location_type == "osm_poi"
    assert result.confidence == 0.90
    assert result.provider == "nominatim"
    assert result.is_synthetic is False


def test_jsonv2_spells_the_osm_key_category_not_class():
    """Regression guard for a bug a live run caught and the original
    fixtures hid. Nominatim's format=jsonv2 returns `category`; only the
    older format=json returns `class`. Reading `class` alone classified
    every real result as `unknown` (0.40) instead of its true bucket."""
    provider, _ = nominatim("nominatim_address_poi.json")
    raw = provider.geocode_address("x").raw
    assert "category" in raw and "class" not in raw, "fixture must be real jsonv2 shape"
    assert provider.geocode_address("x").location_type == "osm_poi"


def test_legacy_class_spelling_still_classifies():
    """format=json (and older Nominatim) spell it `class`. Both are
    accepted so a version/format change cannot silently regress."""
    legacy = [{"lat": "-6.2", "lon": "106.8", "class": "amenity", "type": "restaurant",
               "name": "Legacy Shaped", "display_name": "Legacy Shaped, Jakarta"}]
    provider, _ = nominatim(payload=legacy)
    assert provider.geocode_address("x").location_type == "osm_poi"


def test_nominatim_never_fabricates_a_google_place_id():
    """An OSM id must never travel in a Google-named field — downstream
    consumers treat google_place_id as a Google identifier."""
    provider, _ = nominatim("nominatim_address_poi.json")
    result = provider.geocode_address("Grand Indonesia")
    assert result.google_place_id is None
    # ...but OSM identity is still preserved for audit.
    assert result.raw["osm_type"] == "way"
    assert isinstance(result.raw["osm_id"], int)


def test_nominatim_street_granularity():
    provider, _ = nominatim("nominatim_address_street.json")
    result = provider.geocode_address("Jalan Kemang Raya, Jakarta")
    assert result.location_type == "osm_street"
    assert result.confidence == 0.65


def test_nominatim_city_centroid_gets_low_confidence():
    """A vague address collapsing onto a city boundary is a known
    geocoder behaviour; it must not come back looking precise."""
    provider, _ = nominatim("nominatim_address_area.json")
    result = provider.geocode_address("Denpasar, Bali")
    assert result.location_type == "osm_area"
    assert result.confidence == 0.30


def test_nominatim_zero_results_returns_none_not_an_error():
    provider, _ = nominatim("nominatim_zero_results.json")
    assert provider.geocode_address("Nonexistent Address 12345") is None


def test_nominatim_sends_indonesia_bias_params():
    provider, session = nominatim("nominatim_address_poi.json")
    provider.geocode_address("Jalan Sudirman")
    params = session.calls[0]["params"]
    assert params["countrycodes"] == "id"
    assert params["viewbox"] == "94.5,6.5,141.5,-11.5"


def test_nominatim_sends_identifying_user_agent():
    provider, session = nominatim("nominatim_address_poi.json")
    provider.geocode_address("Jalan Sudirman")
    ua = session.calls[0]["headers"]["User-Agent"]
    assert "now-engine-geocode" in ua


def test_empty_user_agent_is_a_config_error_before_any_call():
    session = FakeSession([])
    provider = NominatimProvider(session=session, user_agent="", min_interval_s=0.0)
    with pytest.raises(ProviderConfigError):
        provider.geocode_address("Anywhere")
    assert session.calls == []


# --------------------------------------------------------------------------
# The name-agreement gate — rung 3's silent-wrong-answer defence
# --------------------------------------------------------------------------


def test_nominatim_find_place_accepts_a_real_name_match():
    provider, _ = nominatim("nominatim_name_hit.json")
    result = provider.find_place("Potato Head Beach Club", "Seminyak, Bali")
    assert result is not None
    assert (result.lat, result.lng) == (-8.6794068, 115.1499595)
    assert result.confidence == NAME_SEARCH_CONFIDENCE


def test_nominatim_find_place_rejects_the_enclosing_suburb():
    """The failure this gate exists for: searching a venue name returns
    a real coordinate for Seminyak, the suburb. That is worse than a
    miss, so it must come back as None."""
    provider, _ = nominatim("nominatim_name_wrong_thing.json")
    assert provider.find_place("Potato Head Beach Club", "Seminyak, Bali") is None


def test_photon_find_place_rejects_the_enclosing_suburb():
    provider, _ = photon("photon_name_wrong_thing.json")
    assert provider.find_place("Potato Head Beach Club", "Seminyak, Bali") is None


@pytest.mark.parametrize(
    "queried,feature,expected",
    [
        ("Potato Head Beach Club", "Potato Head Beach Club", True),
        ("Potato Head Beach Club", "Potato Head", True),   # {potato,head} == {potato,head}
        ("Potato Head Beach Club", "Seminyak", False),     # shares nothing
        # "Beach"/"Club" are non-distinctive, so this reduces to an empty
        # feature name — it could be any beach club, and is now rejected.
        # It was accepted while the gate scored on all significant tokens.
        ("Potato Head Beach Club", "Beach Club", False),
        ("Potato Head Beach Club", "Club", False),
        ("Revolver", "Revolver Espresso", True),           # {revolver} subset
        ("Revolver", "Seminyak", False),
        ("Revolver", None, False),
        ("Revolver", "", False),
        ("W Bali", "Seminyak", False),                     # "W" is not significant
        # Brand collision: the distinctive token "vacation" is absent from
        # the query, so these are different properties.
        ("Anantara Seminyak", "Anantara Vacation Club", False),
        # ...but a genuine shorter form of the same name still matches.
        ("The Legian Seminyak Bali", "The Legian Bali", True),
        ("The Legian Seminyak Bali", "The Trans Resort Bali", False),
    ],
)
def test_name_agrees_cases(queried, feature, expected):
    assert name_agrees(queried, feature) is expected


def test_name_agrees_ignores_the_administrative_envelope():
    """Matching against display_name would let a venue with 'Bali' in its
    name match its own province. The gate must read the feature's own
    name only."""
    display_name = "Seminyak, Badung, Bali, Indonesia"
    assert name_agrees("Bali Beach Resort", display_name) is False


# --------------------------------------------------------------------------
# Photon
# --------------------------------------------------------------------------


def test_photon_parses_geojson_lon_lat_order():
    """GeoJSON coordinates are [lon, lat] — the inverse of every other
    shape in this package. Getting this backwards puts Bali in Somalia."""
    provider, _ = photon("photon_name_hit.json")
    result = provider.find_place("Potato Head Beach Club", "Seminyak, Bali")
    assert result is not None
    assert result.lat == -8.6801   # negative -> southern hemisphere
    assert result.lng == 115.1553  # positive -> eastern hemisphere


def test_photon_street_granularity():
    provider, _ = photon("photon_address_street.json")
    result = provider.geocode_address("Jalan Kemang Raya")
    assert result.location_type == "osm_street"
    assert result.confidence == 0.65
    assert result.provider == "photon"


def test_photon_zero_results():
    provider, _ = photon("photon_zero_results.json")
    assert provider.geocode_address("Nothing Here") is None


def test_photon_formats_an_address_from_properties():
    provider, _ = photon("photon_name_hit.json")
    result = provider.find_place("Potato Head Beach Club", None)
    assert result.formatted_address == (
        "Potato Head Beach Club, Jalan Petitenget, Seminyak, Badung, Bali, Indonesia"
    )


def test_photon_feature_without_geometry_is_an_error_not_a_guess():
    payload = {"features": [{"properties": {"name": "X"}, "geometry": {}}]}
    provider, _ = photon(payload=payload)
    with pytest.raises(ProviderError):
        provider.geocode_address("X")


# --------------------------------------------------------------------------
# HTTP status mapping
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_retryable_status_codes(status_code):
    provider, _ = nominatim(payload=[], status_code=status_code)
    with pytest.raises(RetryableProviderError):
        provider.geocode_address("Anywhere")


@pytest.mark.parametrize("status_code", [401, 403])
def test_blocked_status_codes_are_config_errors(status_code):
    provider, _ = nominatim(payload=[], status_code=status_code)
    with pytest.raises(ProviderConfigError):
        provider.geocode_address("Anywhere")


def test_other_4xx_is_a_plain_provider_error():
    provider, _ = nominatim(payload=[], status_code=400)
    with pytest.raises(ProviderError):
        provider.geocode_address("Anywhere")


def test_network_error_is_retryable():
    class ExplodingSession:
        def get(self, *a, **k):
            raise ConnectionError("boom")

    provider = NominatimProvider(session=ExplodingSession(), min_interval_s=0.0)
    with pytest.raises(RetryableProviderError):
        provider.geocode_address("Anywhere")


def test_non_json_body_is_a_provider_error():
    session = FakeSession(None, 200, raise_on_json=True)
    provider = NominatimProvider(session=session, min_interval_s=0.0)
    with pytest.raises(ProviderError):
        provider.geocode_address("Anywhere")


# --------------------------------------------------------------------------
# Throttle — Nominatim's 1 req/s policy is a functional requirement
# --------------------------------------------------------------------------


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


def test_throttle_waits_between_calls():
    clock = FakeClock()
    session = FakeSession(_load("nominatim_address_poi.json"))
    provider = NominatimProvider(
        session=session, min_interval_s=1.0, sleep_fn=clock.sleep, clock_fn=clock.now
    )
    provider.geocode_address("one")
    provider.geocode_address("two")
    assert clock.slept == [1.0], "second call must wait a full interval"


def test_throttle_does_not_wait_when_enough_time_has_passed():
    clock = FakeClock()
    session = FakeSession(_load("nominatim_address_poi.json"))
    provider = NominatimProvider(
        session=session, min_interval_s=1.0, sleep_fn=clock.sleep, clock_fn=clock.now
    )
    provider.geocode_address("one")
    clock.t += 5.0  # caller spent 5s doing other work
    provider.geocode_address("two")
    assert clock.slept == []


def test_self_hosted_can_disable_the_throttle_entirely():
    clock = FakeClock()
    session = FakeSession(_load("nominatim_address_poi.json"))
    provider = NominatimProvider(
        session=session, min_interval_s=0.0, sleep_fn=clock.sleep, clock_fn=clock.now
    )
    for _ in range(5):
        provider.geocode_address("x")
    assert clock.slept == []


# --------------------------------------------------------------------------
# Granularity classification
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "osm_class,osm_type,expected",
    [
        ("amenity", "restaurant", "poi"),
        ("shop", "bakery", "poi"),
        ("tourism", "hotel", "poi"),
        ("leisure", "beach_resort", "poi"),
        ("building", "yes", "building"),
        ("highway", "residential", "street"),
        ("place", "suburb", "locality"),
        ("place", "village", "locality"),
        ("place", "city", "area"),
        ("place", "country", "area"),
        ("place", "house", "building"),
        ("boundary", "administrative", "area"),
        ("natural", "beach", "area"),
        (None, None, "unknown"),
        ("something_new", "x", "unknown"),
    ],
)
def test_classify_granularity(osm_class, osm_type, expected):
    assert classify_granularity(osm_class, osm_type) == expected


def test_confidence_never_exceeds_the_google_equivalent():
    """OSM POI geometry is community-contributed; claiming Google's
    ROOFTOP-grade 0.95 for it would overstate what we know."""
    from now_geocode.providers.google import GEOCODE_LOCATION_TYPE_CONFIDENCE
    from now_geocode.providers.osm import GRANULARITY_CONFIDENCE

    assert GRANULARITY_CONFIDENCE["poi"] < GEOCODE_LOCATION_TYPE_CONFIDENCE["ROOFTOP"]
    assert GRANULARITY_CONFIDENCE["street"] < GEOCODE_LOCATION_TYPE_CONFIDENCE["RANGE_INTERPOLATED"]
    assert GRANULARITY_CONFIDENCE["locality"] < GEOCODE_LOCATION_TYPE_CONFIDENCE["GEOMETRIC_CENTER"]
    assert GRANULARITY_CONFIDENCE["area"] < GEOCODE_LOCATION_TYPE_CONFIDENCE["APPROXIMATE"]
