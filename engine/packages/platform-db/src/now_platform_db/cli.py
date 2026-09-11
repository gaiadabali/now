from __future__ import annotations

import json
import os
from pathlib import Path

import click
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from now_platform_db.partitions import drop_partitions_older_than, ensure_daily_partitions
from now_platform_db.schema_hash import compute_hash, diff_structures
from now_platform_db.settings import platform_database_url

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = PACKAGE_ROOT / "schema_baseline.json"


def _alembic_config(url: str | None = None) -> Config:
    cfg = Config(str(PACKAGE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PACKAGE_ROOT / "src" / "now_platform_db" / "migrations"))
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@click.group()
def cli() -> None:
    """now-platform-db: migrations + schema-hash gate for now_platform.engine."""


@cli.command()
@click.option("--url", default=None, help="Override the platform DSN.")
def migrate(url: str | None) -> None:
    """Apply every pending migration to the platform DB (idempotent)."""
    dsn = url or platform_database_url()
    command.upgrade(_alembic_config(dsn), "head")
    click.echo(f"[now-platform-db] migrated {dsn} to head")


@cli.command()
@click.option("--url", default=None)
@click.option("--write-baseline", is_flag=True, help="Overwrite the committed schema_baseline.json.")
def hash(url: str | None, write_baseline: bool) -> None:
    """Print (and optionally record) the structural hash of `engine`."""
    dsn = url or platform_database_url()
    engine = create_engine(dsn)
    with engine.connect() as conn:
        digest, structure = compute_hash(conn)
    click.echo(digest)
    if write_baseline:
        BASELINE_PATH.write_text(json.dumps({"hash": digest, "structure": structure}, indent=2, sort_keys=True))
        click.echo(f"[now-platform-db] wrote baseline to {BASELINE_PATH}")


@cli.command()
@click.option("--url", default=None)
def check(url: str | None) -> None:
    """Fail (exit 1) if the live schema differs from schema_baseline.json."""
    if not BASELINE_PATH.exists():
        raise click.ClickException(f"no baseline at {BASELINE_PATH}; run `hash --write-baseline` first")
    baseline = json.loads(BASELINE_PATH.read_text())
    dsn = url or platform_database_url()
    engine = create_engine(dsn)
    with engine.connect() as conn:
        digest, structure = compute_hash(conn)
    if digest == baseline["hash"]:
        click.echo(f"[now-platform-db] OK — schema matches baseline ({digest[:12]})")
        return
    diffs = diff_structures(baseline["structure"], structure)
    click.echo(f"[now-platform-db] DRIFT DETECTED — expected {baseline['hash'][:12]}, got {digest[:12]}", err=True)
    for line in diffs:
        click.echo(f"  - {line}", err=True)
    raise SystemExit(1)


@cli.command("ensure-partitions")
@click.option("--url", default=None)
@click.option("--days-ahead", default=7, show_default=True)
def ensure_partitions(url: str | None, days_ahead: int) -> None:
    """Create any missing daily partitions for engine.ad_events."""
    dsn = url or platform_database_url()
    engine = create_engine(dsn)
    with engine.begin() as conn:
        created = ensure_daily_partitions(conn, days_ahead=days_ahead)
    if created:
        click.echo(f"[now-platform-db] created partitions: {', '.join(created)}")
    else:
        click.echo("[now-platform-db] no new partitions needed")


@cli.command("drop-old-partitions")
@click.option("--url", default=None)
@click.option("--retention-days", required=True, type=int)
def drop_old_partitions(url: str | None, retention_days: int) -> None:
    dsn = url or platform_database_url()
    engine = create_engine(dsn)
    with engine.begin() as conn:
        dropped = drop_partitions_older_than(conn, retention_days=retention_days)
    if dropped:
        click.echo(f"[now-platform-db] dropped partitions: {', '.join(dropped)}")
    else:
        click.echo("[now-platform-db] nothing older than retention window")


if __name__ == "__main__":
    cli()
