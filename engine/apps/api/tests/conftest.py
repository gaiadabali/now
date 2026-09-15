"""Shared test fixtures.

These tests run against a throwaway Postgres container spun up by the
implementing agent (see engine/apps/api/README.md for the exact `docker
run` + seed SQL). Nothing here talks to a real production city database --
the seeded registry uses synthetic slugs (`alpha`, `beta`, ...) precisely so
these tests don't themselves become a site-name-literal violation.
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
import pytest

from app.config import Settings

TEST_DB_HOST = os.environ.get("NOW_TEST_DB_HOST", "localhost")
TEST_DB_PORT = int(os.environ.get("NOW_TEST_DB_PORT", "55510"))
TEST_DB_USER = os.environ.get("NOW_TEST_DB_USER", "now")
TEST_DB_PASSWORD = os.environ.get("NOW_TEST_DB_PASSWORD", "now")

CITY_TEST_DATABASES = ("now_alpha", "now_beta")

# Mirrors tests/seed/events_schema.sql's own partition block. It lives here
# too, rather than only in the seed, because the seed runs ONCE when the
# container is first provisioned while `CURRENT_DATE` moves every day: a
# container older than three days has no partition covering "now", and an
# INSERT into a daily-partitioned table with no matching partition FAILS.
# That surfaced as seven `assert 400 == 204` failures in test_events.py --
# the endpoint correctly translating a real `EventOutOfRangeError` into a
# 400, against a test database that had simply aged out from under the
# suite. Re-running it per session is cheap and idempotent
# (`CREATE TABLE IF NOT EXISTS`), and keeps the failure mode it protects
# against -- a `ts` far outside any partition, which test_events.py
# deliberately exercises -- exactly as it was.
_ENSURE_PARTITIONS_SQL = """
DO $$
DECLARE
    d date;
BEGIN
    FOR d IN SELECT generate_series(CURRENT_DATE - 3, CURRENT_DATE + 3, interval '1 day')::date LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS engine.interactions_p%s PARTITION OF engine.interactions FOR VALUES FROM (%L) TO (%L)',
            to_char(d, 'YYYY_MM_DD'), d, d + 1
        );
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS engine.impressions_p%s PARTITION OF engine.impressions FOR VALUES FROM (%L) TO (%L)',
            to_char(d, 'YYYY_MM_DD'), d, d + 1
        );
    END LOOP;
END $$;
"""


@pytest.fixture(scope="session", autouse=True)
def ensure_event_partitions() -> None:
    """Brings each city test DB's daily partitions up to "today" before the
    suite runs.

    Skips silently if the container is not up or has not been seeded --
    those tests fail on their own terms with a clearer message than a
    connection error raised from a fixture would give.
    """

    async def _run() -> None:
        for database in CITY_TEST_DATABASES:
            try:
                conn = await asyncpg.connect(
                    host=TEST_DB_HOST,
                    port=TEST_DB_PORT,
                    user=TEST_DB_USER,
                    password=TEST_DB_PASSWORD,
                    database=database,
                )
            except (OSError, asyncpg.PostgresError):
                continue
            try:
                await conn.execute(_ENSURE_PARTITIONS_SQL)
            except asyncpg.PostgresError:
                # No engine.interactions/impressions yet -- unseeded DB.
                pass
            finally:
                await conn.close()

    asyncio.run(_run())


def make_test_settings(**overrides: object) -> Settings:
    base: dict[str, object] = dict(
        platform_database_url=(
            f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}"
            f"@{TEST_DB_HOST}:{TEST_DB_PORT}/now_platform"
        ),
        city_db_host=TEST_DB_HOST,
        city_db_port=TEST_DB_PORT,
        city_db_user=TEST_DB_USER,
        city_db_password=TEST_DB_PASSWORD,
        redis_url=None,
        api_keys_file=None,
        site_registry_cache_ttl_seconds=30.0,
    )
    base.update(overrides)
    return Settings(**base)
