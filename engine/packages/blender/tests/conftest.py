"""Shared fixtures for this package's real-Postgres integration tests.
READ-ONLY against `now_jakarta`'s Payload-owned tables and the platform
DB's `engine.sites` (this package's own `weights.py`/`platform.py` writes
are exercised in tests only against the seeded `blend`/`decay` keys via
explicit, reverted transactions -- see `test_weights_integration.py`).
Matches `now-search`/`now-filters`'s existing convention. Every test
using these fixtures skips cleanly (not a failure) if the relevant DB is
unreachable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from now_blender.connections import city_engine, platform_engine

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
