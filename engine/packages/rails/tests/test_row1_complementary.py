"""Row 1 Complementary -- exercised against `now_filters.synthetic`
places (F50/F27: real places carry no usable type/status/price/vibe
variety -- see `now_rails` README "What is validated on real data").
"""

from __future__ import annotations

from now_filters.models import Candidate
from now_filters.synthetic import SYNTH_PLACES_TABLE, SyntheticPlace, create_synthetic_places_table, generate_synthetic_place_rows

from now_rails.row1_complementary import compute_row1
from now_rails.subject import ArticleSubject

SUBJECT_PLACE_ID = 700_001


def _subject(place: Candidate | None, primary_type: str | None = "stay") -> ArticleSubject:
    return ArticleSubject(
        article_id=999_001,
        primary_type=primary_type,
        format=None,
        series_key=None,
        published_at=None,
        title="Test Subject Hotel",
        status="published",
        place=place,
    )


def test_row1_pool_is_complements_only_and_excludes_subject_type(city_conn, relations):
    rows = [
        SyntheticPlace(id=SUBJECT_PLACE_ID, type="stay", status="active", area_term="senopati"),
        SyntheticPlace(id=700_002, type="eat", status="active", area_term="senopati", org_id="org-a"),
        SyntheticPlace(id=700_003, type="drink", status="active", area_term="senopati", org_id="org-b"),
        SyntheticPlace(id=700_004, type="wellness", status="active", area_term="senopati", org_id="org-c"),
        SyntheticPlace(id=700_005, type="stay", status="active", area_term="senopati", org_id="org-d"),  # competitor -- must never appear
        SyntheticPlace(id=700_006, type="shop", status="active", area_term="senopati", org_id="org-e"),  # NOT in stay's complements -- must never appear
    ]
    create_synthetic_places_table(city_conn, rows)

    subject_place = Candidate(entity_type="place", entity_id=SUBJECT_PLACE_ID, type="stay", area_term="senopati")
    subject = _subject(subject_place, primary_type="stay")

    # k=1 -> ladder_target(1, 40) == 3, exactly the size of the real
    # complements pool below -- the ladder is satisfied on rung 1 without
    # ever reaching the editorial-fallback rung (which would legitimately
    # widen past the complements whitelist and let `shop` back in).
    result = compute_row1(city_conn, subject, relations, k=1, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    assert result.subject_type == "stay"
    assert result.rung_name == "strict"
    assert result.pool_size == 3, "pool must be exactly the 3 real complements -- competitor and non-complement excluded before diversify ever runs"
    returned_ids = {i.entity_id for i in result.items}
    assert returned_ids.issubset({700_002, 700_003, 700_004})
    assert SUBJECT_PLACE_ID not in returned_ids, "self must never appear"
    assert 700_005 not in returned_ids, "same-type competitor must never appear"
    assert 700_006 not in returned_ids, "shop is not in stay's complements -- must not appear as Row 1 pool"


def test_row1_rung_stays_strict_when_area_pool_is_large_enough(city_conn, relations):
    # k=6, rerank_pool=40 -> ladder_target = min(40, max(18, 6)) = 18: give
    # the same area >=18 eligible complements so the ladder is satisfied
    # on rung 1 without ever widening area/dropping the complements list.
    rows = [SyntheticPlace(id=SUBJECT_PLACE_ID, type="stay", status="active", area_term="senopati")]
    for i in range(20):
        rows.append(
            SyntheticPlace(id=703_000 + i, type="eat", status="active", area_term="senopati", org_id=f"org-{i}")
        )
    create_synthetic_places_table(city_conn, rows)

    subject_place = Candidate(entity_type="place", entity_id=SUBJECT_PLACE_ID, type="stay", area_term="senopati")
    subject = _subject(subject_place, primary_type="stay")

    result = compute_row1(city_conn, subject, relations, k=6, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    assert result.rung_name == "strict"
    # run_ladder truncates to its own slots_needed (ladder_target(6,40)=18)
    # once that many candidates are found -- 20 available, 18 kept.
    assert result.pool_size == 18
    # max 2 per area (all 20 share "senopati") -- diversity caps the FINAL
    # slots even though the pool itself was plenty large.
    assert len(result.items) <= 2


def test_row1_max_one_per_org(city_conn, relations):
    rows = [SyntheticPlace(id=SUBJECT_PLACE_ID, type="stay", status="active", area_term="senopati")]
    # Ten "eat" places across ten distinct areas (so the area cap doesn't
    # also bind) but only 2 distinct orgs -- max_per_org=1 must cap each
    # org at one slot even though there is plenty of relevant pool left.
    areas = ["senopati", "kemang", "scbd"] * 4
    for i in range(10):
        rows.append(
            SyntheticPlace(
                id=701_000 + i, type="eat", status="active", area_term=areas[i % len(areas)], org_id=f"org-{i % 2}"
            )
        )
    create_synthetic_places_table(city_conn, rows)

    subject_place = Candidate(entity_type="place", entity_id=SUBJECT_PLACE_ID, type="stay", area_term="senopati")
    subject = _subject(subject_place, primary_type="stay")

    result = compute_row1(city_conn, subject, relations, k=10, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    org_by_id = {701_000 + i: f"org-{i % 2}" for i in range(10)}
    orgs_seen = [org_by_id[i.entity_id] for i in result.items]
    assert len(orgs_seen) == len(set(orgs_seen)), f"max 1 per org violated: {orgs_seen}"
    assert len(result.items) <= 2  # only 2 distinct orgs exist in the pool


def test_row1_falls_back_to_editorial_when_pool_is_tiny_everywhere(city_conn, relations):
    rows = [
        SyntheticPlace(id=SUBJECT_PLACE_ID, type="stay", status="active", area_term="scbd"),
        # Only one non-competitor place exists anywhere in the whole
        # synthetic city -- no rung, however permissive, can ever satisfy
        # a target > 1, so the ladder must walk all the way to the last
        # rung (editorial_fallback) and still return this one candidate.
        SyntheticPlace(id=702_001, type="eat", status="active", area_term="kemang", org_id="org-a"),
    ]
    create_synthetic_places_table(city_conn, rows)

    subject_place = Candidate(entity_type="place", entity_id=SUBJECT_PLACE_ID, type="stay", area_term="scbd")
    subject = _subject(subject_place, primary_type="stay")

    result = compute_row1(city_conn, subject, relations, k=6, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    assert {i.entity_id for i in result.items} == {702_001}
    assert result.rung_name == "editorial_fallback"
    assert result.rungs_evaluated == ["strict", "area_to_district", "district_to_city", "editorial_fallback"]


def test_row1_no_subject_type_records_unvalidated_reason(city_conn, relations):
    create_synthetic_places_table(city_conn, generate_synthetic_place_rows(10))
    subject = _subject(place=None, primary_type=None)

    result = compute_row1(city_conn, subject, relations, k=6, rerank_pool=40, places_table=SYNTH_PLACES_TABLE)

    assert result.items == []
    assert result.unvalidated_reason is not None
    assert "F50" in result.unvalidated_reason
