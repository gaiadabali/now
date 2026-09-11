"""Engine construction, reusing `now_db`'s `NOW_PG_*` env-var convention --
this package adds no new connection configuration surface, matching
`now-embeddings`/`now-quality` (see those packages' `connections.py`/`db.py`
docstrings for why: one source of truth for host/port/user/password so this
package never drifts from what `now-db migrate` resolves to on this host).

`platform_engine()` is added for the F41 tsv worker's multi-tenant
routing (`tsv_worker.py`) -- resolving a domain event's `site_slug` to a
`db_ref` requires reading `now_platform.engine.sites`, exactly the same
need `now_embeddings.worker.ReembedWorker` already has, so this mirrors
that module's `connections.py` one-for-one."""

from __future__ import annotations

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import Engine, create_engine


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)


def platform_engine() -> Engine:
    return create_engine(platform_database_url(), future=True)
