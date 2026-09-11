"""Engine construction, reusing `now_db`'s `NOW_PG_*` env-var convention --
one-for-one with `now_search`/`now_filters`/`now_blender`'s own
`connections.py` (one source of truth for host/port/user/password so this
package never drifts from what `now-db migrate` resolves to on this host).

Everything downstream of this module in `now_rails` is **sync**
(`sqlalchemy.engine.Connection`), matching the whole
`{search,filters,quality,embeddings,blender}` stack this package composes
-- see `now_blender.weights`'s docstring for why that stack stays sync
rather than mixing in an async driver. `engine/apps/api` is async
(`AsyncSession`); the API's `app/domain/rails/` bridges the two with
`asyncio.to_thread`, not by making this package async.
"""

from __future__ import annotations

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import Engine, create_engine


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)


def platform_engine() -> Engine:
    return create_engine(platform_database_url(), future=True)
