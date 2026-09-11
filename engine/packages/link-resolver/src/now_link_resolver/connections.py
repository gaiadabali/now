"""Engine construction -- one-for-one with `now_rails.connections` (which
this package's shape otherwise mirrors): reuse `now_db`/`now_platform_db`'s
`NOW_PG_*`/`.env` resolution rather than a third implementation.

Two separate engines on purpose. Sec.11's mechanism is a place-level
lookup in the *city* DB (`public.places`, to get `org_id`/`slug`) and an
org/place-level lookup in the *platform* DB (`engine.partnerships`).
`place_id` has no FK across that boundary (F22) -- the two are joined in
Python, never in SQL, because a cross-database join is not something
Postgres can do here at all.
"""

from __future__ import annotations

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import Engine, create_engine


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)


def platform_engine() -> Engine:
    return create_engine(platform_database_url(), future=True)
