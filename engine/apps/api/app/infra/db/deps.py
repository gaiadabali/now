"""The multi-DB session router. Everything downstream imports from here.

    Depends(get_city_db)      # site slug from path -> pooled engine for that city DB
    Depends(get_platform_db)  # single shared platform pool

Both dependencies read their shared state off `request.app.state`, set up
once in `app.main.create_app`'s lifespan -- not module-level globals -- so
tests can spin up independent `FastAPI` app instances (e.g. pointed at two
different throwaway Postgres containers) without leaking pools between them.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import asyncpg
from fastapi import HTTPException, Path, Request
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from now_config import SiteNotFoundError

logger = logging.getLogger("engine_api.db.deps")

# Driver/connection errors that mean "the database is unreachable" rather
# than "something is wrong with the query". Mapped to 503, never 500.
#
# `asyncpg.PostgresError` is included deliberately broad: it is only ever
# caught around a bare connection-establishment probe in this module (never
# around arbitrary business-query execution), so any Postgres error raised
# there -- wrong database name (InvalidCatalogNameError), bad credentials,
# etc. -- is inherently a "can't reach this city's database" condition, not
# a query bug. Plain `OperationalError` alone is not enough: SQLAlchemy's
# asyncpg dialect does not wrap every connect-time failure in a DBAPIError,
# some surface as the raw asyncpg/OS exception (verified empirically against
# a throwaway Postgres instance -- see engine/apps/api/README.md).
_UNREACHABLE_ERRORS = (
    OperationalError,
    asyncpg.PostgresError,
    ConnectionError,
    OSError,
    TimeoutError,
)


async def get_platform_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Yields an `AsyncSession` bound to the single shared platform pool."""
    sessionmaker = request.app.state.platform_sessionmaker
    async with sessionmaker() as session:
        yield session


async def get_city_db(
    request: Request,
    site: str = Path(..., description="City site slug, resolved against the `sites` registry."),
) -> AsyncIterator[AsyncSession]:
    """Resolves `site` (a path segment, e.g. `/v1/{site}/...`) to a pooled
    `AsyncSession` for that city's database.

    - Unknown site slug            -> HTTP 404
    - Site registered but disabled -> HTTP 404 (not eligible to serve traffic)
    - Site's database unreachable  -> HTTP 503, and the pool cache is left
      untouched so a transient outage doesn't force a pool rebuild
    - Platform registry unreachable -> HTTP 503
    """
    registry = request.app.state.site_registry
    pools = request.app.state.city_pools

    try:
        site_config = await registry.get_by_slug(site)
    except SiteNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown site '{site}'") from None
    except _UNREACHABLE_ERRORS as exc:
        logger.error("platform registry unreachable while resolving site=%s", site)
        raise HTTPException(
            status_code=503,
            detail="site registry is temporarily unavailable",
        ) from exc

    if not site_config.is_active:
        # A provisioning/disabled site is not a routing target yet -- treat
        # it the same as "doesn't exist" rather than leaking lifecycle state.
        raise HTTPException(status_code=404, detail=f"unknown site '{site}'")

    sessionmaker = await pools.get_sessionmaker(site_config)
    session = sessionmaker()
    try:
        # Cheap connectivity probe. Without this, a dead city DB surfaces as
        # whatever exception the first real query happens to raise, which
        # for most business endpoints would bubble up as an uncaught 500.
        await session.connection()
    except _UNREACHABLE_ERRORS as exc:
        await session.close()
        logger.error("city db unreachable for site=%s db_ref=%s", site, site_config.db_ref)
        raise HTTPException(
            status_code=503,
            detail=f"database for site '{site}' is temporarily unavailable",
        ) from exc

    try:
        yield session
    finally:
        await session.close()
