"""arq worker: cron schedule + the re-embed stream consumer.

    arq app.main.WorkerSettings

Two kinds of work share this process.

**Cron jobs** (`app/jobs.py`) are arq's own — partition maintenance and the
heartbeat. arq is here for `cron_jobs`; the queue is incidental, because the
fan-out unit is a site, not a task.

**The re-embed consumer** is `now_embeddings.worker.ReembedWorker`, which
already existed and already handles `article.published` off the Redis Stream
with a consumer group. It is not reimplemented here — this app gives it a
process to live in. It is synchronous and blocking, so it runs in a daemon
thread rather than the event loop.

Running it in-process is a deliberate trade. Two containers would isolate a
crash; one container fits a 2 vCPU / 7 GB box that already hosts three other
stacks. The thread is therefore *supervised*: if it dies, the worker stops
writing heartbeats, so the failure surfaces as unhealthy rather than as a
silently idle consumer. Set ENGINE_WORKER_RUN_REEMBED_CONSUMER=false to split
it out.
"""

from __future__ import annotations

import logging
import threading

from arq import cron
from arq.connections import RedisSettings

from app import jobs
from app.config import Settings

logger = logging.getLogger(__name__)

# Module-level so shutdown and the health command can see it.
_reembed_thread: threading.Thread | None = None
_reembed_failed = threading.Event()


def _run_reembed_consumer(settings: Settings) -> None:
    """Body of the supervised thread. Never raises out — a thread that dies
    with an exception takes its traceback nowhere useful."""

    try:
        from now_embeddings.cli import _provider
        from now_embeddings.worker import ReembedWorker

        provider = _provider(settings.reembed_provider)
        worker = ReembedWorker(provider=provider, redis_url=settings.redis_url)
        logger.info(
            "re-embed consumer starting (provider=%s)", settings.reembed_provider
        )
        # `run_forever`, not `run` — ReembedWorker exposes run_once (bounded,
        # used by tests and `worker --once`) and run_forever (the loop). There
        # is no `run`, so this raised AttributeError on the first line of the
        # thread, every start, and the consumer never once ran in production.
        # The supervision worked exactly as designed: the flag latched and the
        # container reported unhealthy. Nothing read the report.
        worker.run_forever()
    except Exception:
        # Latching the flag is the point: the heartbeat job reads it and
        # stops renewing, which is what turns "a thread quietly died" into
        # an unhealthy container.
        _reembed_failed.set()
        logger.exception("re-embed consumer died — worker will report unhealthy")


async def startup(ctx: dict) -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    ctx["settings"] = settings

    logger.info(
        "engine-worker starting: platform=%s partitions=+%dd retention=%s",
        settings.platform_database_url.rsplit("@", 1)[-1],  # never log credentials
        settings.partition_days_ahead,
        settings.interaction_retention_days or "never",
    )

    if settings.run_reembed_consumer:
        global _reembed_thread
        _reembed_thread = threading.Thread(
            target=_run_reembed_consumer,
            args=(settings,),
            name="reembed-consumer",
            daemon=True,
        )
        _reembed_thread.start()
    else:
        logger.info("re-embed consumer disabled by configuration")


async def shutdown(ctx: dict) -> None:
    # The consumer thread is a daemon and blocks on Redis; there is no clean
    # interrupt for it short of closing the connection, and an unacked
    # message is safe to leave — the consumer group redelivers it. Say so
    # rather than pretending to join a thread that will not stop.
    logger.info("engine-worker shutting down")


async def heartbeat_or_fail(ctx: dict) -> dict:
    """Heartbeat, gated on the consumer thread still being alive."""

    settings: Settings = ctx["settings"]
    if settings.run_reembed_consumer:
        if _reembed_failed.is_set() or (
            _reembed_thread is not None and not _reembed_thread.is_alive()
        ):
            logger.error("re-embed consumer is not running; withholding heartbeat")
            return {"heartbeat": "withheld", "reason": "reembed consumer down"}
    return await jobs.heartbeat(ctx)


class WorkerSettings:
    """Consumed by `arq app.main.WorkerSettings`."""

    functions = [jobs.ensure_partitions, jobs.drop_old_partitions]
    cron_jobs = [
        # 03:10 UTC — well before Jakarta/Bali morning traffic (UTC+7/+8),
        # and 14 days of runway means a missed night is not an incident.
        cron(jobs.ensure_partitions, hour=3, minute=10, run_at_startup=True),
        # 03:40, after the create pass, and a no-op unless retention is set.
        cron(jobs.drop_old_partitions, hour=3, minute=40),
        # Every minute, with a 180s TTL: two consecutive misses expire the
        # key, so a single slow tick is not treated as death.
        cron(heartbeat_or_fail, minute=set(range(60)), run_at_startup=True),
    ]

    on_startup = startup
    on_shutdown = shutdown

    # One job at a time. Every job here fans out over all cities and opens a
    # database connection per city; letting several run concurrently on a
    # 2 vCPU box would contend for exactly the resource they all need.
    max_jobs = 1
    job_timeout = 900

    # An attribute, not a method: arq reads this off the class directly, and
    # a staticmethod here is silently ignored — the worker would fall back to
    # localhost and never reach the container's Redis.
    redis_settings = RedisSettings.from_dsn(Settings.from_env().redis_url)
