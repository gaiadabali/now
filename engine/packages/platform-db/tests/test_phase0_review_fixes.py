"""Independent review of PR #58 (Phase 0 foundations) found two more
data-integrity gaps beyond the F6/F7 role-name and RLS-on-views issues
(see `test_rls_site_isolation.py` for those). This file proves the fixes:

  1. `print_orders`/`print_subscriptions` no longer have a `NOT NULL` on
     `identity_id` that contradicted `ON DELETE SET NULL`/P2.9's
     anonymise-on-delete promise. "No guest checkout" (§11a.5) is now
     enforced by a `BEFORE INSERT` trigger instead, which cannot conflict
     with the system `UPDATE` that `ON DELETE SET NULL` performs.
  2. `voucher_claims`' per-reader cap is enforced by a `BEFORE INSERT`
     trigger that locks the referenced `offers` row, closing a race where
     two concurrent claims could both pass an app-level "count, then
     insert" check.

Most of this file follows `test_rls_site_isolation.py`'s convention
(one transaction, opened by the connecting superuser, rolled back at
teardown — safe against a real, shared `now_platform`). The one
exception is `test_voucher_claims_concurrent_race_is_serialized`: proving
a real cross-connection lock requires two independent, committed
transactions that can each see the other's row — which a single
rolled-back transaction cannot provide (nothing is visible outside it to
a second connection). That test therefore creates and migrates its own
scratch database, commits real rows to it, and drops it again at
teardown — the same "scratch DB for a from-real-commits proof" pattern
this ticket's safety rules ask for, never touching `now_platform`.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def _make_paid_partnership(conn, *, org_id: str, site_id: str) -> str:
    return conn.execute(
        text(
            """
            INSERT INTO engine.partnerships (org_id, site_id, tier, status)
            VALUES (:org_id, :site_id, 'paid', 'active')
            RETURNING id
            """
        ),
        {"org_id": org_id, "site_id": site_id},
    ).scalar_one()


def _make_offer(conn, *, partnership_id: str, site_id: str, per_reader_cap: int = 1) -> str:
    now = datetime.now(timezone.utc)
    return conn.execute(
        text(
            """
            INSERT INTO engine.offers
                (partnership_id, site_id, title, kind, redemption_mode, valid_from, valid_to, per_reader_cap)
            VALUES
                (:partnership_id, :site_id, 'Test offer', 'percent_off', 'shared_code', :vf, :vt, :cap)
            RETURNING id
            """
        ),
        {
            "partnership_id": partnership_id,
            "site_id": site_id,
            "vf": now - timedelta(days=1),
            "vt": now + timedelta(days=30),
            "cap": per_reader_cap,
        },
    ).scalar_one()


def _make_identity(conn) -> str:
    return conn.execute(
        text("INSERT INTO engine.identities (email, email_norm) VALUES (:e, :e) RETURNING id"),
        {"e": f"phase0-review-{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()


def _make_print_order(conn, *, site_id: str, identity_id: str | None) -> str:
    return conn.execute(
        text(
            """
            INSERT INTO engine.print_orders
                (identity_id, site_id, email, email_norm, status,
                 subtotal_idr, shipping_idr, total_idr, delivery)
            VALUES
                (:identity_id, :site_id, 'review-fix-test@example.test', 'review-fix-test@example.test',
                 'pending_payment', 50000, 20000, 70000, '{}'::jsonb)
            RETURNING id
            """
        ),
        {"identity_id": identity_id, "site_id": site_id},
    ).scalar_one()


def _make_print_plan(conn, *, site_id: str) -> str:
    return conn.execute(
        text(
            """
            INSERT INTO engine.print_plans (site_id, kind, price_idr, delivery_zone)
            VALUES (:site_id, 'single_issue', 50000, 'bali')
            RETURNING id
            """
        ),
        {"site_id": site_id},
    ).scalar_one()


def _make_print_subscription(conn, *, site_id: str, identity_id: str | None, plan_id: str) -> str:
    return conn.execute(
        text(
            """
            INSERT INTO engine.print_subscriptions
                (identity_id, site_id, plan_id, status, issues_total,
                 starts_with_issue, ends_after_issue, delivery)
            VALUES
                (:identity_id, :site_id, :plan_id, 'active', 6,
                 '2026-10-01', '2027-04-01', '{}'::jsonb)
            RETURNING id
            """
        ),
        {"identity_id": identity_id, "site_id": site_id, "plan_id": plan_id},
    ).scalar_one()


@pytest.fixture
def site_and_offer(conn):
    site_id = _make_site(conn, "reviewfix")
    org_id = _make_org(conn, "ReviewFixOrg")
    partnership_id = _make_paid_partnership(conn, org_id=org_id, site_id=site_id)
    offer_id = _make_offer(conn, partnership_id=partnership_id, site_id=site_id)
    return {"site_id": site_id, "org_id": org_id, "partnership_id": partnership_id, "offer_id": offer_id}


# --- 1. print_orders/print_subscriptions: nullable identity_id, trigger-enforced ---


def test_print_order_requires_identity_at_creation(conn, site_and_offer):
    """§11a.5, enforced at INSERT — a guest-checkout attempt is rejected,
    not silently allowed by a nullable column."""
    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="no guest checkout"):
        _make_print_order(conn, site_id=site_and_offer["site_id"], identity_id=None)
    savepoint.rollback()


def test_print_subscription_requires_identity_at_creation(conn, site_and_offer):
    plan_id = _make_print_plan(conn, site_id=site_and_offer["site_id"])
    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="no guest checkout"):
        _make_print_subscription(conn, site_id=site_and_offer["site_id"], identity_id=None, plan_id=plan_id)
    savepoint.rollback()


def test_deleting_identity_anonymises_print_order_and_subscription(conn, site_and_offer):
    """The bug this fixes: identity_id was NOT NULL with ON DELETE SET NULL
    (print_orders) or ON DELETE RESTRICT (print_subscriptions) — deleting a
    reader who had ever bought print either failed with a not-null
    violation or was blocked outright. Both must now succeed and leave the
    finance record behind, anonymised, per P2.9."""
    site_id = site_and_offer["site_id"]
    identity_id = _make_identity(conn)
    plan_id = _make_print_plan(conn, site_id=site_id)
    order_id = _make_print_order(conn, site_id=site_id, identity_id=identity_id)
    subscription_id = _make_print_subscription(conn, site_id=site_id, identity_id=identity_id, plan_id=plan_id)

    # The actual proof: this must not raise.
    conn.execute(text("DELETE FROM engine.identities WHERE id = :id"), {"id": identity_id})

    order_identity = conn.execute(
        text("SELECT identity_id FROM engine.print_orders WHERE id = :id"), {"id": order_id}
    ).scalar_one()
    subscription_identity = conn.execute(
        text("SELECT identity_id FROM engine.print_subscriptions WHERE id = :id"), {"id": subscription_id}
    ).scalar_one()
    assert order_identity is None
    assert subscription_identity is None

    # The rows themselves survive — this is anonymisation, not erasure.
    assert conn.execute(text("SELECT count(*) FROM engine.print_orders WHERE id = :id"), {"id": order_id}).scalar_one() == 1
    assert (
        conn.execute(
            text("SELECT count(*) FROM engine.print_subscriptions WHERE id = :id"), {"id": subscription_id}
        ).scalar_one()
        == 1
    )


# --- 2. voucher_claims per-reader cap, enforced by a locking trigger ---


def test_voucher_claim_trigger_rejects_over_cap(conn, site_and_offer):
    """Sequential proof (one connection): the trigger itself rejects a
    second claim once the cap (1, this offer's default) is reached — the
    non-concurrent half of the fix. See
    test_voucher_claims_concurrent_race_is_serialized below for the actual
    race this trigger exists to close."""
    identity_id = _make_identity(conn)
    offer_id = site_and_offer["offer_id"]
    now = datetime.now(timezone.utc)

    conn.execute(
        text(
            "INSERT INTO engine.voucher_claims (offer_id, identity_id, status, expires_at) "
            "VALUES (:offer_id, :identity_id, 'claimed', :expires_at)"
        ),
        {"offer_id": offer_id, "identity_id": identity_id, "expires_at": now + timedelta(hours=72)},
    )

    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="already at the per-reader cap"):
        conn.execute(
            text(
                "INSERT INTO engine.voucher_claims (offer_id, identity_id, status, expires_at) "
                "VALUES (:offer_id, :identity_id, 'claimed', :expires_at)"
            ),
            {"offer_id": offer_id, "identity_id": identity_id, "expires_at": now + timedelta(hours=72)},
        )
    savepoint.rollback()

    count = conn.execute(
        text(
            "SELECT count(*) FROM engine.voucher_claims "
            "WHERE offer_id = :offer_id AND identity_id = :identity_id"
        ),
        {"offer_id": offer_id, "identity_id": identity_id},
    ).scalar_one()
    assert count == 1


def test_voucher_claim_trigger_rejects_unknown_offer(conn, site_and_offer):
    """The trigger's own guard against a not-yet-existing offer (NOT FOUND
    branch) — otherwise a bad offer_id would read `cap` as NULL and the
    `existing_claims >= cap` comparison would silently be NULL (neither
    true nor false), letting the INSERT through with no cap enforced at
    all."""
    identity_id = _make_identity(conn)
    savepoint = conn.begin_nested()
    with pytest.raises(DBAPIError, match="does not reference an existing offer"):
        conn.execute(
            text(
                "INSERT INTO engine.voucher_claims (offer_id, identity_id, status, expires_at) "
                "VALUES (:offer_id, :identity_id, 'claimed', now() + interval '1 hour')"
            ),
            {"offer_id": str(uuid.uuid4()), "identity_id": identity_id},
        )
    savepoint.rollback()


# --- The real concurrency proof: two independent, committed connections ---

_MIGRATIONS_ROOT = Path(__file__).resolve().parents[1] / "src" / "now_platform_db" / "migrations"
_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _migrate_to_head(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_MIGRATIONS_ROOT))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


@pytest.fixture
def voucher_race_scratch_db():
    """A private, from-empty scratch database for the one test that needs
    real, cross-connection-visible commits. Created and migrated here,
    dropped at teardown regardless of outcome — `now_platform` and every
    city database are untouched by this fixture."""
    admin_engine = create_engine(platform_database_url().rsplit("/", 1)[0] + "/postgres")
    db_name = f"now_platform_voucher_race_scratch_{uuid.uuid4().hex[:8]}"
    with admin_engine.connect() as admin_conn:
        admin_conn.execution_options(isolation_level="AUTOCOMMIT").execute(text(f'CREATE DATABASE "{db_name}"'))
    scratch_url = platform_database_url().rsplit("/", 1)[0] + f"/{db_name}"
    try:
        _migrate_to_head(scratch_url)
        yield scratch_url
    finally:
        admin_engine.dispose()
        # A fresh admin connection: `DROP DATABASE` must run outside any
        # transaction and cannot run on a connection that ever touched the
        # target database.
        admin_engine2 = create_engine(platform_database_url().rsplit("/", 1)[0] + "/postgres")
        with admin_engine2.connect() as admin_conn:
            admin_conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
            )
        admin_engine2.dispose()


def test_voucher_claims_concurrent_race_is_serialized(voucher_race_scratch_db):
    """The actual bug: without a lock, two concurrent claims for the same
    (offer, identity) can both run the app-level "count existing claims"
    check before either has inserted, both see zero, and both insert --
    a per_reader_cap=1 offer silently double-claimed. Proves the fix with
    two real threads, each its own connection and transaction, timed so
    the second one is genuinely blocked on the first's row lock (not
    merely running after it by accident of scheduling):

        T1: BEGIN; INSERT claim 1 (trigger locks the offer row, counts 0,
            inserts) -- HOLDS the lock, does not commit yet.
        (main thread waits for T1's insert to complete, then gives T2 a
         moment to reach its own blocking SELECT ... FOR UPDATE)
        T2: BEGIN; INSERT claim 2 -- blocks inside Postgres on the offer
            row's lock, held by T1's still-open transaction.
        T1: COMMIT -- releases the lock.
        T2: unblocks, re-counts (now sees T1's committed claim), 1 >= cap
            of 1, the trigger raises. T2's INSERT fails.

    Exactly one claim exists afterward.
    """
    engine = create_engine(voucher_race_scratch_db)
    try:
        with engine.connect() as setup_conn:
            trans = setup_conn.begin()
            site_id = _make_site(setup_conn, "vouchrace")
            org_id = _make_org(setup_conn, "VoucherRaceOrg")
            partnership_id = _make_paid_partnership(setup_conn, org_id=org_id, site_id=site_id)
            offer_id = _make_offer(setup_conn, partnership_id=partnership_id, site_id=site_id, per_reader_cap=1)
            identity_id = _make_identity(setup_conn)
            trans.commit()  # must be visible to two OTHER connections

        results: dict[str, str] = {}
        t1_inserted = threading.Event()
        t1_may_commit = threading.Event()

        def worker_one():
            conn1 = engine.connect()
            trans1 = conn1.begin()
            try:
                conn1.execute(
                    text(
                        "INSERT INTO engine.voucher_claims (offer_id, identity_id, status, expires_at) "
                        "VALUES (:o, :i, 'claimed', now() + interval '1 hour')"
                    ),
                    {"o": offer_id, "i": identity_id},
                )
                results["t1"] = "inserted"
            except Exception as exc:  # pragma: no cover - would fail the test's own assertions below
                results["t1"] = f"error: {exc}"
                trans1.rollback()
                conn1.close()
                t1_inserted.set()
                return
            t1_inserted.set()
            # Hold the transaction (and the offer row's lock) open until
            # the main thread confirms T2 is genuinely blocked on it.
            t1_may_commit.wait(timeout=10)
            trans1.commit()
            conn1.close()

        def worker_two():
            t1_inserted.wait(timeout=10)
            conn2 = engine.connect()
            trans2 = conn2.begin()
            try:
                conn2.execute(
                    text(
                        "INSERT INTO engine.voucher_claims (offer_id, identity_id, status, expires_at) "
                        "VALUES (:o, :i, 'claimed', now() + interval '1 hour')"
                    ),
                    {"o": offer_id, "i": identity_id},
                )
                results["t2"] = "inserted"
                trans2.commit()
            except Exception as exc:
                results["t2"] = f"rejected: {exc}"
                trans2.rollback()
            finally:
                conn2.close()

        t1 = threading.Thread(target=worker_one)
        t2 = threading.Thread(target=worker_two)
        t1.start()
        t1_inserted.wait(timeout=10)
        t2.start()
        # Give worker_two time to actually reach its blocking SELECT ...
        # FOR UPDATE inside Postgres before we let worker_one commit --
        # otherwise this would just prove sequential ordering, not a real
        # lock wait.
        time.sleep(0.5)
        t1_may_commit.set()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert results.get("t1") == "inserted"
        assert results.get("t2", "").startswith("rejected:")
        assert "already at the per-reader cap" in results["t2"]

        with engine.connect() as check_conn:
            final_count = check_conn.execute(
                text(
                    "SELECT count(*) FROM engine.voucher_claims "
                    "WHERE offer_id = :o AND identity_id = :i"
                ),
                {"o": offer_id, "i": identity_id},
            ).scalar_one()
        assert final_count == 1
    finally:
        engine.dispose()
