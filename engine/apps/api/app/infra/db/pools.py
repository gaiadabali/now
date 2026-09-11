"""Lazily-created, cached connection pools — one AsyncEngine per city.

This is half of the router described in ARCHITECTURE.md §3.5:

    Depends(get_city_db)      # site from path -> pooled engine for that city DB
    Depends(get_platform_db)  # single shared platform pool

`CityPoolRegistry` owns the "pooled engine for that city DB" half. Adding a
city never touches this code — a new `sites` row is enough, because the
engine is created on first request for a not-yet-seen slug and cached from
then on.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from now_config import SiteConfig

logger = logging.getLogger("engine_api.db.pools")


@dataclass
class _Pool:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    db_ref: str
    created_at: float


class CityPoolRegistry:
    """Keyed by site slug. One `AsyncEngine` per city, created on first use.

    A connectivity *failure* (the city DB is unreachable) never evicts the
    cached engine here -- SQLAlchemy's pool (with `pool_pre_ping`) recovers
    on its own once the database comes back, and tearing down/rebuilding the
    whole pool on every failed request would be far more expensive than one
    failed connection attempt. The only thing that evicts and rebuilds a
    pool is `db_ref` itself changing (a site repointed at a different
    database), which is checked on every lookup.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pools: dict[str, _Pool] = {}
        self._lock = asyncio.Lock()

    async def get_sessionmaker(self, site: SiteConfig) -> async_sessionmaker[AsyncSession]:
        existing = self._pools.get(site.slug)
        if existing is not None and existing.db_ref == site.db_ref:
            return existing.sessionmaker

        async with self._lock:
            # Re-check under the lock -- another request may have created it
            # (or rotated db_ref) while we were waiting.
            existing = self._pools.get(site.slug)
            if existing is not None and existing.db_ref == site.db_ref:
                return existing.sessionmaker

            if existing is not None:
                logger.warning(
                    "db_ref changed for site %s; rebuilding pool",
                    site.slug,
                )
                await existing.engine.dispose()

            dsn = self._settings.build_city_dsn(site.db_ref)
            engine = create_async_engine(
                dsn,
                pool_size=self._settings.city_pool_size,
                max_overflow=self._settings.city_pool_max_overflow,
                pool_pre_ping=True,
                pool_recycle=1800,
            )
            sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
            self._pools[site.slug] = _Pool(
                engine=engine,
                sessionmaker=sessionmaker,
                db_ref=site.db_ref,
                created_at=time.monotonic(),
            )
            logger.info("created city pool for site=%s db_ref=%s", site.slug, site.db_ref)
            return sessionmaker

    def cached_slugs(self) -> list[str]:
        """For tests/observability: which cities currently have a live pool."""
        return list(self._pools.keys())

    async def dispose_all(self) -> None:
        async with self._lock:
            for pool in self._pools.values():
                await pool.engine.dispose()
            self._pools.clear()
