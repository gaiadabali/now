"""Row 2 Nearby -- radius is a hard filter, degrading to same-area (then
district/city) when geo is sparse. Exercised against
`now_filters.synthetic` places (F50/F27: real places have 0/177
coordinates and 0/177 `status='active']` today -- see the package README).
"""

from __future__ import annotations

from now_filters.models import Candidate
from now_filters.synthetic import SYNTH_PLACES_TABLE, SyntheticPlace, create_synthetic_places_table

from now_rails.row2_nearby import compute_row2
from now_rails.subject import ArticleSubject

SUBJECT_PLACE_ID = 800_001
SUBJECT_LAT, SUBJECT_LNG = -6.2200, 106.8000


def _subject(place: Candidate | None, primary_type: str | None = "stay") -> ArticleSubject:
    return ArticleSubject(
        article_id=999_002, primary_type=primary_type, format=None, series_key=None, published_at=None,
        title="Test Subject Hotel", status="published", place=place,
    )


def test_row2_hard_radius_excludes_far_places(city_conn, relations):
    rows = [
        SyntheticPlace(id=SUBJECT_PLACE_ID, type="stay", status="active", area_term="senopati", lat=SUBJECT_LAT, lng=SUBJECT_LNG),
        SyntheticPlace(id=800_002, type="do", status="active", area_term="senopati", lat=SUBJECT_LAT + 0.001, lng=SUBJECT_LNG + 0.001, org_id="org-a"),  # ~150m -- within 2km
        SyntheticPlace(id=800_003, type="do", status="active", area_term="senopati", lat=SUBJECT_LAT + 0.5, lng=SUBJECT_LNG + 0.5, org_id="org-b"),  # ~70km -- outside even the widest rung
        SyntheticPlace(id=800_004, type="stay", status="active", area_term="senopati", lat=SUBJECT_LAT, lng=SUBJECT_LNG, org_id="org-c"),  # competitor, right next door -- must never appear
    ]
    create_synthetic_places_table(city_conn, rows)

    subject_place = Candidate(entity_type="place", entity_id=SUBJECT_PLACE_ID, type="stay", area_term="senopati", lat=SUBJECT_LAT, lng=SUBJECT_LNG)
    subject = _subject(subject_place, primary_type="stay")

    result = compute_row2(city_conn, subject, relations, k=6, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    returned_ids = {i.entity_id for i in result.items}
    assert 800_002 in returned_ids, "a genuinely nearby, non-competitor place must appear"
    assert 800_004 not in returned_ids, "same-type competitor must never appear even when closest"
    assert 800_003 not in returned_ids or result.rung_name == "editorial_fallback", (
        "the 70km-away place should only appear if the ladder was forced to the widest, area-dropping rung"
    )


def test_row2_never_empty_when_any_eligible_place_exists_anywhere(city_conn, relations):
    rows = [
        SyntheticPlace(id=SUBJECT_PLACE_ID, type="stay", status="active", area_term="senopati", lat=SUBJECT_LAT, lng=SUBJECT_LNG),
        # No coordinates at all, far area -- must still surface once the
        # ladder drops to a city-wide, no-radius rung.
        SyntheticPlace(id=800_005, type="do", status="active", area_term="kemang", lat=None, lng=None, org_id="org-z"),
    ]
    create_synthetic_places_table(city_conn, rows)

    subject_place = Candidate(entity_type="place", entity_id=SUBJECT_PLACE_ID, type="stay", area_term="senopati", lat=SUBJECT_LAT, lng=SUBJECT_LNG)
    subject = _subject(subject_place, primary_type="stay")

    result = compute_row2(city_conn, subject, relations, k=6, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    assert len(result.items) == 1
    assert result.items[0].entity_id == 800_005
    assert result.rung_name in ("area_to_district", "district_to_city", "drop_freshness", "editorial_fallback", "drop_open_now", "widen_radius_15km", "widen_radius_5km")


def test_row2_unknown_subject_type_fails_closed(city_conn, relations):
    create_synthetic_places_table(city_conn, [SyntheticPlace(id=800_006, type="do", status="active", area_term="senopati")])
    subject = _subject(place=None, primary_type=None)

    result = compute_row2(city_conn, subject, relations, k=6, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    assert result.items == []
    assert result.unvalidated_reason is not None and "F50" in result.unvalidated_reason
