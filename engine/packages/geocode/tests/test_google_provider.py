"""Unit tests for GoogleProvider, replayed against recorded fixture JSON
under tests/fixtures/google/ — zero network access, zero API key. The
fake session records every call so tests can assert on the Indonesia
bias params (region/components) the provider is required to send."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from now_geocode.providers.base import ProviderConfigError, RetryableProviderError
from now_geocode.providers.google import GoogleProvider

FIXTURES = Path(__file__).parent / "fixtures" / "google"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Records every .get() call; returns the fixture queued for that URL."""

    def __init__(self, queue: dict[str, dict]):
        self.queue = queue
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(self.queue[url])


def make_provider(fixture_by_url: dict[str, str]) -> tuple[GoogleProvider, FakeSession]:
    session = FakeSession({url: _load(name) for url, name in fixture_by_url.items()})
    provider = GoogleProvider(api_key="test-key", session=session)
    return provider, session


def test_geocode_address_ok_rooftop():
    from now_geocode.providers.google import GEOCODE_URL

    provider, session = make_provider({GEOCODE_URL: "geocode_ok_rooftop.json"})
    result = provider.geocode_address("Jl. Kemang Raya No. 1, South Jakarta")
    assert result is not None
    assert (result.lat, result.lng) == (-6.2605, 106.8140)
    assert result.google_place_id == "ChIJ_fixture_rooftop_001"
    assert result.location_type == "ROOFTOP"
    assert result.confidence == 0.95
    assert result.is_synthetic is False


def test_geocode_address_ok_approximate_gets_lower_confidence():
    from now_geocode.providers.google import GEOCODE_URL

    provider, _ = make_provider({GEOCODE_URL: "geocode_ok_approximate.json"})
    result = provider.geocode_address("Ubud")
    assert result.location_type == "APPROXIMATE"
    assert result.confidence == 0.35


def test_geocode_zero_results_returns_none_not_an_error():
    from now_geocode.providers.google import GEOCODE_URL

    provider, _ = make_provider({GEOCODE_URL: "geocode_zero_results.json"})
    assert provider.geocode_address("Nonexistent Address 12345") is None


def test_geocode_over_query_limit_is_retryable():
    from now_geocode.providers.google import GEOCODE_URL

    provider, _ = make_provider({GEOCODE_URL: "geocode_over_query_limit.json"})
    with pytest.raises(RetryableProviderError):
        provider.geocode_address("Any Address")


def test_geocode_request_denied_is_config_error_not_retryable():
    from now_geocode.providers.google import GEOCODE_URL

    provider, _ = make_provider({GEOCODE_URL: "geocode_request_denied.json"})
    with pytest.raises(ProviderConfigError):
        provider.geocode_address("Any Address")


def test_geocode_sends_indonesia_bias_params():
    from now_geocode.providers.google import GEOCODE_URL

    provider, session = make_provider({GEOCODE_URL: "geocode_ok_rooftop.json"})
    provider.geocode_address("Jl. Sudirman")
    params = session.calls[0]["params"]
    assert params["region"] == "id"
    assert params["components"] == "country:ID"


def test_find_place_ok():
    from now_geocode.providers.google import PLACES_TEXTSEARCH_URL

    provider, session = make_provider({PLACES_TEXTSEARCH_URL: "textsearch_ok.json"})
    result = provider.find_place("Potato Head Beach Club", "Seminyak, Bali")
    assert result is not None
    assert (result.lat, result.lng) == (-8.6801, 115.1553)
    assert result.location_type == "place_search"
    assert result.confidence == 0.6
    query_sent = session.calls[0]["params"]["query"]
    assert "Potato Head Beach Club" in query_sent
    assert "Seminyak" in query_sent


def test_find_place_zero_results():
    from now_geocode.providers.google import PLACES_TEXTSEARCH_URL

    provider, _ = make_provider({PLACES_TEXTSEARCH_URL: "textsearch_zero_results.json"})
    assert provider.find_place("Nothing Here", None) is None


def test_missing_api_key_raises_config_error_before_any_call():
    provider = GoogleProvider(api_key=None, session=object())
    with pytest.raises(ProviderConfigError):
        provider.geocode_address("Anywhere")


def test_env_var_supplies_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "from-env")
    provider = GoogleProvider()
    assert provider.api_key == "from-env"


def test_network_error_is_retryable():
    class ExplodingSession:
        def get(self, *a, **k):
            raise ConnectionError("boom")

    provider = GoogleProvider(api_key="k", session=ExplodingSession())
    with pytest.raises(RetryableProviderError):
        provider.geocode_address("Anywhere")
