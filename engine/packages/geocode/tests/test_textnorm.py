from now_geocode.textnorm import candidate_key, normalize_name, slugify


def test_normalize_name_strips_accents_punct_case():
    assert normalize_name("  Café del Mar, Bali!  ") == "cafe del mar bali"


def test_normalize_name_empty():
    assert normalize_name(None) == ""
    assert normalize_name("") == ""


def test_slugify_basic():
    assert slugify("Café del Mar, Bali!") == "cafe-del-mar-bali"


def test_slugify_never_empty():
    assert slugify("!!!") == "place"


def test_candidate_key_stable_and_distinguishes_address():
    k1 = candidate_key("Bali", None)
    k2 = candidate_key("Bali", None)
    k3 = candidate_key("Bali", "Some Address")
    assert k1 == k2
    assert k1 != k3
