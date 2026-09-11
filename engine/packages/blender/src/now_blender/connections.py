"""Engine construction, reusing `now_db`'s `NOW_PG_*` env-var convention --
this package adds no new connection configuration surface, matching
`now-search`/`now-filters`/`now-quality`/`now-embeddings` (one source of
truth for host/port/user/password so this package never drifts from what
`now-db migrate` resolves to on this host).

`platform_engine()` mirrors `now_search.connections.platform_engine()`
one-for-one: this package needs `now_platform.engine.sites.ranking_weights`
(both the `'decay'` key now-db's `site:create` already seeds, and the
`'blend'` key this package seeds itself -- see `weights.py`), exactly the
same cross-database need now-search's tsv worker and now-embeddings'
`ReembedWorker` already have.
"""

from __future__ import annotations

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import Engine, create_engine


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)


def platform_engine() -> Engine:
    return create_engine(platform_database_url(), future=True)
