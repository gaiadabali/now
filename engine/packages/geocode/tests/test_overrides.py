"""Rung 0 (human-verified overrides) and the rung-3 challenge."""

from __future__ import annotations

import json

import pytest

from now_geocode.ladder import VENUE_SPECIFICITY, resolve_candidate, specificity
from now_geocode.models import PlaceCandidate, ProviderResult, Rung, Status
from now_geocode.overrides import OverrideError, load_overrides
from now_geocode.pipeline import run
from now_geocode.state import StateStore


def candidate(**kw) -> PlaceCandidate:
    base = dict(
        key="k1", name="A Venue", address=None, city=None, province=None, country=None,
        existing_lat=None, existing_lng=None, existing_google_place_id=None,
    )
    base.update(kw)
    return PlaceCandidate(**base)


def write(tmp_path, *rows):
    p = tmp_path / "ov.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def entry(**kw):
    base = {"place_key": "k1", "name": "A Venue", "action": "override",
            "lat": -8.68, "lng": 115.15, "confidence": 0.9,
            "sources": ["https://example.org/x"], "note": "checked"}
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def test_missing_file_is_not_an_error(tmp_path):
    assert load_overrides(tmp_path / "nope.jsonl") == {}
    assert load_overrides(None) == {}


def test_doc_header_row_is_skipped(tmp_path):
    p = write(tmp_path, {"_comment": "docs", "_schema": {}}, entry())
    assert list(load_overrides(p)) == ["k1"]


def test_override_without_a_source_is_rejected(tmp_path):
    """An uncited coordinate cannot be told apart from a fabricated one."""
    p = write(tmp_path, entry(sources=[]))
    with pytest.raises(OverrideError, match="source"):
        load_overrides(p)


def test_override_without_a_coordinate_is_rejected(tmp_path):
    p = write(tmp_path, entry(lat=None))
    with pytest.raises(OverrideError, match="coordinate"):
        load_overrides(p)


def test_unknown_action_is_rejected(tmp_path):
    p = write(tmp_path, entry(action="delete"))
    with pytest.raises(OverrideError, match="action"):
        load_overrides(p)


def test_duplicate_place_key_is_rejected(tmp_path):
    p = write(tmp_path, entry(), entry(note="again"))
    with pytest.raises(OverrideError, match="duplicate"):
        load_overrides(p)


def test_merge_into_without_a_target_is_rejected(tmp_path):
    p = write(tmp_path, entry(action="merge_into", lat=None, lng=None))
    with pytest.raises(OverrideError, match="merge_into_place_key"):
        load_overrides(p)


def test_malformed_json_fails_loudly(tmp_path):
    p = tmp_path / "ov.jsonl"
    p.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(OverrideError):
        load_overrides(p)


def test_the_real_jakarta_overrides_file_loads():
    """The shipped file must stay valid — it is hand-edited."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[4]
    ov = load_overrides(repo / "jakarta" / "site" / "place-overrides.jsonl")
    assert len(ov) == 15
    assert all(o.sources for o in ov.values() if o.action == "override")


# --------------------------------------------------------------------------
# Rung 0 beats everything below it
# --------------------------------------------------------------------------


class StubProvider:
    name = "stub"

    def __init__(self, address_result=None, place_result=None):
        self.address_calls = 0
        self.place_calls = 0
        self._a = address_result
        self._p = place_result

    def geocode_address(self, address):
        self.address_calls += 1
        return self._a

    def find_place(self, name, context):
        self.place_calls += 1
        return self._p


def result(lat=-8.6, lng=115.1, location_type="osm_poi", confidence=0.9):
    return ProviderResult(
        lat=lat, lng=lng, formatted_address="x", google_place_id=None,
        location_type=location_type, confidence=confidence, provider="stub",
    )


def test_override_wins_over_an_existing_coordinate(tmp_path):
    """Rung 0 sits above rung 1 deliberately: the file exists because some
    free-seed points are wrong."""
    ov = load_overrides(write(tmp_path, entry(lat=-8.11, lng=115.22)))
    c = candidate(existing_lat=-8.99, existing_lng=115.99)

    outcome = resolve_candidate(c, None, overrides=ov)

    assert outcome.rung is Rung.MANUAL_OVERRIDE
    assert (outcome.lat, outcome.lng) == (-8.11, 115.22)
    assert outcome.location_type == "manual_override"


def test_override_makes_no_provider_call(tmp_path):
    ov = load_overrides(write(tmp_path, entry()))
    provider = StubProvider(address_result=result())
    resolve_candidate(candidate(address="Somewhere"), provider, overrides=ov)
    assert provider.address_calls == 0 and provider.place_calls == 0


def test_override_outside_indonesia_is_still_bbox_checked(tmp_path):
    """A human can typo a sign. The bbox gate still applies."""
    ov = load_overrides(write(tmp_path, entry(lat=51.5074, lng=-0.1278)))
    outcome = resolve_candidate(candidate(), None, overrides=ov)
    assert outcome.status is Status.REJECTED
    assert "out_of_bounds" in outcome.flags


def test_drop_removes_the_coordinate_but_keeps_the_row(tmp_path):
    ov = load_overrides(write(tmp_path, entry(action="drop", lat=None, lng=None, sources=[])))
    outcome = resolve_candidate(candidate(existing_lat=-8.9, existing_lng=115.9), None, overrides=ov)
    assert outcome.status is Status.UNRESOLVED
    assert outcome.lat is None
    assert "manual override" in outcome.review_reason


def test_merge_into_rejects_and_names_the_survivor(tmp_path):
    ov = load_overrides(write(tmp_path, entry(
        action="merge_into", lat=None, lng=None, sources=[], merge_into_place_key="k2")))
    outcome = resolve_candidate(candidate(), None, overrides=ov)
    assert outcome.status is Status.REJECTED
    assert "merged_duplicate" in outcome.flags
    assert "k2" in outcome.review_reason


def test_overrides_bypass_the_state_cache(tmp_path):
    """Editing place-overrides.jsonl must take effect without anyone
    knowing they also had to delete a .state.jsonl."""
    venues = [{"wp_id": 1, "name": "A Venue", "status": "publish", "address": "Somewhere"}]
    state_path = tmp_path / "s.jsonl"

    places, _ = run(venues, [], provider=StubProvider(address_result=result()),
                    state=StateStore(state_path))
    key = places[0].place_key

    ov = load_overrides(write(tmp_path, entry(place_key=key, lat=-8.11, lng=115.22)))
    places2, _ = run(venues, [], provider=StubProvider(address_result=result()),
                     state=StateStore(state_path), overrides=ov)

    assert (places2[0].lat, places2[0].lng) == (-8.11, 115.22)
    assert places2[0].source is Rung.MANUAL_OVERRIDE


# --------------------------------------------------------------------------
# Rung 3 challenges a coarse rung 2
# --------------------------------------------------------------------------


def test_venue_level_rung2_is_not_challenged():
    """No extra call when rung 2 already answered at venue level."""
    provider = StubProvider(address_result=result(location_type="osm_poi"))
    resolve_candidate(candidate(address="x"), provider)
    assert provider.place_calls == 0


def test_street_level_rung2_is_challenged():
    provider = StubProvider(address_result=result(location_type="osm_street", confidence=0.65))
    resolve_candidate(candidate(address="x"), provider)
    assert provider.place_calls == 1


def test_name_hit_beats_a_street_hit_despite_lower_confidence():
    """The crux. A rung-3 OSM name hit is capped at 0.50 while a street
    hit scores 0.65, so ranking by confidence keeps the street — the
    inversion that left 33 rows on street points."""
    provider = StubProvider(
        address_result=result(location_type="osm_street", confidence=0.65),
        place_result=result(lat=-8.7, lng=115.2, location_type="osm_poi", confidence=0.50),
    )
    outcome = resolve_candidate(candidate(address="x"), provider)
    assert outcome.rung is Rung.NAME_PLACE_SEARCH
    assert (outcome.lat, outcome.lng) == (-8.7, 115.2)


def test_street_hit_is_kept_when_the_name_search_finds_nothing():
    provider = StubProvider(
        address_result=result(location_type="osm_street", confidence=0.65), place_result=None)
    outcome = resolve_candidate(candidate(address="x"), provider)
    assert outcome.rung is Rung.ADDRESS_GEOCODE


def test_a_rejected_challenge_never_beats_a_resolved_street_hit():
    """A region centroid below the venue floor must not displace a real
    street-level answer."""
    provider = StubProvider(
        address_result=result(location_type="osm_street", confidence=0.65),
        place_result=result(location_type="osm_area", confidence=0.30),
    )
    outcome = resolve_candidate(candidate(address="x"), provider)
    assert outcome.rung is Rung.ADDRESS_GEOCODE
    assert outcome.status is Status.RESOLVED


def test_challenge_can_be_disabled():
    provider = StubProvider(address_result=result(location_type="osm_street", confidence=0.65))
    resolve_candidate(candidate(address="x"), provider, challenge_coarse_rung2=False)
    assert provider.place_calls == 0


def test_retryable_challenge_does_not_discard_the_rung2_result():
    from now_geocode.providers.base import RetryableProviderError

    class P(StubProvider):
        def find_place(self, name, context):
            raise RetryableProviderError("429")

    provider = P(address_result=result(location_type="osm_street", confidence=0.65))
    outcome = resolve_candidate(candidate(address="x"), provider)
    assert outcome.rung is Rung.ADDRESS_GEOCODE
    assert outcome.retryable_error is None


@pytest.mark.parametrize(
    "location_type,expected_at_least_venue",
    [("osm_poi", True), ("osm_building", True), ("ROOFTOP", True), ("place_search", True),
     ("mappress_poi", True), ("manual_override", True),
     ("osm_street", False), ("GEOMETRIC_CENTER", False), ("osm_area", False),
     ("APPROXIMATE", False), ("osm_locality", False)],
)
def test_specificity_ranking(location_type, expected_at_least_venue):
    assert (specificity(location_type) >= VENUE_SPECIFICITY) is expected_at_least_venue


def test_unknown_location_type_is_not_trusted_as_a_venue():
    assert specificity("something_new") < VENUE_SPECIFICITY
    assert specificity(None) < VENUE_SPECIFICITY
