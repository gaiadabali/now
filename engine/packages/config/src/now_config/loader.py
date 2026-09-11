"""Loads `sites` registry rows from the platform database.

This module owns zero connection/pool lifecycle — it is handed a live
`AsyncConnection` by the caller and returns parsed `SiteConfig` objects. That
keeps it reusable from `engine-api`, `engine-worker` and `web` alike, all of
which need "slug/hostname -> SiteConfig" but each own their own pooling.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from now_config.errors import SiteNotFoundError
from now_config.models import SiteConfig

# `sites` lives in the platform DB's `engine` schema (Alembic-owned), not
# `public` (Payload-owned) -- confirmed against E0.2's baseline migration
# (engine/packages/platform-db/.../0001_baseline_engine_schema.py):
# `CREATE TABLE engine.sites (...)`. Always schema-qualify: the connecting
# role's `search_path` is not guaranteed to include `engine`.
_TABLE = "engine.sites"
_COLUMNS = (
    "id, slug, hostname, name, locale, timezone, currency, "
    "brand_tokens, nav, home_rails, ranking_weights, db_ref, "
    "enabled_modules, status"
)

_SELECT_BY_SLUG = text(f"SELECT {_COLUMNS} FROM {_TABLE} WHERE slug = :slug")
_SELECT_BY_HOSTNAME = text(f"SELECT {_COLUMNS} FROM {_TABLE} WHERE hostname = :hostname")
_SELECT_ALL = text(f"SELECT {_COLUMNS} FROM {_TABLE} ORDER BY slug")


class SiteConfigLoader:
    """Reads `sites` rows and parses them into `SiteConfig`."""

    async def load_by_slug(self, conn: AsyncConnection, slug: str) -> SiteConfig:
        result = await conn.execute(_SELECT_BY_SLUG, {"slug": slug})
        row = result.mappings().first()
        if row is None:
            raise SiteNotFoundError(lookup="slug", value=slug)
        return SiteConfig.model_validate(dict(row))

    async def load_by_hostname(self, conn: AsyncConnection, hostname: str) -> SiteConfig:
        result = await conn.execute(_SELECT_BY_HOSTNAME, {"hostname": hostname})
        row = result.mappings().first()
        if row is None:
            raise SiteNotFoundError(lookup="hostname", value=hostname)
        return SiteConfig.model_validate(dict(row))

    async def load_all(self, conn: AsyncConnection) -> Sequence[SiteConfig]:
        result = await conn.execute(_SELECT_ALL)
        return [SiteConfig.model_validate(dict(row)) for row in result.mappings().all()]
