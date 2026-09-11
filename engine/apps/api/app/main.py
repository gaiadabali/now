"""engine-api entrypoint.

One deployment serves every city (ARCHITECTURE.md §3.5). `create_app` is a
factory rather than a bare module-level `FastAPI()` so tests can build
independent instances -- each with its own platform engine, site registry
cache and city pool registry stored on `app.state` -- without leaking pools
between tests that point at different throwaway databases.

Run locally:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from now_config import SiteConfigLoader

from app.api.root import router as root_router
from app.api.v1.router import router as v1_router
from app.config import Settings, get_settings
from app.infra.auth.api_key import ApiKeyStore
from app.infra.db.pools import CityPoolRegistry
from app.infra.db.registry import SiteRegistryCache
from app.infra.logging.middleware import RequestContextMiddleware
from app.infra.logging.setup import setup_logging
from app.infra.ratelimit.limiter import RateLimiter

logger = logging.getLogger("engine_api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        platform_engine = create_async_engine(
            settings.platform_database_url,
            pool_size=settings.platform_pool_size,
            max_overflow=settings.platform_pool_max_overflow,
            pool_pre_ping=True,
        )
        app.state.settings = settings
        app.state.platform_engine = platform_engine
        app.state.platform_sessionmaker = async_sessionmaker(
            platform_engine, expire_on_commit=False
        )
        app.state.site_registry = SiteRegistryCache(
            loader=SiteConfigLoader(),
            platform_engine=platform_engine,
            ttl_seconds=settings.site_registry_cache_ttl_seconds,
        )
        app.state.city_pools = CityPoolRegistry(settings)
        app.state.api_keys = ApiKeyStore.from_file(settings.api_keys_file)
        app.state.rate_limiter = RateLimiter(
            redis_url=settings.redis_url,
            limit=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

        logger.info("engine-api starting", extra={})
        try:
            yield
        finally:
            await app.state.city_pools.dispose_all()
            await platform_engine.dispose()
            logger.info("engine-api stopped", extra={})

    app = FastAPI(
        title="NOW! Engine API",
        description="Multi-tenant read/write API for the NOW! Engine — one deployment, many cities.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(root_router)
    app.include_router(v1_router)
    return app


app = create_app()
