"""F27 (PROGRESS.md, launch-blocking): `status='pending_review'` places
must never surface. Two proofs:

1. Against REAL `now_jakarta.places` data (every row currently
   `status='pending_review'` -- originally 177 loader-seeded rows, now
   many more from E2.3's article-text extraction, all created with the
   same placeholder status; verified directly against this database --
   see module-level query below): the hard filter must return exactly
   zero candidates. This is not a synthetic scenario; it is today's live
   database state.
2. Against a SYNTHETIC mix of active/pending_review/closed places
   (needed because real data has no status variety to prove the *filter
   discriminates* rather than coincidentally returning zero for any
   reason): pending_review and closed rows must be excluded while
   active rows of the same type survive.
"""

from __future__ import annotations

from sqlalchemy import text

from now_filters.hard import build_places_hard_filter_sql, fetch_places_hard_filtered
from now_filters.synthetic import SYNTH_PLACES_TABLE, SyntheticPlace, create_synthetic_places_table


def test_real_places_table_is_currently_100pct_pending_review(conn):
    """Documents the live-data premise this test file is built on: EVERY
    real row in `public.places` is `status='pending_review'`, regardless
    of how many rows exist.

    The exact row count is deliberately NOT asserted here any more. It
    was hardcoded at 177 (the original loader-seeded set) until E2.3
    (place entity extraction + dedup) populated thousands more rows from
    article text -- every one of them created with the SAME
    `status='pending_review'` placeholder the original 177 already used
    (see `now-place-extraction`'s README/db.py), so the invariant this
    test actually protects (F27: nothing un-reviewed is rail-eligible)
    still holds. A hardcoded count would need editing every time E2.3 (or
    any future loader) re-runs and finds more mentions -- the 100%
    pending_review PROPERTY is what F27 needs verified live, not a
    specific row count frozen at one point in time.

    If this ever fails, it means something (E2.1 reclassification, or a
    manual edit) has flipped a real row to `active`/`closed` --
    `test_real_active_places_filter_returns_zero` below should be
    revisited at that point (it would no longer be proving F27 against
    100% pending_review data)."""
    row = conn.execute(
        text("SELECT count(*) AS n, count(*) FILTER (WHERE status = 'pending_review') AS pending FROM public.places")
    ).one()
    assert row.n > 0, "public.places is empty -- nothing for this test to prove"
    assert row.pending == row.n, f"{row.n - row.pending} row(s) are not pending_review -- F27 premise no longer holds"


def test_real_active_places_filter_returns_zero(conn, relations):
    """The F27 proof against real data: with `status='active'` enforced
    unconditionally, today's live `now_jakarta.places` table -- 100%
    `pending_review`, whatever the current row count -- yields zero
    candidates for every subject type. This is the guarantee: not "the
    filter looks correct", but "run against the actual current database,
    nothing pending_review comes back"."""
    for subject_type in ("stay", "eat", "drink", "wellness", "shop", "do", "event", "editorial", None):
        query = build_places_hard_filter_sql(subject_type=subject_type, relations=relations)
        rows = fetch_places_hard_filtered(conn, query)
        assert rows == [], f"pending_review place(s) surfaced for subject_type={subject_type!r}: {rows}"


def test_synthetic_status_discrimination(conn, relations):
    """Proves the filter actually discriminates on `status`, not merely
    that it happens to return zero. All three rows below share the same
    type (`eat`, a complement of `stay` -- never itself excluded by
    competitor logic for a `stay` subject), so the ONLY thing that can
    explain a row's absence from the result is its status."""
    rows = [
        SyntheticPlace(id=101, type="eat", status="active"),
        SyntheticPlace(id=102, type="eat", status="pending_review"),
        SyntheticPlace(id=103, type="eat", status="closed"),
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(subject_type="stay", relations=relations, places_table=SYNTH_PLACES_TABLE)
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert survivors == {101}


def test_f27_mislabelled_venue_scenario(conn, relations):
    """The exact scenario F27 describes: a real hotel that has not been
    reclassified yet and still wears the loader sentinel
    (`type='editorial'`). While it is `status='pending_review'` (today's
    real state for every row in `public.places`) it must not surface. If someone
    manually flips it to `status='active'` WITHOUT fixing its type first
    (a plausible operational mistake), this test demonstrates the second
    half of F27's warning: it survives the status gate and is then
    invisible to competitor exclusion in both directions (id=202 is not
    excluded from a `stay` page, since its type is `editorial`, not
    `stay`) -- proving status='active'-only is NOT a complete guarantee
    once bad data is marked active, only THE current guarantee against
    today's pending_review sentinel. This is exactly why the package
    recommendation (README) is a dedicated `unknown` type."""
    rows = [
        SyntheticPlace(id=201, type="editorial", status="pending_review"),  # today's real shape
        SyntheticPlace(id=202, type="editorial", status="active"),  # hypothetical operational mistake
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(subject_type="stay", relations=relations, places_table=SYNTH_PLACES_TABLE)
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert 201 not in survivors, "pending_review sentinel leaked through -- F27 enforcement broken"
    assert 202 in survivors, (
        "this assertion documents the residual gap, it is not a desired outcome: "
        "an *active* mislabelled place is NOT caught by status alone -- see README recommendation"
    )
