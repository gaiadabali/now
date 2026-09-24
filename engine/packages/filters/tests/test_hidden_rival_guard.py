"""The hidden-rival guard end to end: `build_articles_hard_filter_sql
(hidden_rival_pattern=...)` against synthetic `articles`/`places`/
`place_mentions`, proving a Kimpton/Westin-SHAPED case (a hotel subject,
an `event`-typed candidate that is really about a competing hotel) and a
restaurant->bar case both survive as regressions.

**Not a reproduction of the literal article id 4417.** `now_filters
.hidden_rival`'s module docstring records the measured, honest limit: the
real article's hotel mention is `role='mentioned'`, split across two
unlinked `place_id` rows, so `role='featured'`-only does NOT catch that
specific row today (an upstream entity-fragmentation gap, not a guard
bug). This fixture instead puts the hotel name on the FEATURED mention,
which is the shape the shipped rule DOES catch and is validated against a
much larger real sample -- see that module's docstring and the ticket
report for the actual precision measurement."""

from __future__ import annotations

from now_filters.hard import build_articles_hard_filter_sql, fetch_articles_hard_filtered
from now_filters.hidden_rival import hidden_rival_pattern_for_subject
from now_filters.synthetic import (
    SYNTH_ARTICLES_TABLE,
    SYNTH_PLACE_MENTIONS_TABLE,
    SYNTH_PLACES_TABLE,
    SyntheticArticle,
    SyntheticPlace,
    SyntheticPlaceMention,
    create_synthetic_articles_table,
    create_synthetic_place_mentions_table,
    create_synthetic_places_table,
)


def test_kimpton_westin_shaped_case_hotel_subject_excludes_mistyped_hotel_event_article(conn, relations):
    """A `stay` subject (id=1, standing in for the Kimpton story) must not
    offer article id=2 (typed `event`, really a hotel's wellness event --
    the Westin/Kimpton shape from docs/EDITION-2-PLAN.md §2), while a
    genuine, unrelated `event` article (id=3) survives."""
    articles = [
        SyntheticArticle(id=1, primary_type="stay"),  # subject itself, excluded elsewhere (self)
        SyntheticArticle(id=2, primary_type="event"),  # the hidden rival -- really a `stay` venue
        SyntheticArticle(id=3, primary_type="event"),  # genuine, unrelated event -- must survive
    ]
    create_synthetic_articles_table(conn, articles)
    places = [
        # `id=101` is the FEATURED mention's place row -- named for the
        # hotel itself, matching the real case: article 4417's real
        # featured mention (place id=13787) is titled "Celebrate Wellness
        # 2026" in the CMS but its `name` there is the event's own name,
        # not the venue's -- this fixture instead puts the venue's own
        # name on the FEATURED row directly, which is the simpler, still-
        # faithful shape: what matters to the guard is that a
        # `role='featured'` place's NAME reads as a `stay` venue, not which
        # id happens to hold it.
        SyntheticPlace(id=101, type="event", name="The Westin Resort Nusa Dua, Bali"),
        SyntheticPlace(id=102, type="event", name="Bali International Convention Center"),
        SyntheticPlace(id=201, type="event", name="Ubud Food Festival"),
    ]
    create_synthetic_places_table(conn, places)
    mentions = [
        SyntheticPlaceMention(article_id=2, place_id=102, role="mentioned", surface_text="Bali International Convention Center"),
        SyntheticPlaceMention(article_id=2, place_id=101, role="featured", surface_text="The Westin Resort Nusa Dua, Bali"),
        SyntheticPlaceMention(article_id=3, place_id=201, role="featured", surface_text="Ubud Food Festival"),
    ]
    create_synthetic_place_mentions_table(conn, mentions)

    pattern = hidden_rival_pattern_for_subject("stay", relations)
    assert pattern is not None

    query = build_articles_hard_filter_sql(
        subject_type="stay",
        relations=relations,
        exclude_self_id=1,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_pattern=pattern,
        place_mentions_table=SYNTH_PLACE_MENTIONS_TABLE,
        places_table=SYNTH_PLACES_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 2 not in survivors, "hidden-rival guard failed to catch the Kimpton/Westin case"
    assert 3 in survivors, "hidden-rival guard over-excluded an unrelated event article"


def test_restaurant_subject_excludes_bar_hiding_under_editorial(conn, relations):
    """A second, independently-constructed case: an `eat` (restaurant)
    subject must not be offered an `editorial`-typed article that is
    really a write-up centrally about a rooftop bar."""
    articles = [
        SyntheticArticle(id=10, primary_type="eat"),  # subject
        SyntheticArticle(id=11, primary_type="editorial"),  # hidden rival -- really a `drink` venue
        SyntheticArticle(id=12, primary_type="editorial"),  # genuine editorial piece -- must survive
    ]
    create_synthetic_articles_table(conn, articles)
    places = [
        SyntheticPlace(id=301, type="editorial", name="Sky Garden Rooftop Bar"),
        SyntheticPlace(id=302, type="editorial", name="Jakarta Heritage Trail"),
    ]
    create_synthetic_places_table(conn, places)
    mentions = [
        SyntheticPlaceMention(article_id=11, place_id=301, role="featured", surface_text="Sky Garden Rooftop Bar"),
        SyntheticPlaceMention(article_id=12, place_id=302, role="featured", surface_text="Jakarta Heritage Trail"),
    ]
    create_synthetic_place_mentions_table(conn, mentions)

    pattern = hidden_rival_pattern_for_subject("eat", relations)
    assert pattern is not None

    query = build_articles_hard_filter_sql(
        subject_type="eat",
        relations=relations,
        exclude_self_id=10,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_pattern=pattern,
        place_mentions_table=SYNTH_PLACE_MENTIONS_TABLE,
        places_table=SYNTH_PLACES_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 11 not in survivors, "hidden-rival guard failed to catch a bar hiding under editorial on a restaurant subject"
    assert 12 in survivors


def test_mentioned_role_alone_does_not_trigger_the_guard(conn, relations):
    """A place merely name-dropped (`role='mentioned'`) must not exclude
    the article -- only `role='featured'` does (module docstring). This is
    what keeps the guard from being a blanket 'never mentions a hotel'
    filter, which would be far too aggressive."""
    articles = [SyntheticArticle(id=20, primary_type="event")]
    create_synthetic_articles_table(conn, articles)
    places = [SyntheticPlace(id=401, type="event", name="Grand Hyatt Resort Bali")]
    create_synthetic_places_table(conn, places)
    mentions = [
        SyntheticPlaceMention(article_id=20, place_id=401, role="mentioned", surface_text="Grand Hyatt Resort Bali"),
    ]
    create_synthetic_place_mentions_table(conn, mentions)

    pattern = hidden_rival_pattern_for_subject("stay", relations)
    query = build_articles_hard_filter_sql(
        subject_type="stay",
        relations=relations,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_pattern=pattern,
        place_mentions_table=SYNTH_PLACE_MENTIONS_TABLE,
        places_table=SYNTH_PLACES_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 20 in survivors, "a `role='mentioned'` reference alone incorrectly triggered the hidden-rival guard"


def test_no_pattern_means_no_additional_exclusion(conn, relations):
    """`hidden_rival_pattern=None` (the default) must produce byte-for-byte
    the same surviving set as never having added this parameter -- a
    `do`/`event`/`editorial` subject excludes nothing, so
    `hidden_rival_pattern_for_subject` returns `None` for them and the
    guard must be entirely inert."""
    articles = [SyntheticArticle(id=30, primary_type="stay")]
    create_synthetic_articles_table(conn, articles)
    places = [SyntheticPlace(id=501, type="stay", name="Any Old Resort")]
    create_synthetic_places_table(conn, places)
    mentions = [SyntheticPlaceMention(article_id=30, place_id=501, role="featured", surface_text="Any Old Resort")]
    create_synthetic_place_mentions_table(conn, mentions)

    pattern = hidden_rival_pattern_for_subject("event", relations)
    assert pattern is None

    query = build_articles_hard_filter_sql(
        subject_type="event",
        relations=relations,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_pattern=pattern,
        place_mentions_table=SYNTH_PLACE_MENTIONS_TABLE,
        places_table=SYNTH_PLACES_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 30 in survivors
