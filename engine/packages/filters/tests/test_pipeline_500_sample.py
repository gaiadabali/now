"""Acceptance criterion: "No empty rail across a 500-article sample
(using synthetic types)."

Uses a REAL 500-id sample from `now_jakarta.articles` (real `id`,
`published_at`, `series_key`, real `engine.quality_scores` rows) with a
SYNTHETIC `primary_type` overlay (deterministic hash assignment across the
8 L1 types, `now_filters.synthetic.deterministic_type`) copied into an
explicitly-named temp table -- real articles cannot be used directly for
this criterion because `primary_type` is NULL for all 4,772 rows (E2.1
has not run), which (see `test_hard_filters_competitor.py` /
`hard.py` module docstring) means the REAL hard filter today returns
ZERO candidates for every non-empty competitor exclusion. That zero
result is honest and expected against live data -- this test exists
specifically to prove the MACHINERY does not starve once real type data
exists, using synthetic types as the stand-in ARCHITECTURE.md's own task
brief calls for.

For every one of the 8 L1 subject types, the hard-filtered candidate pool
(drawn from the 500-sample, competitor-excluded, quality-floor applied,
series-deduped) must be non-empty.
"""

from __future__ import annotations

from sqlalchemy import text

from now_filters.hard import build_articles_hard_filter_sql, fetch_articles_hard_filtered
from now_filters.synthetic import SYNTH_ARTICLES_TABLE, SyntheticArticle, create_synthetic_articles_table, deterministic_type

SAMPLE_SIZE = 500
ALL_L1_TYPES = ("stay", "eat", "drink", "wellness", "shop", "do", "event", "editorial")


def _build_500_sample(conn) -> None:
    rows = conn.execute(
        text("SELECT id, series_key, published_at FROM public.articles ORDER BY id LIMIT :n"),
        {"n": SAMPLE_SIZE},
    ).fetchall()
    assert len(rows) == SAMPLE_SIZE, f"expected {SAMPLE_SIZE} real articles, got {len(rows)}"

    synthetic_rows = [
        SyntheticArticle(
            id=r.id,
            primary_type=deterministic_type(r.id, pool=ALL_L1_TYPES),
            series_key=r.series_key,
            published_at=r.published_at,
            status="published",
        )
        for r in rows
    ]
    create_synthetic_articles_table(conn, synthetic_rows)


def test_synthetic_type_distribution_covers_all_eight_l1_types(conn):
    """Sanity check on the sample itself before asserting anything about
    the filter: the deterministic hash assignment must actually produce
    every L1 type across 500 ids (a skewed or degenerate hash would make
    the "no empty rail" assertion below vacuous for whichever type never
    appears)."""
    _build_500_sample(conn)
    rows = conn.execute(text(f"SELECT primary_type, count(*) FROM {SYNTH_ARTICLES_TABLE} GROUP BY 1")).fetchall()
    seen_types = {r[0] for r in rows}
    assert seen_types == set(ALL_L1_TYPES)
    for type_, count in rows:
        assert count > 0, type_


def test_no_empty_rail_across_500_article_sample_for_every_subject_type(conn, relations):
    _build_500_sample(conn)
    empty_types = []
    counts = {}
    for subject_type in ALL_L1_TYPES:
        query = build_articles_hard_filter_sql(
            subject_type=subject_type,
            relations=relations,
            articles_table=SYNTH_ARTICLES_TABLE,
            series_dedup=True,
        )
        result = fetch_articles_hard_filtered(conn, query)
        counts[subject_type] = len(result)
        if not result:
            empty_types.append(subject_type)
        # Direct proof the rail is competitor-clean, not just non-empty.
        excluded = relations[subject_type].exclude_same
        if excluded:
            assert all(c.type != subject_type for c in result), f"{subject_type} rail leaked a same-type competitor"

    assert not empty_types, f"empty rail(s) for subject type(s): {empty_types} -- counts: {counts}"


def test_no_empty_rail_holds_even_with_quality_floor_applied(conn, relations):
    """Repeats the same assertion with the real `engine.quality_scores`
    floor active (this sample's real ids DO have real quality scores --
    E2.6 scored all 4,772 articles) to prove the two real filters
    (competitor + quality) compose without starving the rail together,
    not just individually."""
    _build_500_sample(conn)
    for subject_type in ALL_L1_TYPES:
        query = build_articles_hard_filter_sql(
            subject_type=subject_type,
            relations=relations,
            articles_table=SYNTH_ARTICLES_TABLE,
            series_dedup=True,
            quality_floor=0.35,
        )
        result = fetch_articles_hard_filtered(conn, query)
        assert result, f"empty rail for {subject_type} once the real quality floor is applied"
