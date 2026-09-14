from pathlib import Path

import pytest

from now_geocode.models import ProviderResult, Status
from now_geocode.pipeline import iter_jsonl, run
from now_geocode.state import StateStore

REPO_ROOT = Path(__file__).resolve().parents[4]
VENUES_PATH = REPO_ROOT / "jakarta" / "content" / "extracted" / "venues.jsonl"
GEO_PATH = REPO_ROOT / "jakarta" / "content" / "extracted" / "geo.jsonl"

# These are gitignored DERIVED data (see docs/data-provenance.md), so they
# exist only on a machine that has run wp-extract. A clean CI checkout has
# neither, and the test below used to fail there with FileNotFoundError —
# it passed only where the extraction had already been run. Skipping keeps
# it valuable locally without making CI depend on data the repo does not
# and should not carry.
requires_extracted_data = pytest.mark.skipif(
    not (VENUES_PATH.exists() and GEO_PATH.exists()),
    reason="jakarta/content/extracted/*.jsonl absent (gitignored derived data); run wp-extract first",
)


class CountingStubProvider:
    """Answers rung 2/3 deterministically and counts real calls made,
    so tests can assert the state cache actually prevents re-billing."""

    def __init__(self):
        self.address_calls = 0
        self.place_calls = 0

    def geocode_address(self, address):
        self.address_calls += 1
        return ProviderResult(
            lat=-6.2, lng=106.8, formatted_address=address, google_place_id="p",
            location_type="ROOFTOP", confidence=0.9, provider="stub",
        )

    def find_place(self, name, context):
        self.place_calls += 1
        return None


def test_no_provider_resolves_only_free_seed_zero_fabrication():
    venues = [{"wp_id": 1, "name": "Needs Geocoding", "status": "publish", "address": "Somewhere"}]
    geo = [
        {"source": "mappress", "wp_id": 2, "map_id": 1, "title": "Free Seed Point",
         "address": None, "lat": -8.5, "lng": 115.2}
    ]
    places, stats = run(venues, geo, provider=None)
    by_name = {p.name: p for p in places}
    assert by_name["Free Seed Point"].status == Status.RESOLVED
    assert by_name["Needs Geocoding"].status == Status.UNRESOLVED
    assert by_name["Needs Geocoding"].lat is None  # never fabricated


def test_every_place_gets_an_area_term_even_when_unresolved():
    venues = [{"wp_id": 1, "name": "Unresolvable Thing", "status": "publish", "city": "Ubud"}]
    places, _ = run(venues, [], provider=None)
    assert places[0].status == Status.UNRESOLVED
    assert places[0].area_term == "ubud"


def test_resumability_second_run_hits_cache_not_provider(tmp_path):
    venues = [{"wp_id": 1, "name": "Cached Venue", "status": "publish", "address": "Some Address"}]
    provider = CountingStubProvider()
    state_path = tmp_path / "state.jsonl"

    state1 = StateStore(state_path)
    run(venues, [], provider=provider, state=state1)
    assert provider.address_calls == 1

    state2 = StateStore(state_path)  # fresh process resuming the batch
    places2, stats2 = run(venues, [], provider=provider, state=state2)
    assert provider.address_calls == 1  # not called again
    assert stats2.resolved_from_cache == 1
    assert places2[0].status == Status.RESOLVED


def test_duplicate_centroid_flagged_across_distinct_provider_results():
    venues = [
        {"wp_id": 1, "name": "Place One", "status": "publish", "address": "Addr One"},
        {"wp_id": 2, "name": "Place Two", "status": "publish", "address": "Addr Two"},
    ]

    class SameSpotProvider:
        def geocode_address(self, address):
            return ProviderResult(
                lat=-6.2, lng=106.8, formatted_address=address, google_place_id=None,
                location_type="GEOMETRIC_CENTER", confidence=0.55, provider="stub",
            )

        def find_place(self, name, context):
            return None

    places, stats = run(venues, [], provider=SameSpotProvider())
    assert all("duplicate_centroid" in p.flags for p in places)
    assert stats.flagged.get("duplicate_centroid") == 2


def test_slugs_are_unique_on_name_collision():
    venues = [
        {"wp_id": 1, "name": "Same Name", "status": "publish", "city": "Ubud"},
        {"wp_id": 2, "name": "Same Name (Different Branch)", "status": "publish", "city": "Sanur"},
    ]
    # Force a real slug collision by using identical names but distinct
    # addresses so dedupe.py does not merge them into one candidate.
    venues = [
        {"wp_id": 1, "name": "Same Name", "status": "publish", "address": "Addr A", "city": "Ubud"},
        {"wp_id": 2, "name": "Same Name", "status": "publish", "address": "Addr B", "city": "Sanur"},
    ]
    places, _ = run(venues, [], provider=None)
    slugs = [p.slug for p in places]
    assert len(slugs) == len(set(slugs))


@requires_extracted_data
def test_real_extracted_files_end_to_end_zero_cost():
    """Smoke test against the actual E1.1 extraction output (frozen
    contract, not a fixture this package owns) — proves the free seed
    ingests before anything else and nothing is fabricated."""

    venue_rows = iter_jsonl(VENUES_PATH)
    geo_rows = iter_jsonl(GEO_PATH)
    places, stats = run(venue_rows, geo_rows, provider=None)

    assert stats.total_candidates > 150  # real corpus, not a stub
    resolved = stats.by_status.get("resolved", 0)
    assert resolved >= 60  # the free geo.jsonl seed, ~62 on the real data
    assert stats.by_status.get("rejected", 0) == 0  # no known bad points in the current corpus
    assert stats.by_source.get("address_geocode", 0) == 0  # no provider configured -> never called
    assert stats.by_source.get("name_place_search", 0) == 0
    assert all(p.area_term for p in places)  # 100% area-term coverage, resolved or not
    assert all(p.lat is None or p.status != Status.UNRESOLVED for p in places)  # never a coordinate on an unresolved row
