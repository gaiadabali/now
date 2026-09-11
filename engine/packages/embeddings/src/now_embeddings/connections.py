"""Engine construction, reusing the exact same `NOW_PG_*` env-var
convention `now-db` and `now-platform-db` already define -- this package
adds no new connection configuration surface, deliberately, so it never
drifts from what `now-db migrate` / `now-platform-db` already resolve to
on this host (see F3 in PROGRESS.md: Postgres is remapped to 15432 here)."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)


def platform_engine() -> Engine:
    return create_engine(platform_database_url(), future=True)
