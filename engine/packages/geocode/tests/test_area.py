from now_geocode.area import assign_area
from now_geocode.models import PlaceCandidate
from now_geocode.terms import load_location_tree

TREE = load_location_tree()


def _candidate(**kwargs) -> PlaceCandidate:
    base = dict(
        key="k",
        name="Test Place",
        address=None,
        city=None,
        province=None,
        country=None,
        existing_lat=None,
        existing_lng=None,
        existing_google_place_id=None,
    )
    base.update(kwargs)
    return PlaceCandidate(**base)


def test_address_text_match_wins_over_everything():
    c = _candidate(address="Jl. Kemang Raya No. 1, South Jakarta", name="Some Cafe")
    a = assign_area(c, TREE, None, None)
    assert a.slug == "kemang"
    assert a.method == "text_match"
    assert a.confidence == 0.9


def test_name_text_match_when_no_address():
    c = _candidate(name="Seminyak Beach Club")
    a = assign_area(c, TREE, None, None)
    assert a.slug == "seminyak"
    assert a.confidence == 0.75


def test_city_province_match_when_no_address_or_name_hit():
    c = _candidate(name="XYZ Venue", city="Ubud")
    a = assign_area(c, TREE, None, None)
    assert a.slug == "ubud"
    assert a.confidence == 0.6


def test_geometric_nearest_when_no_text_signal_but_has_coords():
    c = _candidate(name="Unnamed POI")
    # Right on top of the seeded Seminyak centroid.
    a = assign_area(c, TREE, -8.6913, 115.1683)
    assert a.slug == "seminyak"
    assert a.method == "geometric_nearest"
    assert a.distance_km is not None and a.distance_km < 1.0


def test_country_fallback_when_nothing_at_all():
    c = _candidate(name="???")
    a = assign_area(c, TREE, None, None)
    assert a.slug == "indonesia"
    assert a.method == "country_fallback"
    assert a.confidence == 0.15


def test_international_fallback_on_explicit_non_indonesia_country():
    c = _candidate(name="Some Overseas Thing", country="Singapore")
    a = assign_area(c, TREE, None, None)
    assert a.slug == "international"
    assert a.method == "international_fallback"


def test_text_match_beats_geometric_even_when_farther_looking():
    # Coordinates land geometrically nearest to Jakarta, but the address
    # explicitly names Kemang — text should still win (it's cited, not guessed).
    c = _candidate(address="Kemang Raya")
    a = assign_area(c, TREE, -6.9, 107.0)  # nowhere near Kemang's centroid
    assert a.slug == "kemang"
    assert a.method == "text_match"
