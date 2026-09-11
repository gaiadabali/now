"""TTL-cached view over the platform `sites` table.

Adding, editing or disabling a site is picked up within
`settings.site_registry_cache_ttl_seconds` of the write landing in Postgres
-- no API restart, no redeploy. `invalidate()` / `invalidate_all()` are the
documented invalidation hook for callers that want it sooner (an admin
action, or a future LISTEN/NOTIFY trigger from the platform DB).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from now_config import SiteConfig, SiteConfigLoader, SiteNotFoundError

__all__ = ["SiteRegistryCache", "SiteNotFoundError"]


@dataclass
class _CacheEntry:
    site: SiteConfig
    expires_at: float


class SiteRegistryCache:
    def __init__(
        self,
        loader: SiteConfigLoader,
        platform_engine: AsyncEngine,
        ttl_seconds: float,
    ) -> None:
        self._loader = loader
        self._engine = platform_engine
        self._ttl = ttl_seconds
        self._by_slug: dict[str, _CacheEntry] = {}

    async def get_by_slug(self, slug: str) -> SiteConfig:
        """Returns the `SiteConfig` for `slug`.

        Raises `now_config.SiteNotFoundError` for an unknown slug -- callers
        map that to 404. Raises whatever SQLAlchemy/asyncpg raises if the
        platform DB itself is unreachable -- callers map that to 503.
        """
        now = time.monotonic()
        cached = self._by_slug.get(slug)
        if cached is not None and cached.expires_at > now:
            return cached.site

        async with self._engine.connect() as conn:
            site = await self._loader.load_by_slug(conn, slug)

        self._by_slug[slug] = _CacheEntry(site=site, expires_at=now + self._ttl)
        return site

    def invalidate(self, slug: str) -> None:
        self._by_slug.pop(slug, None)

    def invalidate_all(self) -> None:
        self._by_slug.clear()

    def cached_slugs(self) -> list[str]:
        return list(self._by_slug.keys())
