"""End-to-end: a real OSM provider driven through the real ladder and
the real pipeline, with only the HTTP session faked.

test_osm_provider.py proves the provider parses correctly in isolation;
these prove the pieces actually compose — that `ladder.py` needed no
changes to accept an OSM provider, that the quality gates still fire on
OSM-shaped results, and that a chained run produces the same
`geocoded_places.jsonl` contract as a Google run."""

from __future__ import annotations

import json
from pathlib import Path

from now_geocode.models import ProviderResult, Rung, Status
from now_geocode.pipeline import run
from now_geocode.providers.chain import ChainProvider
from now_geocode.providers.osm import NominatimProvider, PhotonProvider
from now_geocode.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "osm"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class RoutingSession:
    """Returns a different fixture depending on the query, so one
    session can serve a multi-candidate pipeline run."""

    def __init__(self, by_query_substring: dict, default=None):
        self.by_query_substring = by_query_substring
        self.default = default if default is not None else []
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params})
        query = (params or {}).get("q", "")
        payload = self.default
        for needle, fixture in self.by_query_substring.items():
            if needle.lower() in query.lower():
                payload = fixture
                break

        class R:
            status_code = 200

            def json(self_inner):
                return payload

        return R()


def _nominatim(session) -> NominatimProvider:
    return NominatimProvider(session=session, min_interval_s=0.0)


def test_osm_provider_resolves_a_place_through_the_real_ladder():
    session = RoutingSession({"Grand Indonesia": _load("nominatim_address_poi.json")})
    venues = [{"wp_id": 1, "name": "Grand Indonesia", "status": "publish",
               "address": "Grand Indonesia Shopping Town", "city": "Jakarta"}]

    places, stats = run(venues, [], provider=_nominatim(session))

    place = places[0]
    assert place.status == Status.RESOLVED
    assert place.source == Rung.ADDRESS_GEOCODE
    assert (place.lat, place.lng) == (-6.1957601, 106.8214547)
    assert place.location_type == "osm_poi"
    assert place.google_place_id is None  # OSM run leaves the Google field empty


def test_free_seed_still_wins_over_a_provider_call():
    """Rung 1 is free and must short-circuit before any HTTP call."""
    session = RoutingSession({}, default=_load("nominatim_address_poi.json"))
    geo = [{"source": "mappress", "wp_id": 2, "map_id": 1, "title": "Already Known",
            "address": None, "lat": -8.5, "lng": 115.2}]

    places, _ = run([], geo, provider=_nominatim(session))

    assert places[0].source == Rung.EXISTING_COORDINATES
    assert session.calls == [], "rung 1 must not touch the network"


def test_wrong_thing_result_lands_in_review_not_in_the_deliverable():
    """The whole reason name_agrees exists, proven end to end: OSM
    answers a venue-name search with the enclosing suburb, and the row
    comes out unresolved with no coordinate rather than resolved at a
    real-looking but wrong point."""
    session = RoutingSession({"Potato Head": _load("nominatim_name_wrong_thing.json")})
    venues = [{"wp_id": 1, "name": "Potato Head Beach Club", "status": "publish",
               "city": "Seminyak", "province": "Bali"}]

    places, _ = run(venues, [], provider=_nominatim(session))

    assert places[0].status == Status.UNRESOLVED
    assert places[0].lat is None
    assert places[0].source == Rung.UNRESOLVED


def test_out_of_indonesia_osm_result_is_rejected_by_the_quality_gate():
    """A geocoder returning a real point in the wrong hemisphere must be
    caught by the existing bbox gate — the OSM path gets the same
    protection the Google path does."""
    london = [{"place_id": 1, "osm_type": "node", "osm_id": 2, "lat": "51.5074", "lon": "-0.1278",
               "class": "amenity", "type": "restaurant", "name": "Jakarta Restaurant",
               "display_name": "Jakarta Restaurant, London, United Kingdom"}]
    session = RoutingSession({"Jakarta Restaurant": london})
    venues = [{"wp_id": 1, "name": "Jakarta Restaurant", "status": "publish",
               "address": "Jakarta Street"}]

    places, _ = run(venues, [], provider=_nominatim(session))

    assert places[0].status == Status.REJECTED
    assert "out_of_bounds" in places[0].flags


def test_state_cache_prevents_a_second_osm_call(tmp_path):
    session = RoutingSession({"Grand Indonesia": _load("nominatim_address_poi.json")})
    venues = [{"wp_id": 1, "name": "Grand Indonesia", "status": "publish",
               "address": "Grand Indonesia Shopping Town"}]
    state_path = tmp_path / "s.jsonl"

    run(venues, [], provider=_nominatim(session), state=StateStore(state_path))
    calls_after_first = len(session.calls)
    run(venues, [], provider=_nominatim(session), state=StateStore(state_path))

    assert calls_after_first == 1
    assert len(session.calls) == 1, "a cached final answer must not be re-fetched"


def test_chain_falls_through_to_a_second_provider_in_a_real_run():
    """Photon misses, Nominatim answers — and the pipeline neither knows
    nor cares which one did it."""
    photon = PhotonProvider(
        session=RoutingSession({}, default=_load("photon_zero_results.json")), min_interval_s=0.0
    )
    nominatim = _nominatim(RoutingSession({"Grand Indonesia": _load("nominatim_address_poi.json")}))
    chain = ChainProvider([photon, nominatim])

    venues = [{"wp_id": 1, "name": "Grand Indonesia", "status": "publish",
               "address": "Grand Indonesia Shopping Town"}]
    places, _ = run(venues, [], provider=chain)

    assert places[0].status == Status.RESOLVED
    assert places[0].location_type == "osm_poi"


def test_chained_output_matches_the_google_run_contract():
    """A free run must emit exactly the same row shape E2.3/E1.8 already
    consume — swapping the provider is not allowed to change the
    contract."""
    session = RoutingSession({"Grand Indonesia": _load("nominatim_address_poi.json")})
    venues = [{"wp_id": 1, "name": "Grand Indonesia", "status": "publish",
               "address": "Grand Indonesia Shopping Town"}]

    osm_places, _ = run(venues, [], provider=_nominatim(session))

    class GoogleLike:
        def geocode_address(self, address):
            return ProviderResult(
                lat=-6.2605, lng=106.8140, formatted_address=address,
                google_place_id="ChIJ_x", location_type="ROOFTOP", confidence=0.95,
                provider="google",
            )

        def find_place(self, name, context):
            return None

    google_places, _ = run(venues, [], provider=GoogleLike())

    assert set(osm_places[0].to_json().keys()) == set(google_places[0].to_json().keys())
    assert osm_places[0].to_json()["status"] == google_places[0].to_json()["status"]
