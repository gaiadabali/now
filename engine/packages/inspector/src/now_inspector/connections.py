"""Connection resolution -- reuses `now_db.settings.city_database_url`
exactly like `now-search`/`now-quality`/`now-embeddings` do, so this
package introduces no new `NOW_PG_*` reading logic and never drifts from
what `now-db migrate` (and the project's `.env`, per F31) resolves to.

F124/F125 (T2 decay trust gate): `platform_engine()` is new -- this
package previously never touched the platform DB at all. It is needed to
resolve the format facet's term ids (F92: no cross-DB FK, see
`now_blender.format_terms_cache`) and, optionally, a site's real (possibly
tuned) `sites.ranking_weights['decay']` -- mirroring exactly how
`now_blender.reranker.BlenderReranker.build` / `now_rails.orchestrator
.RailsOrchestrator.build` already take an optional platform connection
alongside the city one.
"""

from __future__ import annotations

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import Engine, create_engine


def city_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref), future=True)


def platform_engine() -> Engine:
    return create_engine(platform_database_url(), future=True)
