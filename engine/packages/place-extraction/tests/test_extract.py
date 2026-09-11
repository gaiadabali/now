from now_place_extraction.extract import extract_candidates, is_non_venue_phrase, looks_venue_shaped, plausible_new_place
from now_place_extraction.textwalk import flatten


def test_extracts_multiword_venue_name_with_connector():
    text = "We stayed at The Ritz-Carlton Jakarta Mega Kuningan for three nights."
    cands = [c.surface_text for c in extract_candidates(text)]
    assert "The Ritz-Carlton Jakarta Mega Kuningan" in cands


def test_does_not_start_or_end_on_a_connector():
    text = "Lunch at Warung Mia was excellent, then coffee at the cafe nearby."
    for c in extract_candidates(text):
        first, last = c.surface_text.split(" ")[0].lower(), c.surface_text.split(" ")[-1].lower()
        assert first not in {"the", "of", "at", "by", "and"}
        assert last not in {"the", "of", "at", "by", "and"}


def test_offsets_round_trip_against_source_text():
    text = "Nearby: Warung Mia for lunch and Ritz Carlton Mega Kuningan for dinner."
    cands = extract_candidates(text)
    for c in cands:
        assert text[c.start : c.end] == c.surface_text


def test_looks_venue_shaped():
    assert looks_venue_shaped("Potato Head Beach Club")
    assert not looks_venue_shaped("John Smith")


def test_looks_venue_shaped_does_not_substring_match():
    # "bar" inside "Lebaran" (Eid), "spa" inside "Spanish" -- found live
    # against real article text, not a hypothetical.
    assert not looks_venue_shaped("Lebaran")
    assert not looks_venue_shaped("Spanish")
    assert not looks_venue_shaped("Happy Lebaran")


def test_geographic_areas_are_not_plausible_new_places():
    # These belong in `places.area_term` / the platform location-term
    # tree (ARCHITECTURE.md Sec.4), never as their own venue row for
    # anything this pipeline creates.
    assert not plausible_new_place("South Jakarta")
    assert not plausible_new_place("Kebayoran Baru")
    assert not plausible_new_place("Hong Kong")
    assert not plausible_new_place("Central Java")
    assert not plausible_new_place("Chinese New Year")
    # A real venue that happens to CONTAIN an area name is unaffected --
    # the exclusion is a full-phrase match, not a substring one.
    assert plausible_new_place("Fraser Residence Menteng")


def test_is_non_venue_phrase_catches_bare_region_names():
    # Found live: `now_jakarta.public.places` id=4 is literally named
    # "Bali" (Finding #1) -- an exact gazetteer match against it fired on
    # every article merely mentioning the region in passing (1004 mentions
    # in the first real run, 64% of a random sample being this one row).
    # pipeline.py applies this same check to a gazetteer HIT, not just a
    # brand-new candidate.
    assert is_non_venue_phrase("Bali")
    assert is_non_venue_phrase("Ubud")
    assert not is_non_venue_phrase("Fraser Residence Menteng")


def test_temporal_event_phrases_are_not_plausible_new_places():
    # "Wellness" and "Restaurant" alone are already excluded; the harder
    # case found live is a generic keyword + a temporal word ("Wellness
    # Day", an event, not a venue) -- both words individually look
    # innocuous but together describe an event.
    assert not plausible_new_place("Wellness Day")
    assert not plausible_new_place("Restaurant Week")


def test_academy_awards_is_not_venue_shaped():
    # "academy" was removed from VENUE_KEYWORDS after it matched "Academy
    # Awards" (the Oscars) live -- real academies still match via "school".
    assert not looks_venue_shaped("Academy Awards")
    assert looks_venue_shaped("Mengen Culinary School")


def test_flatten_strips_html_and_joins_blocks():
    blocks = [
        {"type": "heading", "level": 2, "html": "<b>Where to Stay</b>"},
        {"type": "paragraph", "html": "We loved <em>The Viceroy Bali</em>."},
        {"type": "list", "ordered": False, "items": ["Warung Mia", "Motel Mexicola"]},
    ]
    text = flatten(blocks)
    assert "Where to Stay" in text
    assert "The Viceroy Bali" in text
    assert "Warung Mia" in text
    assert "<" not in text
