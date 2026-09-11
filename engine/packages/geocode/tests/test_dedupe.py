from now_geocode.dedupe import MergeReport, build_candidates
from now_geocode.models import SourceKind


def test_merges_venue_and_geo_row_by_normalized_name():
    venues = [
        {
            "wp_id": 1,
            "name": "Potato Head Beach Club",
            "status": "publish",
            "address": "Jl. Petitenget",
            "city": "Seminyak",
            "province": "Bali",
            "country": "Indonesia",
        }
    ]
    geo = [
        {
            "source": "mappress",
            "wp_id": 999,
            "map_id": 5,
            "title": "Potato Head Beach Club",
            "address": None,
            "lat": -8.68,
            "lng": 115.15,
        }
    ]
    report = MergeReport()
    candidates = build_candidates(venues, geo, report)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.existing_lat == -8.68
    assert c.address == "Jl. Petitenget"  # kept from the venue row even though the free seed had no address
    assert {r.kind for r in c.source_refs} == {SourceKind.TRIBE_VENUE, SourceKind.MAPPRESS}
    assert len(report.merges) == 1


def test_distinct_names_stay_distinct():
    venues = [
        {"wp_id": 1, "name": "Warung Bali", "status": "publish", "city": "Ubud"},
        {"wp_id": 2, "name": "Warung Jakarta", "status": "publish", "city": "Menteng"},
    ]
    candidates = build_candidates(venues, [])
    assert len(candidates) == 2


def test_draft_venue_kept_and_flagged_not_dropped():
    venues = [{"wp_id": 1, "name": "Unpublished Spot", "status": "draft"}]
    report = MergeReport()
    candidates = build_candidates(venues, [], report)
    assert len(candidates) == 1
    assert candidates[0].status_hint == "draft"
    assert report.dropped_draft_venues == 1


def test_conflicting_city_on_merge_is_flagged():
    venues = [
        {"wp_id": 1, "name": "Ambiguous Name", "status": "publish", "city": "Seminyak"},
        {"wp_id": 2, "name": "Ambiguous Name", "status": "publish", "city": "Menteng"},
    ]
    report = MergeReport()
    build_candidates(venues, [], report)
    assert len(report.conflicts) == 1


def test_deterministic_ordering_independent_of_input_order():
    venues_a = [
        {"wp_id": 2, "name": "Bravo", "status": "publish"},
        {"wp_id": 1, "name": "Alpha", "status": "publish"},
    ]
    venues_b = list(reversed(venues_a))
    keys_a = [c.key for c in build_candidates(venues_a, [])]
    keys_b = [c.key for c in build_candidates(venues_b, [])]
    assert keys_a == keys_b


def test_geo_row_with_no_matching_name_becomes_its_own_candidate():
    geo = [
        {
            "source": "google_map",
            "wp_id": 42,
            "map_id": None,
            "title": "Jakarta International Stadium (JIS)",
            "address": "Papanggo, North Jakarta City, Jakarta, Indonesia",
            "lat": -6.12512,
            "lng": 106.86003,
            "place_id": "ChIJ_test",
        }
    ]
    candidates = build_candidates([], geo)
    assert len(candidates) == 1
    assert candidates[0].existing_google_place_id == "ChIJ_test"
