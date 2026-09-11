from now_geocode.models import GeocodedPlace, Rung, Status
from now_geocode.pgdemo import render_st_dwithin_demo_sql


def _place(key, name, lat, lng, status=Status.RESOLVED, source=Rung.EXISTING_COORDINATES):
    return GeocodedPlace(
        place_key=key, name=name, slug=name.lower().replace(" ", "-"), address=None,
        city=None, province=None, country=None, lat=lat, lng=lng, status=status,
        source=source, confidence=0.9, google_place_id=None, area_term="jakarta",
        area_term_source="text_match", area_term_confidence=0.9, flags=[],
        source_refs=[], review_reason=None,
    )


def test_sql_contains_temp_table_and_on_commit_drop():
    places = [_place("k1", "A", -6.2, 106.8), _place("k2", "B", -6.21, 106.81)]
    sql = render_st_dwithin_demo_sql(places)
    assert "CREATE TEMP TABLE" in sql
    assert "ON COMMIT DROP" in sql
    assert "ST_DWithin" in sql
    assert "ST_MakePoint(106.8, -6.2)" in sql


def test_excludes_unresolved_and_rejected():
    places = [
        _place("k1", "Resolved", -6.2, 106.8),
        _place("k2", "Rejected", 52.0, 4.0, status=Status.REJECTED),
        _place("k3", "Unresolved", None, None, status=Status.UNRESOLVED),
    ]
    sql = render_st_dwithin_demo_sql(places)
    assert "'Resolved'" in sql
    assert "'Rejected'" not in sql
    assert "'Unresolved'" not in sql


def test_empty_input_rolls_back_instead_of_crashing():
    sql = render_st_dwithin_demo_sql([])
    assert "ROLLBACK" in sql


def test_sql_string_literals_escape_single_quotes():
    places = [_place("k1", "O'Brien's Bar", -6.2, 106.8)]
    sql = render_st_dwithin_demo_sql(places)
    assert "O''Brien''s Bar" in sql
