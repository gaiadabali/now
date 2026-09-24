from __future__ import annotations

from now_classifier.facet_tagging.lexicon import ZONE_BODY, ZONE_LEAD, ZONE_TITLE, build_term_matcher, match_term_zones

SEED = [
    {"slug": "surf", "label": "Surf", "aliases": ["surfing", "surfboard"]},
    {"slug": "wellness", "label": "Wellness", "aliases": ["spa day"]},
]


def test_title_match_wins_over_lead_and_body() -> None:
    matcher = build_term_matcher(SEED)
    zones = match_term_zones("A Guide to Surfing in Canggu", "great waves", "more waves and beach talk " * 20, matcher)
    assert zones["surf"] == ZONE_TITLE


def test_lead_only_match_is_reported_as_lead() -> None:
    matcher = build_term_matcher(SEED)
    zones = match_term_zones("A Quiet Weekend Away", "Book a spa day at the resort", "unrelated body text " * 20, matcher)
    assert zones["wellness"] == ZONE_LEAD


def test_body_only_match_is_reported_as_body() -> None:
    matcher = build_term_matcher(SEED)
    body = ("filler " * 100) + "a surfboard leaning by the door" + (" filler" * 100)
    zones = match_term_zones("A Quiet Weekend Away", "no signal here", body, matcher)
    assert zones.get("surf") == ZONE_BODY


def test_no_match_is_absent_not_none() -> None:
    matcher = build_term_matcher(SEED)
    zones = match_term_zones("Nothing Related Here", "still nothing", "still nothing at all", matcher)
    assert "surf" not in zones
    assert "wellness" not in zones


def test_word_boundary_prevents_substring_false_positive() -> None:
    # "surf" must not match inside "resurface" -- word-boundary regex, not bare substring.
    matcher = build_term_matcher(SEED)
    zones = match_term_zones("Plans to Resurface the Old Road", "no other signal", "still nothing", matcher)
    assert "surf" not in zones


def test_alias_exclusion_star_drops_whole_term() -> None:
    exclusions = {("audience", "surf"): "*"}
    matcher = build_term_matcher(SEED, facet_key="audience", alias_exclusions=exclusions)
    slugs = {tp.slug for tp in matcher}
    assert "surf" not in slugs
    assert "wellness" in slugs


def test_alias_exclusion_drops_only_the_named_alias() -> None:
    exclusions = {("topic", "wellness"): frozenset({"spa day"})}
    matcher = build_term_matcher(SEED, facet_key="topic", alias_exclusions=exclusions)
    zones = match_term_zones("A headline", "Book a spa day now", "filler", matcher)
    # "spa day" was excluded, but the term's own label "Wellness" still matches.
    assert "wellness" not in zones
    zones2 = match_term_zones("A Wellness Retreat", "filler", "filler", matcher)
    assert zones2["wellness"] == ZONE_TITLE
