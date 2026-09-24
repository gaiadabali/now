"""DB-integration coverage for `now_filters.hidden_rival_recompute`'s
read/write plumbing -- the gap flagged in the ticket report after the
second pass, which had only pure pattern-compilation tests for this
module. Skips cleanly if `now_jakarta` is unreachable (this package's own
`conftest.py` convention); runs for real in CI/a normal dev shell.

Uses this package's synthetic-table convention throughout (`now_filters
.synthetic`) rather than touching the real `public.articles`/
`public.place_mentions`/`public.places` or the real `engine
.hidden_rival_flags` -- every table name here is a session-scoped TEMP
TABLE, dropped automatically when the connection closes.
"""

from __future__ import annotations

from sqlalchemy import text

from now_filters.hidden_rival_recompute import (
    recompute_flags_for_article,
    recompute_hidden_rival_flags,
    remove_flags_for_article,
)
from now_filters.synthetic import (
    SYNTH_ARTICLES_TABLE,
    SYNTH_HIDDEN_RIVAL_FLAGS_TABLE,
    SYNTH_PLACE_MENTIONS_TABLE,
    SYNTH_PLACES_TABLE,
    SyntheticArticle,
    SyntheticHiddenRivalFlag,
    SyntheticPlace,
    SyntheticPlaceMention,
    create_synthetic_articles_table,
    create_synthetic_hidden_rival_flags_table,
    create_synthetic_place_mentions_table,
    create_synthetic_places_table,
)

_KWARGS = dict(
    articles_table=SYNTH_ARTICLES_TABLE,
    place_mentions_table=SYNTH_PLACE_MENTIONS_TABLE,
    places_table=SYNTH_PLACES_TABLE,
    flags_table=SYNTH_HIDDEN_RIVAL_FLAGS_TABLE,
)


def _flag_rows(conn) -> set[tuple[str, str, str]]:
    rows = conn.execute(text(f"SELECT article_id, matched_type, signal FROM {SYNTH_HIDDEN_RIVAL_FLAGS_TABLE}")).fetchall()
    return {(r.article_id, r.matched_type, r.signal) for r in rows}


def test_full_recompute_finds_both_signals_and_reports_a_diff(conn, relations):
    articles = [
        SyntheticArticle(id=1, primary_type="event", title="Grand Hyatt Bali Resort Presents a Gala"),  # hidden rival via title
        SyntheticArticle(id=2, primary_type="event", title="An Evening of Jazz"),  # hidden rival via featured mention
        SyntheticArticle(id=3, primary_type="editorial", title="A Community Feature"),  # no match either way
    ]
    create_synthetic_articles_table(conn, articles)

    places = [SyntheticPlace(id=101, type="event", name="The Grand Ballroom Resort")]
    create_synthetic_places_table(conn, places)
    mentions = [SyntheticPlaceMention(article_id=2, place_id=101, role="featured", surface_text="The Grand Ballroom Resort")]
    create_synthetic_place_mentions_table(conn, mentions)
    create_synthetic_hidden_rival_flags_table(conn, [])

    report = recompute_hidden_rival_flags(conn, **_KWARGS)
    assert report.added == 2, "expected exactly the title match (article 1) and the featured-mention match (article 2)"
    assert report.removed == 0
    assert report.changed is True

    seen = _flag_rows(conn)
    assert ("1", "stay", "title") in seen
    assert ("2", "stay", "featured_mention") in seen
    assert not any(article_id == "3" for article_id, _, _ in seen)


def test_full_recompute_second_run_is_a_no_op(conn, relations):
    articles = [SyntheticArticle(id=1, primary_type="event", title="Sofitel Bali Resort Gala")]
    create_synthetic_articles_table(conn, articles)
    create_synthetic_places_table(conn, [])
    create_synthetic_place_mentions_table(conn, [])
    create_synthetic_hidden_rival_flags_table(conn, [])

    first = recompute_hidden_rival_flags(conn, **_KWARGS)
    assert first.added == 1

    second = recompute_hidden_rival_flags(conn, **_KWARGS)
    assert second.added == 0
    assert second.removed == 0
    assert second.unchanged == 1
    assert second.changed is False


def test_recompute_flags_for_article_touches_only_that_article(conn, relations):
    articles = [
        SyntheticArticle(id=1, primary_type="event", title="Alila Resort Bali Gala"),
        SyntheticArticle(id=2, primary_type="event", title="Another Resort Gala"),
    ]
    create_synthetic_articles_table(conn, articles)
    create_synthetic_places_table(conn, [])
    create_synthetic_place_mentions_table(conn, [])
    # Pre-seed article 2's flag directly, as if a PRIOR recompute had
    # already found it -- proves recomputing article 1 alone leaves it
    # untouched.
    create_synthetic_hidden_rival_flags_table(
        conn, [SyntheticHiddenRivalFlag(article_id=2, matched_type="stay", signal="title")]
    )

    report = recompute_flags_for_article(conn, 1, **_KWARGS)
    assert report.added == 1
    assert report.removed == 0

    seen = _flag_rows(conn)
    assert ("1", "stay", "title") in seen
    assert ("2", "stay", "title") in seen, "recomputing article 1 must not remove article 2's pre-existing flag"


def test_recompute_flags_for_article_is_idempotent_on_redelivery(conn, relations):
    """The domain-event stream is at-least-once (`now_embeddings.worker`'s
    own docstring) -- redelivering the identical publish event must be a
    safe no-op, not a duplicate-key error or a doubled row."""
    articles = [SyntheticArticle(id=1, primary_type="event", title="Padma Resort Legian Gala")]
    create_synthetic_articles_table(conn, articles)
    create_synthetic_places_table(conn, [])
    create_synthetic_place_mentions_table(conn, [])
    create_synthetic_hidden_rival_flags_table(conn, [])

    first = recompute_flags_for_article(conn, 1, **_KWARGS)
    second = recompute_flags_for_article(conn, 1, **_KWARGS)
    assert first.added == 1
    assert second.added == 0 and second.removed == 0 and second.unchanged == 1


def test_recompute_flags_for_article_removes_a_flag_that_no_longer_applies(conn, relations):
    """An editor removes the hotel-shaped wording from a title -- the next
    recompute (redelivery of `article.republished`) must retract the
    flag, not just add new ones."""
    articles = [SyntheticArticle(id=1, primary_type="event", title="A Community Feature")]
    create_synthetic_articles_table(conn, articles)
    create_synthetic_places_table(conn, [])
    create_synthetic_place_mentions_table(conn, [])
    create_synthetic_hidden_rival_flags_table(
        conn, [SyntheticHiddenRivalFlag(article_id=1, matched_type="stay", signal="title")]
    )

    report = recompute_flags_for_article(conn, 1, **_KWARGS)
    assert report.removed == 1
    assert report.added == 0

    remaining = conn.execute(
        text(f"SELECT count(*) FROM {SYNTH_HIDDEN_RIVAL_FLAGS_TABLE} WHERE article_id = '1'")
    ).scalar_one()
    assert remaining == 0


def test_remove_flags_for_article_deletes_everything_for_that_article(conn, relations):
    create_synthetic_hidden_rival_flags_table(
        conn,
        [
            SyntheticHiddenRivalFlag(article_id=1, matched_type="stay", signal="title"),
            SyntheticHiddenRivalFlag(article_id=1, matched_type="eat", signal="featured_mention"),
            SyntheticHiddenRivalFlag(article_id=2, matched_type="stay", signal="title"),
        ],
    )

    removed = remove_flags_for_article(conn, 1, flags_table=SYNTH_HIDDEN_RIVAL_FLAGS_TABLE)
    assert removed == 2

    rows = conn.execute(text(f"SELECT article_id FROM {SYNTH_HIDDEN_RIVAL_FLAGS_TABLE}")).fetchall()
    assert {r.article_id for r in rows} == {"2"}

    # Idempotent -- a second delete (redelivered unpublish event) is a safe no-op.
    removed_again = remove_flags_for_article(conn, 1, flags_table=SYNTH_HIDDEN_RIVAL_FLAGS_TABLE)
    assert removed_again == 0
