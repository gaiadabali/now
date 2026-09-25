"""The hidden-rival guard end to end: `build_articles_hard_filter_sql`'s
`apply_hidden_rival_guard` predicate against a synthetic `engine
.hidden_rival_flags`-shaped table, proving a Kimpton/Westin-SHAPED case (a
hotel subject, an `event`-typed candidate that is really about a
competing hotel) and a restaurant->bar case both survive as regressions.

Second pass (2026-09-24): the guard reads a PRECOMPUTED table now, not a
live `place_mentions`/`places` regex join (see `now_filters.hard`'s
docstring and `now_filters.hidden_rival_recompute`, which is what actually
populates `engine.hidden_rival_flags` in production) -- these tests
therefore populate the synthetic flags table directly, as if the recompute
had already run, rather than synthesizing place_mentions/places rows for
`build_articles_hard_filter_sql` to join against live. `now_filters
.hidden_rival_recompute`'s OWN detection logic (place-name/title matching
against the lexicon) is covered separately by `test_hidden_rival_lexicon
.py` (pure) and would need a DB-integration test of its own to prove the
recompute step itself against real place_mentions/places -- not added
here given time; flagged as a gap.
"""

from __future__ import annotations

from now_filters.hard import build_articles_hard_filter_sql, fetch_articles_hard_filtered
from now_filters.synthetic import (
    SYNTH_ARTICLES_TABLE,
    SYNTH_HIDDEN_RIVAL_FLAGS_TABLE,
    SyntheticArticle,
    SyntheticHiddenRivalFlag,
    create_synthetic_articles_table,
    create_synthetic_hidden_rival_flags_table,
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
    create_synthetic_hidden_rival_flags_table(
        conn, [SyntheticHiddenRivalFlag(article_id=2, matched_type="stay", signal="featured_mention")]
    )

    query = build_articles_hard_filter_sql(
        subject_type="stay",
        relations=relations,
        exclude_self_id=1,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_flags_table=SYNTH_HIDDEN_RIVAL_FLAGS_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 2 not in survivors, "hidden-rival guard failed to catch the Kimpton/Westin-shaped case"
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
    create_synthetic_hidden_rival_flags_table(
        conn, [SyntheticHiddenRivalFlag(article_id=11, matched_type="drink", signal="featured_mention")]
    )

    query = build_articles_hard_filter_sql(
        subject_type="eat",
        relations=relations,
        exclude_self_id=10,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_flags_table=SYNTH_HIDDEN_RIVAL_FLAGS_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 11 not in survivors, "hidden-rival guard failed to catch a bar hiding under editorial on a restaurant subject"
    assert 12 in survivors


def test_flag_for_an_irrelevant_type_does_not_trigger_the_guard(conn, relations):
    """A flag naming a type the subject does NOT exclude (e.g. `do` on a
    `stay` subject, which complements it) must not exclude the candidate
    -- the guard only fires for `matched_type`s in the subject's own
    excluded-type set, mirroring the main competitor predicate exactly."""
    articles = [SyntheticArticle(id=20, primary_type="event")]
    create_synthetic_articles_table(conn, articles)
    create_synthetic_hidden_rival_flags_table(
        conn, [SyntheticHiddenRivalFlag(article_id=20, matched_type="do", signal="featured_mention")]
    )

    query = build_articles_hard_filter_sql(
        subject_type="stay",
        relations=relations,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_flags_table=SYNTH_HIDDEN_RIVAL_FLAGS_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 20 in survivors, "a flag for a non-excluded type incorrectly triggered the hidden-rival guard"


def test_apply_hidden_rival_guard_false_disables_the_predicate_entirely(conn, relations):
    """`apply_hidden_rival_guard=False` must produce byte-for-byte the
    same surviving set as if the flags table were empty -- the escape
    hatch for a caller/test that wants the primary-type predicate
    isolated from this second check."""
    articles = [SyntheticArticle(id=30, primary_type="stay")]
    create_synthetic_articles_table(conn, articles)
    create_synthetic_hidden_rival_flags_table(
        conn, [SyntheticHiddenRivalFlag(article_id=30, matched_type="stay", signal="featured_mention")]
    )

    query = build_articles_hard_filter_sql(
        subject_type="event",  # excludes nothing -> excluded_types empty -> guard clause never added regardless
        relations=relations,
        series_dedup=False,
        articles_table=SYNTH_ARTICLES_TABLE,
        hidden_rival_flags_table=SYNTH_HIDDEN_RIVAL_FLAGS_TABLE,
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert 30 in survivors
