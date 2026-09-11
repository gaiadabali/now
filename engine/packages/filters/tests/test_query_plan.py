"""Sec.8.G: "push into SQL... constrain the vector search rather than
post-filtering." Real `EXPLAIN` output, asserted on, not just eyeballed --
so a future change that accidentally forces a sequential scan over
`places` fails CI instead of silently degrading p95."""

from __future__ import annotations

from sqlalchemy import text

from now_filters.hard import build_places_hard_filter_sql


def test_radius_predicate_uses_the_gist_index_not_a_seq_scan(conn, relations):
    """The one genuinely large-cardinality predicate this package issues
    (radius via PostGIS) must hit `ix_places_geo`
    (engine/packages/cms/src/migrations/20260908_140000_places_geography.ts)."""
    query = build_places_hard_filter_sql(
        subject_type="stay", relations=relations, center_lat=-6.22, center_lng=106.80, radius_m=2000
    )
    plan_rows = conn.execute(text("EXPLAIN " + query.sql), query.params).fetchall()
    plan_text = "\n".join(r[0] for r in plan_rows)
    # The property that matters is "not a sequential scan". Which index the
    # planner picks is its business: since F51 added `ix_places_status_type`,
    # at 177 rows it may reasonably prefer that over `ix_places_geo` and then
    # filter by distance. Asserting a specific index here would be testing the
    # planner's cost model rather than our query shape.
    assert "Seq Scan on places" not in plan_text, f"radius query fell back to a sequential scan:\n{plan_text}"
    assert ("ix_places_geo" in plan_text) or ("ix_places_status_type" in plan_text), (
        f"expected an index scan on places, got neither index:\n{plan_text}"
    )


def test_status_and_type_predicates_use_the_composite_index(conn, relations):
    """F51 (closed): `public.places` now has `ix_places_status_type`.

    This test previously asserted the OPPOSITE -- it pinned the missing-index
    state as a deliberate trip-wire so it would fail loudly the day someone
    added the index. That is exactly what happened, so the assertion is now
    inverted rather than deleted: it keeps guarding the same property (that
    §8.G's "push selective filters into SQL" is actually index-supported),
    just from the correct side of the fix.
    """
    query = build_places_hard_filter_sql(subject_type="stay", relations=relations)  # no radius -- isolates status/type
    plan_rows = conn.execute(text("EXPLAIN " + query.sql), query.params).fetchall()
    plan_text = "\n".join(r[0] for r in plan_rows)
    assert "Seq Scan on places" not in plan_text, (
        "status/type predicates fell back to a sequential scan despite ix_places_status_type:\n" + plan_text
    )
