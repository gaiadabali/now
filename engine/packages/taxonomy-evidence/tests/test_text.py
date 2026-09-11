from now_taxonomy_evidence.text import (
    DECAY_CLASS, FORMATS, TYPES, VENUE_TYPES, build_location_matcher, clean_html, first_person_density, is_roundup,
    match_locations, period_stamp, score_format_full, score_type,
)

# A small stand-in for the seed location tree (engine/packages/taxonomy/seed),
# just the slugs this test file exercises -- real matcher construction is
# covered by loading the real seed in features.py / cli.py.
_LOCATION_SEED = [
    {"slug": "jakarta", "label": "Jakarta", "aliases": []},
    {"slug": "south-jakarta", "label": "South Jakarta", "aliases": ["Jakarta Selatan"]},
    {"slug": "senayan", "label": "Senayan", "aliases": []},
    {"slug": "bali", "label": "Bali", "aliases": []},
    {"slug": "ubud", "label": "Ubud", "aliases": []},
    {"slug": "canggu", "label": "Canggu", "aliases": []},
    {"slug": "bandung", "label": "Bandung", "aliases": []},
    {"slug": "padang", "label": "Padang", "aliases": []},
    {"slug": "makassar", "label": "Makassar", "aliases": []},
    {"slug": "sulawesi", "label": "Sulawesi", "aliases": []},
    {"slug": "malang", "label": "Malang", "aliases": []},
]


def _matcher():
    return build_location_matcher(_LOCATION_SEED)


def test_clean_html_strips_tags_shortcodes_and_entities():
    raw = '<p>Hello&nbsp;<b>world</b></p>[caption id="x"]img[/caption]<script>alert(1)</script> &amp; more'
    assert clean_html(raw) == "Hello world img & more"


def test_type_cues_pick_venue_types():
    assert score_type("Get Energised at Sakanti Spa", "Sakanti Spa offers massage treatments and wellness rituals.").value == "wellness"
    assert score_type("New Menu at Tiger Palm Restaurant", "Chef Tim unveils dishes at the pan-Asian restaurant.").value == "eat"
    assert score_type("Breman: Bali's Newest Microbrewery and Bar", "Craft beer on tap at the new bar in Canggu.").value == "drink"
    assert score_type("Romantic Getaway at Oakwood Hotel & Residence", "Book the suite package with breakfast for two nights.").value == "stay"


def test_type_scorer_abstains_without_signal():
    assert score_type("A Birthday Wish", "Some reflections on the year.").value is None


# --- F111/F113: keyword-cue instrument fires on topic vocabulary without a
# title anchor -- spot-checked failure mode was "Italy -- The Land of Wines"
# (an editorial history of Italian wine) scoring `drink`; a whisky
# market-entry business story scoring `drink`; a skincare founder profile
# scoring `wellness`. The fix: a candidate with zero title-zone support can
# no longer be decided purely from lead/body density, however broad or
# repetitive -- see NO_TITLE_CEILING in text.py.

def test_body_only_density_no_longer_decides_without_a_title_anchor():
    # A generic, venue-less title; the entire signal is topic vocabulary
    # repeated across the lead/body, never naming a specific venue. Before
    # the fix this scored a confident `drink` from breadth-of-vocabulary
    # alone; now it must abstain (-> sent to review, not auto-applied).
    title = "A Weekend of Reflection"
    body = (
        "The bar was full of stories that night, and the bartender poured cocktails as regulars "
        "talked about the wine list and the craft beer on tap. Sommeliers debated whisky and gin, "
        "while the nightclub next door thumped with bass. Over cocktails and rum, everyone agreed the "
        "lounge was the best rooftop bar in town. "
    ) * 3
    assert score_type(title, body).value is None


def test_title_anchor_still_lets_body_corroborate():
    # The mirror case: once the title itself names the venue type, body
    # repetition of the same vocabulary should still corroborate it -- the
    # fix narrows what body/lead evidence can do ALONE, it does not disable
    # them as corroboration once a title anchor exists.
    title = "Inside Jakarta's Newest Rooftop Bar"
    body = (
        "The bar serves craft cocktails against a skyline view, with a rotating list of small-batch gin "
        "and whisky. Regulars say the bartenders know their way around a shaker, and the wine list is "
        "just as considered as the cocktail menu. "
    ) * 2
    assert score_type(title, body).value == "drink"


def test_format_offer_and_news_and_event():
    assert score_format_full("Festive Package at Hotel X", "IDR 1,500,000++ per person, valid until 31 December. Book now.").value == "offer"
    assert score_format_full("Hotel Borobudur Appoints New General Manager", "The hotel announces the appointment of Jane Doe as GM.").value == "news"
    assert score_format_full("Jakarta Jazz Festival Returns", "The festival will be held on 3 March at JIExpo; tickets are available online.").value == "event"


def test_first_person_routes_to_review_only_for_venues():
    body = ("We arrived at sunset and I ordered the tuna. The service was warm and our table overlooked the bay. "
            "My companion loved the dessert; we tried three cocktails and I must say the portions were generous. " * 3)
    assert first_person_density(body) > 8
    assert score_format_full("A Chic Jimbaran Dinner at Bamboo Chic Restaurant", body).value == "review"
    essay = ("I think we should ask why the city keeps flooding. In my view the governor has ignored us; " * 6)
    assert score_format_full("Idle Thoughts from a Disturbed Resident", essay).value != "review"


def test_period_stamp_and_roundup():
    assert period_stamp("The Best Cocktail Bars in Jakarta (2026)") == "year"
    assert period_stamp("New Restaurants in Bali [Updated]") == "updated"
    assert period_stamp("Christmas in Bali: Lunches and Dinners") == "seasonal"
    assert period_stamp("Destination Dim Sum") is None
    assert is_roundup("8 Best Beer Bars in Jakarta")
    assert is_roundup("10 Best Bali Playgrounds and Parks for Kids (2026 Guide)")
    assert not is_roundup("A Seminyak Oasis")


def test_decay_classes_cover_every_format_and_venue_types_match_seed():
    assert set(DECAY_CLASS) == set(FORMATS)
    assert set(VENUE_TYPES) <= set(TYPES)
    assert set(VENUE_TYPES) == {"stay", "eat", "drink", "wellness", "shop"}


# --- F95: dish-name false positives in the location matcher -----------------
# Root cause: "nasi bali", "siomay bandung" etc. are Indonesian dish names
# (a food noun + a region name), not place mentions, and this naming
# convention is routine in the corpus. The fix suppresses a location match
# only when it is immediately preceded (optionally through a style modifier
# like "khas") by a curated dish-noun -- see the design-tradeoff comment in
# text.py above build_location_matcher.

def test_wp_5557_reproduction_no_longer_matches_jakarta_lead():
    # The concrete case from F95: a Jakarta hotel brunch article whose lead
    # lists "martabak, siomay bandung, nasi bali, ..." as menu items. Neither
    # dish name is a place mention.
    title = "Kristal Hotel and Serviced Residence Launched Sunday Street Food Brunch"
    lead = ("The hotel now offers a spread of Indonesian street food such as martabak, "
            "siomay bandung, nasi bali, nasi liwet and more, every Sunday.")
    assert match_locations(title, lead, _matcher()) == []


def test_dish_names_do_not_match_regardless_of_zone():
    m = _matcher()
    assert match_locations("Nasi Padang for Lunch", "", m) == []
    assert match_locations("", "We tried the soto Padang and it was excellent.", m) == []
    assert match_locations("The Best of Indonesian Comfort Food at Sate Khas Senayan", "", m) == []
    # a generic F&B-brand connector word between the dish noun and the place
    assert match_locations("Sate House Senayan Propels Indonesian Culinary Heritage", "", m) == []


def test_dish_context_suppresses_only_the_dish_occurrence_not_the_slug():
    # If the same place also appears in a non-dish context, it must still be
    # reported -- suppression is per-occurrence, not per-slug.
    m = _matcher()
    assert match_locations("The Best Nasi Padang Joints", "A ranking of restaurants in Padang.", m) == ["padang"]


def test_true_positive_headlines_still_match():
    # These are the protected cases: real title-style location mentions,
    # with and without a preposition, must survive the fix unchanged.
    m = _matcher()
    assert match_locations("Best Restaurants in Bali", "", m) == ["bali"]
    assert match_locations("A Weekend in Bandung", "", m) == ["bandung"]
    assert match_locations("Ubud's Newest Cafe Experience", "", m) == ["ubud"]
    assert match_locations("Best Restaurants in Canggu (2026): A NOW! Bali Guide", "", m) == ["bali", "canggu"]
    assert match_locations("Cultivating Specialty Bali Coffee", "with Tanamera Coffee Indonesia", m) == ["bali"]
    # cuisine-of-a-region phrasing is a real (if soft) location signal and
    # must not be swept up by the dish-noun stoplist.
    assert match_locations("Enjoy the Cuisine of Sulawesi", "", m) == ["sulawesi"]


def test_makassar_dish_name_does_not_leak_into_jakarta_article():
    # wp_id 7881: a Jakarta hotel promo naming "Daging Konro Makassar" as a
    # menu item must not tag the article with location=makassar.
    title = "Enjoy the Cuisine of Sulawesi at Le Meridien Jakarta"
    lead = "Try mouthwatering dishes like Daging Konro Makassar and Ayam Tinutuan this month."
    assert match_locations(title, lead, _matcher()) == ["jakarta", "sulawesi"]


def test_cross_city_brand_false_positive_is_gone():
    # wp_id 87106: a Bali article about the "Sate House Senayan" restaurant
    # brand must not pick up "senayan" (a Jakarta district) as a location.
    title = "Sate House Senayan Propels Indonesian Culinary Heritage to the Global Stage"
    lead = "The brand, born in Bali, has grown its footprint from Canggu to the rest of the island."
    assert match_locations(title, lead, _matcher()) == ["bali", "canggu"]
