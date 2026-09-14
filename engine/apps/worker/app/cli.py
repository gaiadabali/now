"""`now-worker` — operator commands. The worker itself is run by arq
(`arq app.main.WorkerSettings`), not from here; this exists for the things
an operator needs on a box with no HTTP surface to curl."""

from __future__ import annotations

import asyncio
import sys

import click
from redis.asyncio import Redis

from app.config import Settings
from app.sites import load_sites


@click.group()
def cli() -> None:
    pass


@cli.command()
def health() -> None:
    """Exit 0 if the worker wrote a heartbeat recently.

    Used as the container healthcheck. `docker ps` showing "running" only
    proves PID 1 is alive; arq can be wedged, or the re-embed consumer can
    have died, and this is what tells them apart.
    """

    settings = Settings.from_env()

    async def _check() -> bool:
        redis = Redis.from_url(settings.redis_url)
        try:
            return await redis.get(settings.heartbeat_key) is not None
        finally:
            await redis.aclose()

    if asyncio.run(_check()):
        click.echo("ok")
        return
    click.echo(
        f"no heartbeat at {settings.heartbeat_key} — the worker is not running, "
        "is wedged, or its re-embed consumer died (see logs)",
        err=True,
    )
    sys.exit(1)


@cli.command()
def sites() -> None:
    """List what the registry says this worker will fan out over."""

    settings = Settings.from_env()
    found = load_sites(settings.platform_database_url)
    if not found:
        click.echo("no rows in engine.sites — every job will be a no-op", err=True)
        sys.exit(1)
    for site in found:
        click.echo(f"{site.slug}\t{site.db_ref}")


if __name__ == "__main__":
    cli()
