"""Real-Postgres tests for the facet-count mechanism.

**Honest expectation, stated in facets.py's module docstring too**:
`primary_type`/`format` are NULL on every row and `engine.entity_terms`
has 0 rows as of this ticket (E2.1/E2.2 haven't run). So these tests
prove the *mechanism* -- one round trip, correct SQL, "apply every
filter except F" semantics -- using the real (degenerate) data plus one
synthetic ActiveFilter, not a rich real facet distribution. That's the
task brief's own framing: "build the mechanism, and say plainly that
it's unexercised."
"""

from __future__ import annotations

from sqlalchemy import text

from now_search.facets import ActiveFilter, compute_facet_counts


def _some_article_ids(conn, n: int = 50) -> list[int]:
    rows = conn.execute(text("SELECT id FROM public.articles ORDER BY id LIMIT :n"), {"n": n}).fetchall()
    return [r[0] for r in rows]


def test_returns_both_column_facets(conn):
    ids = _some_article_ids(conn)
    counts = compute_facet_counts(conn, candidate_ids=ids)
    assert set(counts.keys()) == {"type", "format"}


def test_current_real_data_is_all_null_bucket(conn):
    """Documents the exact "unexercised" state: every candidate falls
    into the single NULL bucket for both column facets today."""
    ids = _some_article_ids(conn, n=200)
    counts = compute_facet_counts(conn, candidate_ids=ids)
    assert counts["type"] == {"null": len(ids)}
    assert counts["format"] == {"null": len(ids)}


def test_empty_candidate_set_returns_empty_facets(conn):
    counts = compute_facet_counts(conn, candidate_ids=[])
    assert counts == {"type": {}, "format": {}}


def test_active_filter_on_one_facet_narrows_the_other_but_not_itself(conn):
    """'Apply every filter except F': filtering by type=stay should not
    change type's own counts (its own filter is excluded when counting
    itself) but SHOULD be applied when counting format. Since every row
    is NULL today, both facets narrow to the synthetic filter's
    (non-matching) value -- i.e. to zero -- which is exactly correct
    behaviour for a filter value that matches nothing yet, and proves
    the filter clause is actually wired into the format branch's WHERE,
    not silently ignored."""
    ids = _some_article_ids(conn, n=200)
    counts = compute_facet_counts(
        conn, candidate_ids=ids, active_filters=[ActiveFilter(facet="type", values=("stay",))]
    )
    # type's own count ignores its own active filter -> still the real distribution (all null).
    assert counts["type"] == {"null": len(ids)}
    # format's count DOES apply the active type=stay filter -> no row currently has type='stay', so 0 rows.
    assert counts["format"] == {}


def test_term_facet_mechanism_runs_and_is_empty_today(conn):
    """engine.entity_terms has 0 rows as of E3.1 -- this proves the term-facet
    query path executes without error against real Postgres and correctly
    reports "no data" rather than erroring."""
    ids = _some_article_ids(conn, n=50)
    fake_term_ids = [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    counts = compute_facet_counts(
        conn, candidate_ids=ids, term_facet_term_ids={"cuisine": fake_term_ids}
    )
    assert counts["cuisine"] == {}
