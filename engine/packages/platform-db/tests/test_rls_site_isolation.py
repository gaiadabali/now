"""P0.4 (F6/F7) — proof that the runtime role cannot cross sites, cannot DDL,
and cannot write history it shouldn't, by actually switching role and
re-running the query, not by reading the policy SQL and trusting it.

Requires migrations through 0017 applied to whatever `platform_database_url()`
resolves to (see `now_platform_db.settings` — the project `.env` file by
default). Every test runs inside ONE transaction, opened by the `now`
superuser (or whichever role the connection URL names), which:

  1. inserts fixture rows (sites, an org, a partnership, ...) as the
     connecting role — a superuser bypasses RLS/grants unconditionally, so
     this setup step is unaffected by anything this migration set changed;
  2. `SET LOCAL ROLE now_runtime` (or `now_migrator`) to become that role
     for permission-checking purposes — `current_user` changes, RLS policies
     and GRANTs are evaluated against the *new* current_user, but the
     session/connection itself never re-authenticates, so no password is
     needed (a superuser may `SET ROLE` to any role without being a member
     of it — see PostgreSQL's `SET ROLE` docs);
  3. asserts, then `RESET ROLE`;
  4. the fixture's teardown rolls back the whole transaction, so nothing
     written here ever persists in the target database — same convention
     `test_partnerships_expiry.py` already uses, chosen deliberately for
     this suite too so it is safe to run against a real, shared
     `now_platform` and not only a scratch database.

This file was first run against a disposable `now_platform_p0_scratch`
database (migrated from empty to head) to prove the migration chain itself
before being run — successfully, same results — against the local
`now_platform` restored to schema-only state by the Phase 0 restart. See
this ticket's PR description for both runs' output.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

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


def _make_site(conn, slug: str) -> str:
    return conn.execute(
        text(
            """
            INSERT INTO engine.sites (slug, hostname, name, timezone, currency, db_ref)
            VALUES (:slug, :slug || '.internal.test', :slug, 'UTC', 'USD', :slug)
            RETURNING id
            """
        ),
        {"slug": f"{slug}-{uuid.uuid4().hex[:8]}"},
    ).scalar_one()


def _make_org(conn, name: str) -> str:
    return conn.execute(
        text("INSERT INTO engine.orgs (name, slug) VALUES (:name, :slug) RETURNING id"),
        {"name": name, "slug": f"{name.lower()}-{uuid.uuid4().hex[:8]}"},
    ).scalar_one()


def _make_partnership(conn, *, org_id: str, site_id: str, tier: str = "paid") -> str:
    return conn.execute(
        text(
            """
            INSERT INTO engine.partnerships (org_id, site_id, tier, status)
            VALUES (:org_id, :site_id, :tier, 'active')
            RETURNING id
            """
        ),
        {"org_id": org_id, "site_id": site_id, "tier": tier},
    ).scalar_one()


def _make_offer(conn, *, partnership_id: str, site_id: str) -> str:
    now = datetime.now(timezone.utc)
    return conn.execute(
        text(
            """
            INSERT INTO engine.offers
                (partnership_id, site_id, title, kind, redemption_mode, valid_from, valid_to)
            VALUES
                (:partnership_id, :site_id, 'Test offer', 'percent_off', 'shared_code', :vf, :vt)
            RETURNING id
            """
        ),
        {"partnership_id": partnership_id, "site_id": site_id, "vf": now - timedelta(days=1), "vt": now + timedelta(days=30)},
    ).scalar_one()


def _make_print_order(conn, *, site_id: str, identity_id: str) -> str:
    return conn.execute(
        text(
            """
            INSERT INTO engine.print_orders
                (identity_id, site_id, email, email_norm, status,
                 subtotal_idr, shipping_idr, total_idr, delivery)
            VALUES
                (:identity_id, :site_id, 'rls-test@example.test', 'rls-test@example.test',
                 'pending_payment', 50000, 20000, 70000, '{}'::jsonb)
            RETURNING id
            """
        ),
        {"identity_id": identity_id, "site_id": site_id},
    ).scalar_one()


def _make_campaign(conn, *, org_id: str, site_id: str) -> str:
    return conn.execute(
        text("INSERT INTO engine.campaigns (org_id, site_id) VALUES (:org_id, :site_id) RETURNING id"),
        {"org_id": org_id, "site_id": site_id},
    ).scalar_one()


@pytest.fixture
def two_sites_with_paid_offers(conn):
    """One org, one paid partnership, one offer, per of two distinct sites."""
    bali_site = _make_site(conn, "bali")
    jkt_site = _make_site(conn, "jakarta")
    bali_org = _make_org(conn, "BaliOrg")
    jkt_org = _make_org(conn, "JktOrg")
    bali_partnership = _make_partnership(conn, org_id=bali_org, site_id=bali_site)
    jkt_partnership = _make_partnership(conn, org_id=jkt_org, site_id=jkt_site)
    bali_offer = _make_offer(conn, partnership_id=bali_partnership, site_id=bali_site)
    jkt_offer = _make_offer(conn, partnership_id=jkt_partnership, site_id=jkt_site)
    return {
        "bali_site": bali_site,
        "jkt_site": jkt_site,
        "bali_org": bali_org,
        "jkt_org": jkt_org,
        "bali_partnership": bali_partnership,
        "jkt_partnership": jkt_partnership,
        "bali_offer": bali_offer,
        "jkt_offer": jkt_offer,
    }


def _as_runtime(conn, site_id: str | None) -> None:
    conn.execute(text("SET LOCAL ROLE now_runtime"))
    # `SET`/`SET LOCAL` do not accept bind parameters in Postgres ("syntax
    # error at or near $1") -- the value has to be a literal in the
    # statement text. Safe here: every caller passes either None or a uuid
    # this test module generated itself (via gen_random_uuid()/our own
    # fixtures), never anything from outside the test.
    if site_id is None:
        conn.execute(text("RESET app.site_id"))
    else:
        conn.execute(text(f"SET LOCAL app.site_id = '{site_id}'"))


def test_runtime_sees_only_its_own_site_partnerships(conn, two_sites_with_paid_offers):
    f = two_sites_with_paid_offers
    _as_runtime(conn, f["bali_site"])
    rows = conn.execute(text("SELECT site_id FROM engine.partnerships")).fetchall()
    assert {str(r[0]) for r in rows} == {str(f["bali_site"])}
    conn.execute(text("RESET ROLE"))


def test_runtime_with_no_site_context_sees_nothing(conn, two_sites_with_paid_offers):
    """The fail-closed case: a query that forgot to SET app.site_id at all
    must see zero rows, not every site's rows and not an error."""
    _as_runtime(conn, None)
    rows = conn.execute(text("SELECT * FROM engine.partnerships")).fetchall()
    assert rows == []
    rows = conn.execute(text("SELECT * FROM engine.offers")).fetchall()
    assert rows == []
    conn.execute(text("RESET ROLE"))


def test_runtime_with_garbage_site_context_sees_nothing(conn, two_sites_with_paid_offers):
    """current_site_id() must fail closed on an unparseable value too, not
    raise an error the application code could mishandle."""
    conn.execute(text("SET LOCAL ROLE now_runtime"))
    conn.execute(text("SET LOCAL app.site_id = 'not-a-uuid'"))
    rows = conn.execute(text("SELECT * FROM engine.partnerships")).fetchall()
    assert rows == []
    conn.execute(text("RESET ROLE"))


def test_runtime_cannot_read_other_site_row_by_explicit_id(conn, two_sites_with_paid_offers):
    """Proves the isolation holds even for a direct-by-id lookup, not only
    an unfiltered SELECT * — the shape of bug this exists to survive."""
    f = two_sites_with_paid_offers
    _as_runtime(conn, f["bali_site"])
    row = conn.execute(
        text("SELECT id FROM engine.partnerships WHERE id = :id"), {"id": f["jkt_partnership"]}
    ).fetchone()
    assert row is None
    conn.execute(text("RESET ROLE"))


def test_runtime_cannot_insert_cross_site_row(conn, two_sites_with_paid_offers):
    f = two_sites_with_paid_offers
    _as_runtime(conn, f["bali_site"])
    # A Postgres error aborts the current (sub)transaction; a SAVEPOINT
    # keeps that damage from reaching the fixture's own outer transaction,
    # the same convention `test_partnerships_expiry.py` already uses.
    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="row-level security"):
        conn.execute(
            text(
                "INSERT INTO engine.campaigns (org_id, site_id) VALUES (:org_id, :site_id)"
            ),
            {"org_id": f["bali_org"], "site_id": f["jkt_site"]},
        )
    savepoint.rollback()
    conn.execute(text("RESET ROLE"))


def test_migrator_role_bypasses_rls_and_sees_every_site(conn, two_sites_with_paid_offers):
    f = two_sites_with_paid_offers
    conn.execute(text("SET LOCAL ROLE now_migrator"))
    rows = conn.execute(text("SELECT site_id FROM engine.partnerships")).fetchall()
    assert {str(r[0]) for r in rows} == {str(f["bali_site"]), str(f["jkt_site"])}
    conn.execute(text("RESET ROLE"))


def test_joined_policy_placements_scoped_via_campaign_site(conn, two_sites_with_paid_offers):
    """A table with no site_id column of its own (placements) is scoped
    correctly through its FK to campaigns."""
    f = two_sites_with_paid_offers
    bali_campaign = _make_campaign(conn, org_id=f["bali_org"], site_id=f["bali_site"])
    jkt_campaign = _make_campaign(conn, org_id=f["jkt_org"], site_id=f["jkt_site"])
    conn.execute(
        text("INSERT INTO engine.placements (campaign_id, surface, slot) VALUES (:c, 'home', 'rail-1')"),
        {"c": bali_campaign},
    )
    conn.execute(
        text("INSERT INTO engine.placements (campaign_id, surface, slot) VALUES (:c, 'home', 'rail-1')"),
        {"c": jkt_campaign},
    )
    _as_runtime(conn, f["bali_site"])
    rows = conn.execute(text("SELECT campaign_id FROM engine.placements")).fetchall()
    assert {str(r[0]) for r in rows} == {str(bali_campaign)}
    conn.execute(text("RESET ROLE"))


def test_joined_policy_voucher_claims_scoped_via_offer_site(conn, two_sites_with_paid_offers):
    f = two_sites_with_paid_offers
    identity_id = conn.execute(
        text("INSERT INTO engine.identities (email, email_norm) VALUES (:e, :e) RETURNING id"),
        {"e": f"rls-test-{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()
    now = datetime.now(timezone.utc)
    conn.execute(
        text(
            "INSERT INTO engine.voucher_claims (offer_id, identity_id, status, expires_at) "
            "VALUES (:offer_id, :identity_id, 'claimed', :expires_at)"
        ),
        {"offer_id": f["bali_offer"], "identity_id": identity_id, "expires_at": now + timedelta(hours=72)},
    )
    conn.execute(
        text(
            "INSERT INTO engine.voucher_claims (offer_id, identity_id, status, expires_at) "
            "VALUES (:offer_id, :identity_id, 'claimed', :expires_at)"
        ),
        {"offer_id": f["jkt_offer"], "identity_id": identity_id, "expires_at": now + timedelta(hours=72)},
    )
    _as_runtime(conn, f["jkt_site"])
    rows = conn.execute(text("SELECT offer_id FROM engine.voucher_claims")).fetchall()
    assert {str(r[0]) for r in rows} == {str(f["jkt_offer"])}
    conn.execute(text("RESET ROLE"))


def test_runtime_cannot_update_or_delete_append_only_ledgers(conn, two_sites_with_paid_offers):
    """Grant-level, not RLS-level: now_runtime has SELECT+INSERT on
    payment_events/offer_events/ad_events/partnership_audit/offer_audit and
    nothing else. Proven here on payment_events."""
    f = two_sites_with_paid_offers
    identity_id = conn.execute(
        text("INSERT INTO engine.identities (email, email_norm) VALUES (:e, :e) RETURNING id"),
        {"e": f"rls-ledger-{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()
    bali_order = _make_print_order(conn, site_id=f["bali_site"], identity_id=identity_id)
    payment_event_id = conn.execute(
        text(
            "INSERT INTO engine.payment_events (gateway, event_ref, order_id, kind, signature_ok, payload) "
            "VALUES ('simulated', :ref, :order_id, 'test', true, '{}'::jsonb) RETURNING id"
        ),
        {"ref": f"evt-{uuid.uuid4().hex[:8]}", "order_id": bali_order},
    ).scalar_one()

    _as_runtime(conn, f["bali_site"])
    # SELECT is granted and must work, and must see the row (it is
    # correctly attributed to a bali order, and we are in the bali site
    # context).
    seen = conn.execute(
        text("SELECT count(*) FROM engine.payment_events WHERE id = :id"), {"id": payment_event_id}
    ).scalar_one()
    assert seen == 1
    # INSERT is granted and must work, against the same bali order so the
    # RLS WITH CHECK (which requires a resolvable order_id) is satisfied too
    # -- this proves the grant, not a WITH CHECK false negative.
    conn.execute(
        text(
            "INSERT INTO engine.payment_events (gateway, event_ref, order_id, kind, signature_ok, payload) "
            "VALUES ('simulated', :ref, :order_id, 'test', true, '{}'::jsonb)"
        ),
        {"ref": f"evt-{uuid.uuid4().hex[:8]}", "order_id": bali_order},
    )
    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="permission denied"):
        conn.execute(
            text("UPDATE engine.payment_events SET kind = 'tampered' WHERE id = :id"),
            {"id": payment_event_id},
        )
    savepoint.rollback()
    conn.execute(text("RESET ROLE"))


def test_runtime_cannot_ddl_in_engine_schema(conn, two_sites_with_paid_offers):
    conn.execute(text("SET LOCAL ROLE now_runtime"))
    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="permission denied for schema engine"):
        conn.execute(text("CREATE TABLE engine.sabotage (id int)"))
    savepoint.rollback()
    conn.execute(text("RESET ROLE"))


def test_offers_require_paid_partnership_trigger(conn, two_sites_with_paid_offers):
    """Owner's ruling, §11a.1 — an offer against a non-paid partnership is
    rejected at the database layer, not only in application code."""
    f = two_sites_with_paid_offers
    listed_partnership = _make_partnership(conn, org_id=f["bali_org"], site_id=f["bali_site"], tier="listed")
    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="not a paid partnership"):
        _make_offer(conn, partnership_id=listed_partnership, site_id=f["bali_site"])
    savepoint.rollback()
