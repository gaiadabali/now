from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infra.db.pools import CityPoolRegistry
from now_config import SiteConfigLoader

from tests.conftest import make_test_settings


@pytest.mark.asyncio
async def test_pools_are_isolated_per_site() -> None:
    settings = make_test_settings()
    platform_engine = create_async_engine(settings.platform_database_url)
    loader = SiteConfigLoader()
    pools = CityPoolRegistry(settings)
    try:
        async with platform_engine.connect() as conn:
            alpha = await loader.load_by_slug(conn, "alpha")
            beta = await loader.load_by_slug(conn, "beta")

        alpha_maker = await pools.get_sessionmaker(alpha)
        beta_maker = await pools.get_sessionmaker(beta)

        assert alpha_maker is not beta_maker

        async with alpha_maker() as session:
            result = await session.execute(text("SELECT city FROM marker"))
            assert result.scalar_one() == "alpha"

        async with beta_maker() as session:
            result = await session.execute(text("SELECT city FROM marker"))
            assert result.scalar_one() == "beta"

        assert set(pools.cached_slugs()) == {"alpha", "beta"}

        # Calling again for the same site returns the *same* cached pool,
        # not a freshly created one.
        alpha_maker_again = await pools.get_sessionmaker(alpha)
        assert alpha_maker_again is alpha_maker
    finally:
        await pools.dispose_all()
        await platform_engine.dispose()


@pytest.mark.asyncio
async def test_unreachable_city_db_does_not_poison_pool_cache() -> None:
    settings = make_test_settings()
    platform_engine = create_async_engine(settings.platform_database_url)
    loader = SiteConfigLoader()
    pools = CityPoolRegistry(settings)
    try:
        async with platform_engine.connect() as conn:
            delta = await loader.load_by_slug(conn, "delta-unreachable")

        maker = await pools.get_sessionmaker(delta)

        # now_missing_db does not exist on the server -- connecting fails.
        with pytest.raises(Exception):  # noqa: B017 - asserting *some* db error
            async with maker() as session:
                await session.connection()

        # The pool stays cached: a transient/permanent outage must not force
        # a pool rebuild on every request.
        assert "delta-unreachable" in pools.cached_slugs()
        maker_again = await pools.get_sessionmaker(delta)
        assert maker_again is maker
    finally:
        await pools.dispose_all()
        await platform_engine.dispose()
