from now_place_extraction.match import similarity


def test_exact_after_normalization():
    r = similarity("METIS Lounge", "Metis Lounge")
    assert r.exact
    assert r.score == 1.0


def test_name_drift_variants_score_high():
    # The ticket's own example.
    r = similarity("The Ritz-Carlton Jakarta Mega Kuningan", "Ritz Carlton Mega Kuningan")
    assert r.score >= 0.70


def test_different_venues_same_brand_different_area_do_not_over_merge():
    r = similarity("Padma Resort Ubud", "Padma Resort Legian")
    assert r.score < 0.85, f"should not clear the auto-merge gate, got {r.score}"


def test_unrelated_names_score_low():
    r = similarity("Viceroy Bali", "Fairmont Jakarta")
    assert r.score < 0.4


def test_single_shared_generic_descriptor_does_not_auto_merge():
    # Found live: "Grand Suite" (a room type) and "Grand Club" (a
    # membership tier) both reduce to the single core token {"grand"}
    # once "suite"/"club" are stripped as generic -- the old rule treated
    # ANY identical core set as a 0.90+ floor, which merged these (and
    # "The Grand Bali Beach", an unrelated hotel) into one cluster.
    r = similarity("Grand Suite", "Grand Club")
    assert r.score < 0.85, f"single generic-descriptor overlap must not clear the auto-merge gate, got {r.score}"
