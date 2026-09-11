from now_eval.calibration.provenance import provenance_label


def test_category_fixed_bands():
    assert provenance_label("type", 0.95, "inferred") == "category_fixed_high"
    assert provenance_label("location", 0.75, "inferred") == "category_fixed_medium"
    assert provenance_label("format", 0.45, "inferred") == "category_fixed_low"


def test_cue_bands_type_format():
    assert provenance_label("type", 0.93, "ai") == "cue_confident"
    assert provenance_label("format", 0.72, "ai") == "cue_fired"
    assert provenance_label("type", 0.40, "inferred") == "cue_abstain_fallback"


def test_location_090_disambiguated_by_source():
    # The whole point: same confidence number, different mechanism, must not collide.
    assert provenance_label("location", 0.90, "inferred") == "site_home_fallback"
    assert provenance_label("location", 0.90, "ai") == "title_match"
    assert provenance_label("location", 0.90, "inferred") != provenance_label("location", 0.90, "ai")


def test_location_lead_only():
    assert provenance_label("location", 0.55, "ai") == "lead_only_match"


def test_subtype_own_bands():
    assert provenance_label("subtype", 0.70, "ai") == "subtype_keyword_match"
    assert provenance_label("subtype", 0.35, "inferred") == "subtype_no_match_fallback"


def test_subtype_reuses_category_fixed_bands():
    # subtype's category-fixed values (no per-article keyword mechanism
    # involved) are the exact same CATEGORY_FIXED_CONFIDENCE numbers as
    # type/format -- same label, deliberately, since it's the same mapping.
    assert provenance_label("subtype", 0.95, "inferred") == "category_fixed_high"
    assert provenance_label("subtype", 0.75, "inferred") == "category_fixed_medium"
