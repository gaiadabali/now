"""Thin read/write helpers around `now_platform.engine.sites`.

Deliberately raw SQL, not an ORM model: this table is a fixed external
contract (see the platform-db baseline migration docstring and
`now_config.SiteConfig`), and `now-db` only ever needs to read the roster
and upsert one row on `site:create` — a full ORM mapping would be more
surface area than the job requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class SiteRow:
    id: Any
    slug: str
    hostname: str
    name: str
    locale: str
    timezone: str
    currency: str
    db_ref: str
    enabled_modules: list[str]
    status: str


def list_sites(connection: Connection, *, include_disabled: bool = False) -> list[SiteRow]:
    clause = "" if include_disabled else "WHERE status <> 'disabled'"
    rows = connection.execute(
        text(
            f"SELECT id, slug, hostname, name, locale, timezone, currency, "
            f"db_ref, enabled_modules, status "
            f"FROM engine.sites {clause} ORDER BY slug"
        )
    ).fetchall()
    return [
        SiteRow(
            id=r[0],
            slug=r[1],
            hostname=r[2],
            name=r[3],
            locale=r[4],
            timezone=r[5],
            currency=r[6],
            db_ref=r[7],
            enabled_modules=list(r[8] or []),
            status=r[9],
        )
        for r in rows
    ]


def get_site(connection: Connection, slug: str) -> SiteRow | None:
    row = connection.execute(
        text(
            "SELECT id, slug, hostname, name, locale, timezone, currency, "
            "db_ref, enabled_modules, status FROM engine.sites WHERE slug = :slug"
        ),
        {"slug": slug},
    ).first()
    if row is None:
        return None
    return SiteRow(
        id=row[0],
        slug=row[1],
        hostname=row[2],
        name=row[3],
        locale=row[4],
        timezone=row[5],
        currency=row[6],
        db_ref=row[7],
        enabled_modules=list(row[8] or []),
        status=row[9],
    )


def upsert_site(
    connection: Connection,
    *,
    slug: str,
    hostname: str,
    name: str,
    locale: str,
    timezone: str,
    currency: str,
    db_ref: str,
    enabled_modules: list[str],
    status: str = "active",
) -> None:
    """Idempotent insert-or-update keyed by `slug` — safe to call on every
    `site:create` run, including re-runs against an already-provisioned
    site (acceptance criterion: `site:create` is not one-shot-only)."""
    connection.execute(
        text(
            """
            INSERT INTO engine.sites
                (slug, hostname, name, locale, timezone, currency, db_ref, enabled_modules, status)
            VALUES
                (:slug, :hostname, :name, :locale, :timezone, :currency, :db_ref, :enabled_modules, :status)
            ON CONFLICT (slug) DO UPDATE SET
                hostname = EXCLUDED.hostname,
                name = EXCLUDED.name,
                locale = EXCLUDED.locale,
                timezone = EXCLUDED.timezone,
                currency = EXCLUDED.currency,
                db_ref = EXCLUDED.db_ref,
                enabled_modules = EXCLUDED.enabled_modules,
                status = EXCLUDED.status,
                updated_at = now()
            """
        ),
        {
            "slug": slug,
            "hostname": hostname,
            "name": name,
            "locale": locale,
            "timezone": timezone,
            "currency": currency,
            "db_ref": db_ref,
            "enabled_modules": enabled_modules,
            "status": status,
        },
    )
