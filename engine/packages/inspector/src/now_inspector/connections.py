"""Connection resolution -- reuses `now_db.settings.city_database_url`
exactly like `now-search`/`now-quality`/`now-embeddings` do, so this
package introduces no new `NOW_PG_*` reading logic and never drifts from
what `now-db migrate` (and the project's `.env`, per F31) resolves to.
"""

from __future__ import annotations

from now_db.settings import city_database_url
from sqlalchemy import Engine, create_engine


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)
