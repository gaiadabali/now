"""Shared fixtures for this package's real-Postgres integration tests.
READ-ONLY against `now_jakarta`'s Payload-owned tables; synthetic data
lives exclusively in session-scoped `now_filters_synth_*`/
`now_rails_synth_*` temp tables (dropped automatically when the connection
closes). Matches `now-search`/`now-filters`/`now-blender`'s existing
convention. Every test using these fixtures skips cleanly (not a failure)
if the relevant DB is unreachable.
"""

from __future__ import annotations

import pytest
from now_filters.type_relations import load_type_relations
from sqlalchemy import text

from now_rails.connections import city_engine, platform_engine

CITY_DB_REF = "now_jakarta"
PLATFORM_SITE_SLUG = "jakarta"


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
        yield c
        # No commit -- rail_cache writes in individual tests use their own
        # explicit rollback-scoped connection (see test_cache.py) so a
        # test never leaves synthetic cache rows behind in a real table.


@pytest.fixture()
def relations(city_conn):
    return load_type_relations(city_conn)


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
    with platform_eng.connect() as c:
        yield c
