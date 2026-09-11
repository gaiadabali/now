from now_place_extraction.normalize import blocking_key, core_tokens, normalize_full


def test_normalize_full_case_and_punctuation_insensitive():
    assert normalize_full("METIS Lounge") == normalize_full("Metis Lounge")
    assert normalize_full("SVÁ ─ Indonesian Tapas & Bar") != ""


def test_core_tokens_strips_generic_words_but_keeps_area_names():
    # "Resort"/"Bali" are generic; "Ubud" and "Legian" are NOT -- they are
    # the whole reason two same-brand hotels in different areas must stay
    # distinct (see match.py docstring).
    ubud = set(core_tokens("Padma Resort Ubud"))
    legian = set(core_tokens("Padma Resort Legian"))
    assert "ubud" in ubud
    assert "legian" in legian
    assert ubud != legian


def test_blocking_key_falls_back_when_all_words_generic():
    # "The Beach Club" is entirely generic words -- blocking_key must not
    # return an empty string (which would dump every such name into one
    # giant, meaningless block).
    key = blocking_key("The Beach")
    assert key != ""
