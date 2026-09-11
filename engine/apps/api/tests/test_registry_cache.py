from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infra.db.registry import SiteRegistryCache
from now_config import SiteConfigLoader

from tests.conftest import make_test_settings


@pytest.mark.asyncio
async def test_registry_cache_serves_stale_within_ttl_then_refreshes() -> None:
    settings = make_test_settings(site_registry_cache_ttl_seconds=0.2)
    engine = create_async_engine(settings.platform_database_url)
    cache = SiteRegistryCache(
        loader=SiteConfigLoader(),
        platform_engine=engine,
        ttl_seconds=settings.site_registry_cache_ttl_seconds,
    )
    try:
        site = await cache.get_by_slug("alpha")
        original_name = site.name

        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE engine.sites SET name = :n WHERE slug = 'alpha'"),
                {"n": "Alpha City Renamed"},
            )

        # Still inside the TTL window -- the cached (stale) row is served,
        # proving lookups don't hit Postgres on every request.
        still_cached = await cache.get_by_slug("alpha")
        assert still_cached.name == original_name

        await asyncio.sleep(0.25)

        refreshed = await cache.get_by_slug("alpha")
        assert refreshed.name == "Alpha City Renamed"
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE engine.sites SET name = :n WHERE slug = 'alpha'"),
                {"n": "Alpha City"},
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalidate_forces_immediate_refresh() -> None:
    settings = make_test_settings(site_registry_cache_ttl_seconds=30.0)
    engine = create_async_engine(settings.platform_database_url)
    cache = SiteRegistryCache(
        loader=SiteConfigLoader(),
        platform_engine=engine,
        ttl_seconds=settings.site_registry_cache_ttl_seconds,
    )
    try:
        first = await cache.get_by_slug("beta")
        original_name = first.name

        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE engine.sites SET name = :n WHERE slug = 'beta'"),
                {"n": "Beta City Renamed"},
            )

        # Long TTL -- would normally still be stale here.
        still_cached = await cache.get_by_slug("beta")
        assert still_cached.name == original_name

        cache.invalidate("beta")
        refreshed = await cache.get_by_slug("beta")
        assert refreshed.name == "Beta City Renamed"
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE engine.sites SET name = :n WHERE slug = 'beta'"),
                {"n": "Beta City"},
            )
        await engine.dispose()
