"""Real Google provider (ARCHITECTURE.md §15: Geocoding for rung 2,
Places Text Search for rung 3). Never imported implicitly by anything
that must run without a key — `pipeline.run` only touches this class
when the caller explicitly asks for `--provider google`.

Indonesia bias is applied on every call (`region=id` on both endpoints
plus `components=country:ID` on Geocoding) specifically because §15/§6
call out the same-named-street-worldwide failure mode ("Jakarta" streets
exist in multiple countries) — an unbiased query is a known way to
silently geocode to the wrong country, which `quality.in_indonesia_bbox`
then has to catch after the fact. Both layers are kept: bias reduces how
often the bbox gate has to fire, the bbox gate is what actually protects
against it firing after a bias miss.

HTTP is done through an injectable `session` (anything with a
`requests.Session`-shaped `.get(url, params=..., timeout=...) -> response`
with `.json()`) so `tests/test_google_provider.py` can replay recorded
fixtures with zero network access and zero API key.
"""

from __future__ import annotations

import os
from typing import Any

from now_geocode.models import ProviderResult
from now_geocode.providers.base import ProviderConfigError, ProviderError, RetryableProviderError

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_TEXTSEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

# https://developers.google.com/maps/documentation/geocoding/requests-geocoding#Results
# location_type -> a confidence NOW! is willing to record. Text search has
# no equivalent field, so it gets one flat, deliberately-lower ceiling
# (rung 3 is a weaker signal than a real structured-address geocode).
GEOCODE_LOCATION_TYPE_CONFIDENCE = {
    "ROOFTOP": 0.95,
    "RANGE_INTERPOLATED": 0.75,
    "GEOMETRIC_CENTER": 0.55,
    "APPROXIMATE": 0.35,
}
PLACE_SEARCH_CONFIDENCE = 0.6

_RETRYABLE_STATUSES = {"OVER_QUERY_LIMIT", "UNKNOWN_ERROR"}
# INVALID_REQUEST / REQUEST_DENIED are config problems, not something a
# resumable batch run should silently retry into a rate-limit spiral.


class GoogleProvider:
    name = "google"

    def __init__(
        self,
        api_key: str | None = None,
        session: Any = None,
        region: str = "id",
        country_component: str = "ID",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        self._session = session
        self.region = region
        self.country_component = country_component
        self.timeout = timeout

    @property
    def session(self) -> Any:
        if self._session is None:
            import requests  # imported lazily so tests never need it installed as a hard runtime need beyond the declared dep

            self._session = requests.Session()
        return self._session

    def _require_key(self) -> None:
        if not self.api_key:
            raise ProviderConfigError(
                "GOOGLE_MAPS_API_KEY is not set. Supply it via the constructor or the "
                "GOOGLE_MAPS_API_KEY env var — see README.md for which Google API product "
                "and estimated cost this requires."
            )

    def geocode_address(self, address: str) -> ProviderResult | None:
        self._require_key()
        params = {
            "address": address,
            "key": self.api_key,
            "region": self.region,
            "components": f"country:{self.country_component}",
        }
        data = self._get(GEOCODE_URL, params)
        status = data.get("status")
        if status == "ZERO_RESULTS":
            return None
        if status != "OK":
            self._raise_for_status(status, data)
        result = data["results"][0]
        loc = result["geometry"]["location"]
        location_type = result["geometry"].get("location_type")
        return ProviderResult(
            lat=loc["lat"],
            lng=loc["lng"],
            formatted_address=result.get("formatted_address"),
            google_place_id=result.get("place_id"),
            location_type=location_type,
            confidence=GEOCODE_LOCATION_TYPE_CONFIDENCE.get(location_type, 0.5),
            provider=self.name,
            is_synthetic=False,
            raw=result,
        )

    def find_place(self, name: str, context: str | None) -> ProviderResult | None:
        self._require_key()
        query = name if not context else f"{name}, {context}"
        params = {"query": query, "key": self.api_key, "region": self.region}
        data = self._get(PLACES_TEXTSEARCH_URL, params)
        status = data.get("status")
        if status == "ZERO_RESULTS":
            return None
        if status != "OK":
            self._raise_for_status(status, data)
        result = data["results"][0]
        loc = result["geometry"]["location"]
        return ProviderResult(
            lat=loc["lat"],
            lng=loc["lng"],
            formatted_address=result.get("formatted_address"),
            google_place_id=result.get("place_id"),
            location_type="place_search",
            confidence=PLACE_SEARCH_CONFIDENCE,
            provider=self.name,
            is_synthetic=False,
            raw=result,
        )

    def _get(self, url: str, params: dict) -> dict:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except Exception as exc:  # network-level failure — resumable
            raise RetryableProviderError(f"network error calling {url}: {exc}") from exc
        try:
            return response.json()
        except Exception as exc:
            raise ProviderError(f"non-JSON response from {url}") from exc

    def _raise_for_status(self, status: str | None, data: dict) -> None:
        message = data.get("error_message", "")
        if status in _RETRYABLE_STATUSES:
            raise RetryableProviderError(f"{status}: {message}")
        raise ProviderConfigError(f"{status}: {message}")
