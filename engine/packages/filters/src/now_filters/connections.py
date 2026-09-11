"""Engine construction, reusing `now_db`'s `NOW_PG_*` env-var convention --
this package adds no new connection configuration surface, matching
`now-search`/`now-embeddings`/`now-quality` (one source of truth for
host/port/user/password so this package never drifts from what `now-db
migrate` resolves to on this host)."""

from __future__ import annotations

from now_db.settings import city_database_url
from sqlalchemy import Engine, create_engine


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)
