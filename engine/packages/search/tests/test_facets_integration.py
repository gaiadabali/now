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

import pytest
from sqlalchemy import text

from now_search.facets import ActiveFilter, compute_facet_counts


def _some_article_ids(conn, n: int = 50) -> list[int]:
    rows = conn.execute(text("SELECT id FROM public.articles ORDER BY id LIMIT :n"), {"n": n}).fetchall()
    return [r[0] for r in rows]


def test_returns_both_column_facets(conn):
    ids = _some_article_ids(conn)
    counts = compute_facet_counts(conn, candidate_ids=ids)
    assert set(counts.keys()) == {"type", "format"}


def test_counts_partition_the_candidate_set(conn):
    """Every candidate lands in exactly one bucket per column facet.

    This replaces an assertion that every row was in the `null` bucket --
    true when E3.1 was written, false now that E2 classification has run
    (jakarta: 3,589 of 4,772 articles carry a `primary_type`). Pinning a
    snapshot of the corpus made this test fail on *progress*, so what it
    checks now is the property that does not expire: the buckets are a
    partition, and `null` is surfaced as a real bucket rather than
    dropped.
    """
    ids = _some_article_ids(conn, n=200)
    counts = compute_facet_counts(conn, candidate_ids=ids)
    for facet in ("type", "format"):
        assert sum(counts[facet].values()) == len(ids), f"{facet} buckets do not partition the candidates"


def test_empty_candidate_set_returns_empty_facets(conn):
    counts = compute_facet_counts(conn, candidate_ids=[])
    assert counts == {"type": {}, "format": {}}


def test_active_filter_on_one_facet_narrows_the_other_but_not_itself(conn):
    """'Apply every filter except F'.

    Filtering by a `type` value must not change `type`'s own counts --
    otherwise the selected facet reports only what is already on screen,
    which tells a reader nothing about what switching to a sibling value
    would do -- but it MUST narrow `format`'s counts.

    Uses a type value drawn from the live corpus rather than a hardcoded
    one: this previously asserted `type=stay` matched nothing, which was
    a statement about E2 not having run yet, not about the code.
    """
    ids = _some_article_ids(conn, n=200)
    unfiltered = compute_facet_counts(conn, candidate_ids=ids)
    present = [v for v in unfiltered["type"] if v != "null"]
    if not present:
        pytest.skip("no classified articles in this sample -- nothing to filter by")
    chosen = present[0]

    counts = compute_facet_counts(
        conn, candidate_ids=ids, active_filters=[ActiveFilter(facet="type", values=(chosen,))]
    )
    # type's own count ignores its own active filter -> unchanged distribution.
    assert counts["type"] == unfiltered["type"]
    # format's count DOES apply it -> narrowed to exactly the chosen type's rows.
    assert sum(counts["format"].values()) == unfiltered["type"][chosen]


def test_term_facet_mechanism_runs_and_is_empty_today(conn):
    """Proves the term-facet query path executes against real Postgres and
    reports "no data" rather than erroring, for term ids that match
    nothing. (The `entity_terms has 0 rows` framing this carried is no
    longer true -- E2 has since written 17,237 rows -- but the ids used
    below are deliberately fake, so what is asserted still holds.)"""
    ids = _some_article_ids(conn, n=50)
    fake_term_ids = [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    counts = compute_facet_counts(
        conn, candidate_ids=ids, term_facet_term_ids={"cuisine": fake_term_ids}
    )
    assert counts["cuisine"] == {}
