import json

from now_geocode.terms import DEFAULT_LOCATION_SEED, load_location_tree


def _count_seed_terms(terms: list[dict]) -> int:
    return sum(1 + _count_seed_terms(t.get("children", [])) for t in terms)


def test_loads_every_seeded_term():
    """The loader must not drop nodes while walking the tree.

    This used to assert a hardcoded 85 and had been failing since Wave 13
    reseeded the taxonomy to 138 — a stale number, not a loader bug, but
    it left the package without a green suite. Comparing against the seed
    file instead makes the test self-validating: it still catches a loader
    that loses nodes, and it does not need editing every time the
    taxonomy grows.
    """

    seed = json.loads(DEFAULT_LOCATION_SEED.read_text(encoding="utf-8"))
    expected = _count_seed_terms(seed if isinstance(seed, list) else seed.get("terms", []))

    tree = load_location_tree()

    assert expected > 0, "seed file parsed to zero terms — the shape changed"
    assert len(tree.nodes) == expected


def test_specific_beats_general_by_depth_not_string_length():
    tree = load_location_tree()
    # "South Jakarta" (depth 1, 13 chars) is a longer string than "Kemang"
    # (depth 2, 6 chars) but the deeper node must win.
    assert tree.match_text("Jl. Kemang Raya No 1, South Jakarta") == "kemang"


def test_alias_matches():
    tree = load_location_tree()
    assert tree.match_text("A villa in Seminyak, South Bali") == "seminyak"
    assert tree.match_text("Near Bundaran HI") == "thamrin"


def test_generic_dictionary_word_alias_does_not_false_positive():
    tree = load_location_tree()
    # Regression: "Batu" (Malang alias, means "stone") must not hijack a
    # real Bali address just because the street name contains the word.
    assert tree.match_text("Jl. Pantai Batu Belig No. 5") is None
    # But a real, distinctive Malang alias still works.
    assert tree.match_text("A hotel near Bromo") == "malang"


def test_no_match_returns_none():
    tree = load_location_tree()
    assert tree.match_text("this text names no known area") is None
    assert tree.match_text(None) is None


def test_nearest_returns_closest_within_radius():
    tree = load_location_tree()
    # Seminyak's own seeded centroid.
    slug, distance_km = tree.nearest(-8.6913, 115.1683)
    assert slug == "seminyak"
    assert distance_km < 1.0


def test_nearest_none_when_too_far():
    tree = load_location_tree()
    # Middle of the Pacific — nowhere near any seeded centroid.
    assert tree.nearest(10.0, -160.0, max_km=60.0) is None
