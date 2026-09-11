"""Event expiry and venue-status inheritance (Sec.8.A "Event expiry:
`ends_at < now()`" and "Venue closed: `place.status = closed`"). Real
data: 837 events, 329 with a populated `ends_at`, and (verified directly)
100% of those 329 are already in the past relative to 2026-09-09 -- so the
expiry predicate has real, live work to do. Closed-venue inheritance is
proven with a synthetic events+places pair since no real event currently
references a `closed`-status place."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from now_filters.hard import build_events_hard_filter_sql
from now_filters.synthetic import SYNTH_EVENTS_TABLE, SYNTH_PLACES_TABLE, SyntheticPlace, create_synthetic_places_table


def test_real_events_have_populated_and_expired_ends_at(conn):
    row = conn.execute(
        text(
            "SELECT count(*) AS total, count(ends_at) AS with_end, "
            "count(*) FILTER (WHERE ends_at < now()) AS expired FROM public.events"
        )
    ).one()
    assert row.total == 837
    assert row.with_end == 329
    assert row.expired == 329, "expected every populated ends_at to already be in the past for this corpus"


def test_expiry_filter_excludes_all_currently_expired_real_events(conn):
    query = build_events_hard_filter_sql()
    rows = conn.execute(text(query.sql), query.params).fetchall()
    surviving_ids = {r.id for r in rows}

    expired_ids = {
        r[0]
        for r in conn.execute(
            text("SELECT id FROM public.events WHERE ends_at IS NOT NULL AND ends_at < now()")
        ).fetchall()
    }
    assert surviving_ids.isdisjoint(expired_ids), "expired event(s) leaked through"


def test_real_no_end_date_events_are_all_draft_today(conn):
    """Documents the real premise precisely, rather than assuming it:
    verified directly, all 508 `ends_at IS NULL` rows in `now_jakarta`
    are `_status='draft'` (the legacy `upcoming-events` post type's
    missing-occurrence-date gap, ARCHITECTURE.md Sec.6, has not been
    published as-is) -- so `test_draft_events_never_surface` already
    covers today's real no-end-date rows via the status predicate, and
    `test_synthetic_no_end_date_published_event_is_not_treated_as_expired`
    below covers the code path this corpus does not currently exercise:
    a published event that legitimately has no end date must not be
    excluded merely for lacking one."""
    row = conn.execute(
        text(
            "SELECT count(*) FILTER (WHERE _status = 'published') AS published_no_end "
            "FROM public.events WHERE ends_at IS NULL"
        )
    ).one()
    assert row.published_no_end == 0


def test_synthetic_no_end_date_published_event_is_not_treated_as_expired(conn):
    conn.execute(text(f"DROP TABLE IF EXISTS {SYNTH_EVENTS_TABLE}"))
    conn.execute(
        text(
            f"CREATE TEMP TABLE {SYNTH_EVENTS_TABLE} (id int PRIMARY KEY, place_id int, ends_at timestamptz, _status text)"
        )
    )
    conn.execute(text(f"INSERT INTO {SYNTH_EVENTS_TABLE} VALUES (501, NULL, NULL, 'published')"))
    query = build_events_hard_filter_sql(events_table=SYNTH_EVENTS_TABLE)
    rows = conn.execute(text(query.sql), query.params).fetchall()
    assert {r.id for r in rows} == {501}


def test_draft_events_never_surface(conn):
    query = build_events_hard_filter_sql()
    rows = conn.execute(text(query.sql), query.params).fetchall()
    surviving_ids = {r.id for r in rows}
    draft_ids = {r[0] for r in conn.execute(text("SELECT id FROM public.events WHERE _status = 'draft'")).fetchall()}
    assert surviving_ids.isdisjoint(draft_ids)


def test_event_at_closed_or_pending_venue_never_surfaces(conn):
    """Synthetic: a closed venue and a pending_review (F27 sentinel)
    venue each host one non-expired, published event; a third event has
    no venue at all (standalone festival). Only the standalone and the
    active-venue events should survive."""
    places = [
        SyntheticPlace(id=301, type="event", status="active"),
        SyntheticPlace(id=302, type="event", status="closed"),
        SyntheticPlace(id=303, type="event", status="pending_review"),
    ]
    create_synthetic_places_table(conn, places)

    future = datetime.now(timezone.utc) + timedelta(days=30)
    conn.execute(text(f"DROP TABLE IF EXISTS {SYNTH_EVENTS_TABLE}"))
    conn.execute(
        text(
            f"CREATE TEMP TABLE {SYNTH_EVENTS_TABLE} "
            "(id int PRIMARY KEY, place_id int, ends_at timestamptz, published_at timestamptz, _status text)"
        )
    )
    rows = [
        (401, 301, future, future, "published"),  # active venue -- survives
        (402, 302, future, future, "published"),  # closed venue -- excluded
        (403, 303, future, future, "published"),  # pending_review venue -- excluded (F27)
        (404, None, future, future, "published"),  # standalone -- survives
    ]
    for r in rows:
        conn.execute(
            text(f"INSERT INTO {SYNTH_EVENTS_TABLE} VALUES (:id, :pid, :ea, :pa, :st)"),
            {"id": r[0], "pid": r[1], "ea": r[2], "pa": r[3], "st": r[4]},
        )

    query = build_events_hard_filter_sql(events_table=SYNTH_EVENTS_TABLE, places_table=SYNTH_PLACES_TABLE)
    result = conn.execute(text(query.sql), query.params).fetchall()
    surviving_ids = {r.id for r in result}
    assert surviving_ids == {401, 404}
