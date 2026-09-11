"""Shared fixtures for the real-Postgres integration tests in this
package. Unlike now-embeddings' integration test (which uses `now_test`,
a synthetic tenant with no Payload `public` schema), this package's
lexical/semantic retrieval is defined *in terms of* `public.articles`
and `engine.embeddings`/`engine.article_search` -- all only meaningfully
populated in `now_jakarta`.

`conn` (read-only) is for tests that only ever SELECT -- semantic search,
facet counts, RRF-adjacent reads. `write_conn` (this file, below) wraps a
connection in a transaction that is always rolled back at teardown, for
the F41 tsv-pipeline tests that legitimately need to INSERT/UPDATE/DELETE
`engine.article_search` rows (an `engine`-owned table this package's own
migration created, not a Payload-owned one) without leaving any trace on
the shared `now_jakarta` database other tests/agents also read.

Every test using these fixtures skips cleanly (not a failure) if
`now_jakarta` is unreachable, matching this monorepo's existing
convention (see now-embeddings/tests/test_store_integration.py).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from now_search.connections import city_engine

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
        # No commit -- everything this package's read paths do against
        # public.*/engine.article_search is read-only in this fixture.


@pytest.fixture()
def write_conn(engine):
    """A connection with an open transaction that is ALWAYS rolled back,
    never committed -- safe for tests that upsert/delete rows in
    `engine.article_search` (this package's own table, per migration
    0006) against the shared `now_jakarta` database."""
    with engine.connect() as c:
        trans = c.begin()
        try:
            yield c
        finally:
            trans.rollback()
