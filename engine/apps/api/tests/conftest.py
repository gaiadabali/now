"""Shared test fixtures.

These tests run against a throwaway Postgres container spun up by the
implementing agent (see engine/apps/api/README.md for the exact `docker
run` + seed SQL). Nothing here talks to a real production city database --
the seeded registry uses synthetic slugs (`alpha`, `beta`, ...) precisely so
these tests don't themselves become a site-name-literal violation.
"""

from __future__ import annotations

import os

from app.config import Settings

TEST_DB_HOST = os.environ.get("NOW_TEST_DB_HOST", "localhost")
TEST_DB_PORT = int(os.environ.get("NOW_TEST_DB_PORT", "55510"))
TEST_DB_USER = os.environ.get("NOW_TEST_DB_USER", "now")
TEST_DB_PASSWORD = os.environ.get("NOW_TEST_DB_PASSWORD", "now")


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
