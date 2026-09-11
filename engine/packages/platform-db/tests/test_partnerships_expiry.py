"""E4.1 acceptance criterion: "Expiry is query-time, proven by test -- no
batch job." Runs against the real local platform DB (docker, per the task
brief: "Docker and Postgres are running; no env vars needed") rather than
mocking Postgres -- the whole point being proven is DB-level behavior
(`engine.partnerships_active` / `engine.partnership_is_effective`), not
Python logic, so a real connection is the only thing that can actually
prove it.

Every test wraps its work in a transaction that is rolled back in a
fixture teardown, so this suite never leaves rows behind in `now_platform`
regardless of pass/fail -- same idempotency expectation as the rest of
this package's tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from now_platform_db.settings import platform_database_url


@pytest.fixture
def conn():
    engine = create_engine(platform_database_url())
    connection = engine.connect()
    trans = connection.begin()
    try:
        yield connection
    finally:
        trans.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def test_site_id(conn):
    row = conn.execute(text("SELECT id FROM engine.sites WHERE slug = 'test'")).fetchone()
    assert row is not None, "expected the seeded 'test' site (engine.sites) to exist"
    return row[0]


@pytest.fixture
def org_id(conn):
    return conn.execute(
        text(
            "INSERT INTO engine.orgs (name, slug) VALUES (:name, :slug) RETURNING id"
        ),
        {"name": "Expiry Test Org", "slug": f"expiry-test-org-{uuid.uuid4().hex[:8]}"},
    ).scalar_one()


def _insert_partnership(conn, *, org_id=None, place_id=None, site_id, status="active", starts_at=None, ends_at=None, tier="paid"):
    return conn.execute(
        text(
            """
            INSERT INTO engine.partnerships (org_id, place_id, site_id, tier, status, starts_at, ends_at)
            VALUES (:org_id, :place_id, :site_id, :tier, :status, :starts_at, :ends_at)
            RETURNING id
            """
        ),
        {
            "org_id": org_id,
            "place_id": place_id,
            "site_id": site_id,
            "tier": tier,
            "status": status,
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
    ).scalar_one()


def test_expired_partnership_is_inactive_at_query_time_with_no_job(conn, org_id, test_site_id):
    """The core claim: a partnership whose `ends_at` is in the past reads
    as inactive immediately, purely because a SELECT ran -- no cron, no
    UPDATE, no status-flipping job of any kind touches this row between
    INSERT and the assertions below."""
    now = datetime.now(timezone.utc)
    partnership_id = _insert_partnership(
        conn,
        org_id=org_id,
        site_id=test_site_id,
        status="active",  # nobody manually ended it -- expiry must not depend on this being flipped
        starts_at=now - timedelta(days=30),
        ends_at=now - timedelta(days=1),
    )

    # The raw column still says 'active' -- proves the fix isn't "a job
    # updates status", it's "the read computes liveness".
    raw_status = conn.execute(
        text("SELECT status FROM engine.partnerships WHERE id = :id"), {"id": partnership_id}
    ).scalar_one()
    assert raw_status == "active"

    is_effective = conn.execute(
        text(
            "SELECT engine.partnership_is_effective(status, starts_at, ends_at) "
            "FROM engine.partnerships WHERE id = :id"
        ),
        {"id": partnership_id},
    ).scalar_one()
    assert is_effective is False

    active_view_count = conn.execute(
        text("SELECT count(*) FROM engine.partnerships_active WHERE id = :id"),
        {"id": partnership_id},
    ).scalar_one()
    assert active_view_count == 0


def test_effective_partnership_appears_active(conn, org_id, test_site_id):
    now = datetime.now(timezone.utc)
    partnership_id = _insert_partnership(
        conn,
        org_id=org_id,
        site_id=test_site_id,
        status="active",
        starts_at=now - timedelta(days=1),
        ends_at=None,  # open-ended
    )

    is_effective = conn.execute(
        text(
            "SELECT engine.partnership_is_effective(status, starts_at, ends_at) "
            "FROM engine.partnerships WHERE id = :id"
        ),
        {"id": partnership_id},
    ).scalar_one()
    assert is_effective is True

    active_view_count = conn.execute(
        text("SELECT count(*) FROM engine.partnerships_active WHERE id = :id"),
        {"id": partnership_id},
    ).scalar_one()
    assert active_view_count == 1


def test_not_yet_started_partnership_is_inactive(conn, org_id, test_site_id):
    now = datetime.now(timezone.utc)
    partnership_id = _insert_partnership(
        conn,
        org_id=org_id,
        site_id=test_site_id,
        status="active",
        starts_at=now + timedelta(days=7),  # scheduled, not live yet
        ends_at=None,
    )
    active_view_count = conn.execute(
        text("SELECT count(*) FROM engine.partnerships_active WHERE id = :id"),
        {"id": partnership_id},
    ).scalar_one()
    assert active_view_count == 0


def test_paused_status_overrides_time_window(conn, org_id, test_site_id):
    """A manually paused deal must not read as active even mid-window --
    query-time expiry augments the status flag, it doesn't replace it."""
    now = datetime.now(timezone.utc)
    partnership_id = _insert_partnership(
        conn,
        org_id=org_id,
        site_id=test_site_id,
        status="paused",
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=30),
    )
    active_view_count = conn.execute(
        text("SELECT count(*) FROM engine.partnerships_active WHERE id = :id"),
        {"id": partnership_id},
    ).scalar_one()
    assert active_view_count == 0


def test_as_of_a_past_instant_before_expiry(conn, org_id, test_site_id):
    """`partnership_is_effective` takes an explicit `at` for exactly the
    audit/billing-dispute question `partnership_audit` exists to answer:
    was this deal live at some specific past moment, independent of
    whether it's live right now."""
    now = datetime.now(timezone.utc)
    partnership_id = _insert_partnership(
        conn,
        org_id=org_id,
        site_id=test_site_id,
        status="active",
        starts_at=now - timedelta(days=30),
        ends_at=now - timedelta(days=1),
    )
    was_effective = conn.execute(
        text(
            "SELECT engine.partnership_is_effective(status, starts_at, ends_at, :at) "
            "FROM engine.partnerships WHERE id = :id"
        ),
        {"id": partnership_id, "at": now - timedelta(days=15)},
    ).scalar_one()
    assert was_effective is True


def test_exactly_one_of_org_or_place_is_enforced(conn, org_id, test_site_id):
    """Each bad insert runs inside its own SAVEPOINT (`begin_nested`) so the
    CHECK violation -- which aborts the current subtransaction in Postgres,
    same as any other error -- only rolls back that savepoint, leaving the
    fixture's outer transaction (and the org_id it created) usable for the
    next assertion."""
    savepoint = conn.begin_nested()
    with pytest.raises(Exception, match="ck_partnerships_org_xor_place"):
        _insert_partnership(conn, org_id=org_id, place_id=uuid.uuid4(), site_id=test_site_id, status="active")
    savepoint.rollback()

    savepoint = conn.begin_nested()
    with pytest.raises(Exception, match="ck_partnerships_org_xor_place"):
        _insert_partnership(conn, org_id=None, place_id=None, site_id=test_site_id, status="active")
    savepoint.rollback()
