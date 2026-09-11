"""Quality floor and series dedup (Sec.8.A) -- both proven against REAL
`now_jakarta` data, not synthetic: `engine.quality_scores` genuinely has
4,772 real article rows (E2.6 already ran), and `articles.series_key` has
real populated values (5 articles across 2 keys), so there is no need to
fabricate data for either of these two hard filters."""

from __future__ import annotations

from sqlalchemy import text

from now_filters.hard import build_articles_hard_filter_sql, fetch_articles_hard_filtered
from now_quality.scoring import QUALITY_FLOOR


def test_real_corpus_has_low_quality_articles_below_the_floor(conn):
    """Documents the live-data premise: real articles genuinely score
    below QUALITY_FLOOR (0.35) today, so the filter has real work to do,
    not just a synthetic scenario."""
    row = conn.execute(
        text("SELECT count(*) AS below FROM engine.quality_scores WHERE entity_type = 'article' AND score < :floor"),
        {"floor": QUALITY_FLOOR},
    ).one()
    assert row.below > 0, "expected some real articles below QUALITY_FLOOR -- premise of this test file broke"


def test_quality_floor_excludes_real_low_scoring_articles(conn, relations):
    """Every article returned by the hard filter (with `series_dedup`
    disabled, so this test isolates the quality-floor predicate cleanly)
    must have a quality_scores.score >= QUALITY_FLOOR, cross-checked
    directly against `engine.quality_scores` for a real sample.

    Uses `subject_type="editorial"` (a KNOWN, `exclude_same=False` type)
    against the real `relations` fixture to keep competitor exclusion a
    no-op while isolating the quality-floor predicate -- NOT
    `subject_type=None` with an empty `relations={}`, which (post-F68)
    now correctly fails closed and would exclude every real article
    (`primary_type` is NULL archive-wide, F50) rather than isolate
    anything. That combination previously "worked" here only because of
    the F68 bug this ticket fixes."""
    query = build_articles_hard_filter_sql(subject_type="editorial", relations=relations, series_dedup=False)
    # Constrain to a manageable sample via a LIMIT wrapper for speed --
    # the WHERE clause itself is unmodified, so this still exercises the
    # exact production predicate.
    limited_sql = f"SELECT * FROM ({query.sql}) sub ORDER BY id LIMIT 300"
    rows = conn.execute(text(limited_sql), query.params).fetchall()
    ids = [r.id for r in rows]
    assert ids, "expected at least some surviving articles in the first 300 ids"

    below_floor_ids = set(
        r[0]
        for r in conn.execute(
            text(
                "SELECT entity_id::int FROM engine.quality_scores "
                "WHERE entity_type = 'article' AND score < :floor AND entity_id::int = ANY(:ids)"
            ),
            {"floor": QUALITY_FLOOR, "ids": ids},
        ).fetchall()
    )
    assert not below_floor_ids, f"quality floor let through below-floor articles: {below_floor_ids}"


def test_missing_quality_score_does_not_exclude(conn):
    """Places currently have ZERO quality_scores rows (entity_type='place'
    has never been scored -- E2.6 only scored articles). The quality
    floor must not zero out the entire places rail just because nothing
    has been scored yet -- see hard.py docstring: "an un-scored entity is
    not the same thing as a low-quality one."."""
    row = conn.execute(text("SELECT count(*) FROM engine.quality_scores WHERE entity_type = 'place'")).scalar()
    assert row == 0, "expected zero place quality_scores today -- if this changes, this test's premise needs revisiting"


def test_series_dedup_keeps_one_per_real_series_key(conn, relations):
    """Real data: 5 articles share 2 series_keys as of this ticket
    (verified directly: `new-restaurants-in-jakarta-latest-openings` x3,
    `artmoments-jakarta` x2). After dedup, at most one row per series_key
    should be returned among those ids specifically.

    Uses `subject_type="editorial"` against the real `relations` fixture
    for the same reason as `test_quality_floor_excludes_real_low_scoring_articles`
    above -- `subject_type=None, relations={}` would now (post-F68)
    correctly exclude every real (NULL-typed) article, which would make
    this test vacuously pass on an empty result instead of genuinely
    exercising series dedup."""
    known_series = conn.execute(
        text(
            "SELECT series_key, array_agg(id) AS ids FROM public.articles "
            "WHERE series_key IN ('new-restaurants-in-jakarta-latest-openings', 'artmoments-jakarta') "
            "GROUP BY series_key"
        )
    ).fetchall()
    assert len(known_series) == 2, "expected exactly the 2 known real series_key groups"

    query = build_articles_hard_filter_sql(
        subject_type="editorial", relations=relations, series_dedup=True, quality_floor=None
    )
    rows = fetch_articles_hard_filtered(conn, query)
    by_series: dict[str, list[int]] = {}
    for c in rows:
        if c.series_key:
            by_series.setdefault(c.series_key, []).append(c.entity_id)

    for series_key, ids in known_series:
        survivors = by_series.get(series_key, [])
        assert len(survivors) <= 1, f"series dedup failed for {series_key!r}: {survivors}"
        assert set(survivors) <= set(ids)
