"""Shared fixtures for the real-Postgres integration tests in this
package. READ-ONLY against `now_jakarta`'s Payload-owned tables (never
INSERT/UPDATE/DELETE on `public.*`); synthetic data lives exclusively in
session-scoped `now_filters_synth_*` temp tables this package creates
(see `now_filters.synthetic`), torn down automatically when the
connection closes. Matches `now-search`'s existing convention (see
`engine/packages/search/tests/conftest.py`).

Every test using these fixtures skips cleanly (not a failure) if
`now_jakarta` is unreachable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from now_filters.connections import city_engine
from now_filters.type_relations import load_type_relations

DB_REF = "now_jakarta"


@pytest.fixture(scope="module")
def engine():
    eng = city_engine(DB_REF)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"{DB_REF} unreachable: {exc}")
    yield eng
    eng.dispose()


@pytest.fixture()
def conn(engine):
    with engine.connect() as c:
        yield c
        # No commit -- everything this package does against public.* is
        # read-only; synthetic `now_filters_synth_*` temp tables die with
        # the connection.


@pytest.fixture()
def relations(conn):
    return load_type_relations(conn)
