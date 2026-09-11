"""Shared fixtures for this package's real-Postgres integration tests.

Matches `now-rails`/`now-filters`'s existing convention (see
`engine/packages/rails/tests/conftest.py`): every test using these
fixtures skips cleanly (not a failure) if the relevant DB is unreachable.

`place_mentions` is empty archive-wide (E2.3 is blocked on taxonomy
review -- PROGRESS.md), so there is no real mention data to resolve
against. This package is built and tested against **synthetic** data
instead, exactly as E3.2/E3.3/E3.5 did for their own blocked inputs:

  - City-side: a session-scoped **TEMP TABLE** `now_link_resolver_synth_places`
    shaped like `public.places` (id/org_id/slug/name), populated with
    made-up rows and dropped automatically when the connection closes --
    never a write against the real `public.places`. This is `now_filters`'s
    existing convention (see that package's `synthetic.py`): a table with a
    name distinct from any real one, read only when a test explicitly
    passes `places_table=SYNTH_PLACES_TABLE` to `resolve_mention`/
    `fetch_place` -- production code always defaults to the real
    `public.places` and never passes that argument.
  - Platform-side: real `engine.orgs` / `engine.partnerships` rows,
    inserted and read back inside **one connection's uncommitted
    transaction that is always rolled back**, per-test. Nothing is ever
    committed, so concurrent sessions touching the same platform DB (three
    other agents run concurrently per this ticket) never see this
    package's test fixtures, and nothing needs cleanup.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from now_link_resolver.connections import city_engine, platform_engine

CITY_DB_REF = "now_jakarta"
SYNTH_PLACES_TABLE = "now_link_resolver_synth_places"


@pytest.fixture(scope="module")
def city_eng():
    eng = city_engine(CITY_DB_REF)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"{CITY_DB_REF} unreachable: {exc}")
    yield eng
    eng.dispose()


@pytest.fixture()
def city_conn(city_eng):
    with city_eng.connect() as c:
        trans = c.begin()
        c.execute(text(f"DROP TABLE IF EXISTS {SYNTH_PLACES_TABLE}"))
        c.execute(
            text(
                f"""
                CREATE TEMP TABLE {SYNTH_PLACES_TABLE} (
                    id text PRIMARY KEY,
                    org_id text,
                    slug text NOT NULL,
                    name text NOT NULL
                )
                """
            )
        )
        yield c
        trans.rollback()  # belt-and-suspenders; TEMP + no commit already guarantees isolation


@pytest.fixture(scope="module")
def platform_eng():
    eng = platform_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"platform DB unreachable: {exc}")
    yield eng
    eng.dispose()


@pytest.fixture()
def platform_conn(platform_eng):
    """Real `engine.orgs`/`engine.partnerships` tables, one uncommitted
    transaction per test, always rolled back -- never visible to any
    other session, never needing cleanup."""
    with platform_eng.connect() as c:
        trans = c.begin()
        yield c
        trans.rollback()


@pytest.fixture()
def site_id(platform_conn) -> str:
    """A real site row must exist (partnerships.site_id FKs to
    engine.sites). Reuse the jakarta site created by E0/E4.1 if present;
    otherwise insert a throwaway one inside this test's own rolled-back
    transaction."""
    row = platform_conn.execute(
        text("SELECT id::text FROM engine.sites WHERE slug = 'jakarta' LIMIT 1")
    ).first()
    if row is not None:
        return row[0]
    new_id = str(uuid.uuid4())
    platform_conn.execute(
        text(
            """
            INSERT INTO engine.sites (id, slug, hostname, name, locale, timezone, currency, db_ref, status)
            VALUES (:id, :slug, :hostname, :name, 'id-ID', 'Asia/Jakarta', 'IDR', :db_ref, 'active')
            """
        ),
        {
            "id": new_id,
            "slug": f"now-link-resolver-test-{new_id[:8]}",
            "hostname": f"test-{new_id[:8]}.example.invalid",
            "name": "link-resolver test site",
            "db_ref": CITY_DB_REF,
        },
    )
    return new_id


def make_org(conn, *, name: str = "Test Org") -> str:
    org_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO engine.orgs (id, name, slug) VALUES (:id, :name, :slug)"
        ),
        {"id": org_id, "name": name, "slug": f"test-org-{org_id[:8]}"},
    )
    return org_id


def make_partnership(
    conn,
    *,
    site_id: str,
    tier: str,
    org_id: str | None = None,
    place_id: str | None = None,
    status: str = "active",
    starts_at: str | None = None,
    ends_at: str | None = None,
    custom_url: str | None = None,
    show_badge: bool = False,
    badge_label: str | None = None,
) -> str:
    partnership_id = str(uuid.uuid4())
    conn.execute(
        text(
            """
            INSERT INTO engine.partnerships
                (id, org_id, place_id, site_id, tier, status, starts_at, ends_at,
                 custom_url, show_badge, badge_label)
            VALUES
                (:id, :org_id, :place_id, :site_id, :tier, :status, :starts_at, :ends_at,
                 :custom_url, :show_badge, :badge_label)
            """
        ),
        {
            "id": partnership_id,
            "org_id": org_id,
            "place_id": place_id,
            "site_id": site_id,
            "tier": tier,
            "status": status,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "custom_url": custom_url,
            "show_badge": show_badge,
            "badge_label": badge_label,
        },
    )
    return partnership_id


def make_place(conn, *, place_id: str | None = None, org_id: str | None = None, slug: str, name: str) -> str:
    place_id = place_id or str(uuid.uuid4())
    conn.execute(
        text(
            f"INSERT INTO {SYNTH_PLACES_TABLE} (id, org_id, slug, name) "
            "VALUES (:id, :org_id, :slug, :name)"
        ),
        {"id": place_id, "org_id": org_id, "slug": slug, "name": name},
    )
    return place_id
