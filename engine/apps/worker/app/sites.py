"""The site registry is the fan-out unit.

ARCHITECTURE.md §3.5: engine-worker is ONE instance that "iterates the site
registry". That is the whole reason a new city is `site:create bandung` and
not a deployment — nothing here may name a city, and the CI lint that bans
`'jakarta'`/`'bali'` literals under `engine/` applies to this app too.

Every job in `app/jobs.py` is therefore written as "do this to one city",
and `for_each_site` supplies the cities. A job never learns how many there
are or what they are called.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, TypeVar

from now_db.settings import city_database_url
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class Site:
    slug: str
    db_ref: str

    @property
    def dsn(self) -> str:
        """Sync DSN for this city's database.

        `db_ref` is usually a bare database name — every city is on the same
        Postgres instance (§2), so only the dbname varies — but a full DSN
        is passed through. `city_database_url` owns that distinction; this
        property exists so a job never has to.
        """
        return city_database_url(self.db_ref)


def load_sites(platform_dsn: str) -> list[Site]:
    """Read the registry. Ordered by slug purely so logs are stable run to
    run — nothing downstream depends on the order."""

    engine = create_engine(platform_dsn)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT slug, db_ref FROM engine.sites ORDER BY slug")
            ).all()
    finally:
        engine.dispose()
    return [Site(slug=r.slug, db_ref=r.db_ref) for r in rows]


@dataclass
class SiteRunReport:
    """What happened across the fan-out. Kept as data rather than logged and
    forgotten so a job can return it and arq can record it."""

    succeeded: dict[str, object]
    failed: dict[str, str]

    @property
    def ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        parts = [f"{len(self.succeeded)} ok"]
        if self.failed:
            parts.append(f"{len(self.failed)} failed: {', '.join(sorted(self.failed))}")
        return ", ".join(parts)


def for_each_site(sites: list[Site], fn: Callable[[Site], T], *, job: str) -> SiteRunReport:
    """Run `fn` once per site, isolating failures.

    One city failing must not stop the others. A bad `db_ref`, a database
    mid-restore, or a migration half-applied is a per-city condition, and
    letting it abort the loop would mean a single broken city silently stops
    partition maintenance everywhere — which surfaces days later as failed
    beacon inserts on cities that were perfectly healthy.

    The report carries the failures so the caller can decide; arq logs the
    summary and the job is retried on its next cron tick.
    """

    succeeded: dict[str, object] = {}
    failed: dict[str, str] = {}
    for site in sites:
        try:
            succeeded[site.slug] = fn(site)
        except Exception as exc:  # noqa: BLE001 — deliberate per-site isolation
            failed[site.slug] = f"{type(exc).__name__}: {exc}"
            logger.exception("job=%s site=%s failed", job, site.slug)
    return SiteRunReport(succeeded=succeeded, failed=failed)
