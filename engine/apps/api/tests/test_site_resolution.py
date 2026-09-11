from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from now_config import SiteConfigLoader, SiteNotFoundError

from tests.conftest import make_test_settings


@pytest.mark.asyncio
async def test_load_by_slug_returns_typed_config() -> None:
    settings = make_test_settings()
    engine = create_async_engine(settings.platform_database_url)
    loader = SiteConfigLoader()
    try:
        async with engine.connect() as conn:
            site = await loader.load_by_slug(conn, "alpha")
    finally:
        await engine.dispose()

    assert site.slug == "alpha"
    assert site.hostname == "alpha.example.test"
    assert site.db_ref == "now_alpha"
    assert site.is_active is True
    assert "feed" in site.enabled_modules


@pytest.mark.asyncio
async def test_load_by_hostname_returns_typed_config() -> None:
    settings = make_test_settings()
    engine = create_async_engine(settings.platform_database_url)
    loader = SiteConfigLoader()
    try:
        async with engine.connect() as conn:
            site = await loader.load_by_hostname(conn, "beta.example.test")
    finally:
        await engine.dispose()

    assert site.slug == "beta"


@pytest.mark.asyncio
async def test_load_by_slug_unknown_raises_site_not_found() -> None:
    settings = make_test_settings()
    engine = create_async_engine(settings.platform_database_url)
    loader = SiteConfigLoader()
    try:
        async with engine.connect() as conn:
            with pytest.raises(SiteNotFoundError):
                await loader.load_by_slug(conn, "does-not-exist")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_provisioning_site_is_loaded_but_not_active() -> None:
    """The loader itself is a dumb mirror of the row -- lifecycle policy
    (provisioning sites don't serve traffic) lives in the API layer, not
    here. See tests/test_http_api.py::test_provisioning_site_is_404."""
    settings = make_test_settings()
    engine = create_async_engine(settings.platform_database_url)
    loader = SiteConfigLoader()
    try:
        async with engine.connect() as conn:
            site = await loader.load_by_slug(conn, "gamma-provisioning")
    finally:
        await engine.dispose()

    assert site.is_active is False
