"""The scheduled jobs.

Every job here is:

  - **per-site**, driven by the registry (`app/sites.py`) — no city is named;
  - **idempotent**, because arq cron will run it again and a retry must be
    harmless;
  - **DB-only**, because the server has none of the gitignored derived data
    (`docs/data-provenance.md`). That rules out otherwise-obvious jobs:
    `now-quality score` needs `articles.jsonl`, so it is a workstation task,
    not a worker one.

Jobs import the real implementation rather than shelling out to the package
CLI. `now-db ensure-partitions` and `ensure_daily_partitions` do the same
work, but the function returns what it created and raises a real exception,
where the subprocess returns exit status and a string.
"""

from __future__ import annotations

import logging

from now_db.partitions import drop_partitions_older_than, ensure_daily_partitions
from sqlalchemy import create_engine

from app.sites import Site, SiteRunReport, for_each_site, load_sites

logger = logging.getLogger(__name__)

# How far ahead partitions are kept. The failure this prevents is specific:
# `engine.interactions` and `engine.impressions` are daily-partitioned, and an
# INSERT for a date with no partition FAILS — it does not silently route
# anywhere. The beacon writes to both on every page view, so running out of
# partitions is a total loss of behavioural data, which ARCHITECTURE.md §19
# points out cannot be backfilled.
#
# 14 days, not the CLI's default 7, so that a worker outage over a holiday
# still leaves a week of runway.
PARTITION_DAYS_AHEAD = 14

# Retention is deliberately NOT enabled by default (None = never drop).
# Dropping a partition destroys behavioural data permanently, and E7
# personalization is explicitly data-gated on accumulating ~50k sessions.
# Deleting it on a schedule nobody chose would be the wrong default; set
# ENGINE_WORKER_INTERACTION_RETENTION_DAYS when there is a real reason.
DEFAULT_RETENTION_DAYS: int | None = None


def _ensure_partitions_for(site: Site, *, days_ahead: int) -> list[str]:
    engine = create_engine(site.dsn)
    try:
        with engine.begin() as conn:
            created = ensure_daily_partitions(conn, days_ahead=days_ahead)
    finally:
        engine.dispose()
    if created:
        logger.info("site=%s created partitions: %s", site.slug, ", ".join(created))
    return created


def _drop_old_partitions_for(site: Site, *, retention_days: int) -> list[str]:
    engine = create_engine(site.dsn)
    try:
        with engine.begin() as conn:
            dropped = drop_partitions_older_than(conn, retention_days=retention_days)
    finally:
        engine.dispose()
    if dropped:
        logger.warning("site=%s DROPPED partitions: %s", site.slug, ", ".join(dropped))
    return dropped


# ---------------------------------------------------------------------------
# arq entry points. Signature is (ctx, ...) — arq passes its context first.
# ---------------------------------------------------------------------------


async def ensure_partitions(ctx: dict) -> dict:
    """Create tomorrow's partitions before anything needs to write to them."""

    settings = ctx["settings"]
    sites = load_sites(settings.platform_database_url)
    report: SiteRunReport = for_each_site(
        sites,
        lambda s: _ensure_partitions_for(s, days_ahead=settings.partition_days_ahead),
        job="ensure_partitions",
    )
    logger.info("ensure_partitions: %s", report.summary())
    # Returned rather than raised: arq records the result, and a failing city
    # is retried on the next tick. Raising would only mark the whole job
    # failed while telling nobody which city.
    return {"created": report.succeeded, "failed": report.failed}


async def drop_old_partitions(ctx: dict) -> dict:
    """No-op unless a retention window was explicitly configured."""

    settings = ctx["settings"]
    if settings.interaction_retention_days is None:
        logger.debug("drop_old_partitions: no retention window set, skipping")
        return {"skipped": "no retention window configured"}

    sites = load_sites(settings.platform_database_url)
    report = for_each_site(
        sites,
        lambda s: _drop_old_partitions_for(
            s, retention_days=settings.interaction_retention_days
        ),
        job="drop_old_partitions",
    )
    logger.info("drop_old_partitions: %s", report.summary())
    return {"dropped": report.succeeded, "failed": report.failed}


async def heartbeat(ctx: dict) -> dict:
    """Liveness for a process that has no port to probe.

    A container that is `running` proves only that PID 1 has not exited —
    arq could be wedged and Docker would still call it up. This writes a
    short-lived key so `docker exec ... now-worker health` can tell the
    difference between alive and merely present.
    """

    redis = ctx["redis"]
    settings = ctx["settings"]
    # `ex=`, not `expire=`. arq's ctx["redis"] is an ArqRedis, a subclass of
    # redis.asyncio.Redis, whose set() names the TTL `ex`; `expire` was the
    # old aioredis spelling and raises TypeError here. The heartbeat therefore
    # never wrote a key, and the health probe read that as a wedged worker —
    # a liveness check that could only ever report dead.
    await redis.set(settings.heartbeat_key, "1", ex=settings.heartbeat_ttl_seconds)
    return {"heartbeat": settings.heartbeat_key}
