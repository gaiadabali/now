from __future__ import annotations

import json
import os

import click

from .config import REPO_ROOT, MirrorConfig
from .inventory import build_inventory, summarize, write_inventory
from .ledger import iter_ledger
from .mirror import MirrorRun

DEFAULT_INVENTORY = REPO_ROOT / "media_mirror_state" / "inventory.jsonl"
DEFAULT_LEDGER = REPO_ROOT / "media_mirror_state" / "ledger.jsonl"


def _config_from_env(**overrides: object) -> MirrorConfig:
    base = MirrorConfig(
        garage_s3_endpoint=os.environ.get(
            "MEDIA_MIRROR_S3_ENDPOINT",
            f"http://localhost:{os.environ.get('GARAGE_S3_PORT', '3900')}",
        ),
        garage_region=os.environ.get("GARAGE_S3_REGION", "garage"),
        garage_bucket=os.environ.get("GARAGE_MEDIA_BUCKET", "now-media"),
        garage_access_key_id=os.environ.get("GARAGE_ACCESS_KEY_ID", ""),
        garage_secret_access_key=os.environ.get("GARAGE_SECRET_ACCESS_KEY", ""),
    )
    return MirrorConfig(**{**base.__dict__, **overrides})


@click.group()
def cli() -> None:
    """Read-only mirror of NOW! site media (articles + attachments) -> Garage."""


@cli.command("inventory")
@click.option("--out", default=None, help="Output JSONL path (default: media_mirror_state/inventory.jsonl)")
def inventory_cmd(out: str | None) -> None:
    """Build the deduplicated URL inventory and print the report."""
    entries = build_inventory()
    out_path = DEFAULT_INVENTORY if out is None else (REPO_ROOT / out)
    write_inventory(entries, out_path)
    report = summarize(entries)
    click.echo(json.dumps(report, indent=2))
    click.echo(f"\nWritten: {out_path}")


@cli.command("mirror")
@click.option("--inventory", "inventory_path", default=None, help="Inventory JSONL (default: media_mirror_state/inventory.jsonl)")
@click.option("--ledger", "ledger_path", default=None, help="Ledger JSONL (default: media_mirror_state/ledger.jsonl)")
@click.option("--concurrency", default=4, show_default=True, type=int)
@click.option("--delay-seconds", default=0.4, show_default=True, type=float, help="Minimum aggregate seconds between request starts, across all workers.")
@click.option("--limit", default=None, type=int, help="Only process the first N not-yet-done entries (smoke test).")
@click.option("--dry-run", is_flag=True, help="Fetch and validate but do not upload to Garage.")
def mirror_cmd(
    inventory_path: str | None,
    ledger_path: str | None,
    concurrency: int,
    delay_seconds: float,
    limit: int | None,
    dry_run: bool,
) -> None:
    """Fetch inventory URLs and upload valid images into Garage. Resumable."""
    inv = DEFAULT_INVENTORY if inventory_path is None else (REPO_ROOT / inventory_path)
    led = DEFAULT_LEDGER if ledger_path is None else (REPO_ROOT / ledger_path)
    if not inv.exists():
        raise click.ClickException(f"No inventory at {inv} — run `media-mirror inventory` first.")

    config = _config_from_env(concurrency=concurrency, delay_seconds=delay_seconds)
    if not dry_run and not config.garage_access_key_id:
        raise click.ClickException("GARAGE_ACCESS_KEY_ID not set (source .env first), or pass --dry-run.")

    run = MirrorRun(config, led, limit=limit, dry_run=dry_run)
    stats = run.run(inv)
    click.echo(json.dumps(stats, indent=2))


@cli.command("report")
@click.option("--ledger", "ledger_path", default=None)
def report_cmd(ledger_path: str | None) -> None:
    """Summarize the ledger as it stands (safe to run mid-flight)."""
    led = DEFAULT_LEDGER if ledger_path is None else (REPO_ROOT / ledger_path)
    counts: dict[str, int] = {}
    bytes_total = 0
    dedup_saved = 0
    for rec in iter_ledger(led):
        counts[rec.get("status", "?")] = counts.get(rec.get("status", "?"), 0) + 1
        if rec.get("status") == "ok":
            bytes_total += int(rec.get("bytes") or 0)
            if rec.get("dedup_reused"):
                dedup_saved += int(rec.get("bytes") or 0)
    click.echo(json.dumps({"counts": counts, "downloaded_bytes_total": bytes_total, "bytes_saved_by_dedup": dedup_saved}, indent=2))


if __name__ == "__main__":
    cli()
