from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import click

from . import report as report_mod
from .client import RestClient
from .config import Config, ConfigError
from .harvest import sitemap as sitemap_mod
from .runner import COLLECTIONS_BY_KEY, harvest_site
from .sink import read_jsonl
from .verify import check_urls, compare_to_sitemap, host_of, summarise

INVENTORY_ENDPOINTS = (
    "posts",
    "pages",
    "media",
    "upcoming-events",
    "categories",
    "tags",
    "users",
    "comments",
)


def _echo(message: str) -> None:
    click.echo(message)


def site_options(func):
    func = click.option(
        "--base-url",
        default=None,
        help="Site base URL. Falls back to WP_HARVEST_BASE_URL_<SLUG>.",
    )(func)
    func = click.option(
        "--site",
        required=True,
        help="Site slug; output goes to <slug>/content/harvested.",
    )(func)
    return func


def throttle_options(func):
    func = click.option(
        "--timeout", default=45.0, show_default=True, help="Per-request timeout, seconds."
    )(func)
    func = click.option(
        "--delay", default=0.35, show_default=True, help="Pause between requests, seconds."
    )(func)
    return func


def _build(site: str, base_url: str | None, **kw: Any) -> Config:
    try:
        return Config.build(site, base_url, **kw)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group()
@click.version_option(package_name="now-wp-harvest")
def cli() -> None:
    """Read-only harvest of a live WordPress site into JSONL.

    Every command issues GET requests only. Nothing here can modify the
    source site.
    """


@cli.command()
@site_options
@throttle_options
def inventory(site: str, base_url: str | None, delay: float, timeout: float) -> None:
    """Report collection sizes without downloading anything."""
    config = _build(site, base_url, delay_seconds=delay, timeout_seconds=timeout)
    click.echo(f"{config.slug} - {config.base_url}")
    with RestClient(config) as client:
        totals: dict[str, int | None] = {}
        for endpoint in INVENTORY_ENDPOINTS:
            try:
                totals[endpoint] = client.total(endpoint)
            except Exception as exc:  # noqa: BLE001 - report, never abort the sweep
                totals[endpoint] = None
                click.echo(f"  {endpoint:18} error: {exc}", err=True)
        for endpoint, total in totals.items():
            shown = total if total is not None else "n/a"
            click.echo(f"  {endpoint:18} {shown:>8}")
        click.echo(f"  ({client.request_count} requests, {client.retry_count} retries)")


@cli.command()
@site_options
@throttle_options
@click.option("--only", default=None, help="Comma-separated subset of collections.")
@click.option(
    "--resume/--restart",
    default=True,
    show_default=True,
    help="Continue from the saved page cursor.",
)
@click.option(
    "--context",
    type=click.Choice(["view", "edit"]),
    default="view",
    show_default=True,
    help="'edit' returns raw post_content but requires authentication.",
)
@click.option(
    "--output-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Override the output directory.",
)
def harvest(
    site: str,
    base_url: str | None,
    delay: float,
    timeout: float,
    only: str | None,
    resume: bool,
    context: str,
    output_dir: Path | None,
) -> None:
    """Harvest collections to JSONL and write a report."""
    config = _build(
        site,
        base_url,
        output_dir=output_dir,
        delay_seconds=delay,
        timeout_seconds=timeout,
    )
    keys = None
    if only:
        keys = [k.strip() for k in only.split(",") if k.strip()]
        unknown = [k for k in keys if k not in COLLECTIONS_BY_KEY]
        if unknown:
            known = ", ".join(COLLECTIONS_BY_KEY)
            raise click.ClickException(
                f"Unknown collection(s): {', '.join(unknown)}. Known: {known}"
            )

    click.echo(f"Harvesting {config.slug} from {config.base_url} (context={context})")
    with RestClient(config) as client:
        results = harvest_site(
            config, keys, resume=resume, context=context, client=client, progress=_echo
        )
        requests_made, retries = client.request_count, client.retry_count

    md_path, _ = report_mod.write(
        config, results, {"requests": requests_made, "retries": retries}
    )
    click.echo("")
    for result in results:
        flag = "ok        " if result.complete else "INCOMPLETE"
        reported = result.reported_total if result.reported_total is not None else "?"
        click.echo(
            f"  {flag} {result.key:11} {result.unique_ids:>6} unique / {reported} reported"
        )
    click.echo(f"\n{requests_made} requests, {retries} retries")
    click.echo(f"Report: {md_path}")
    if any(not r.complete for r in results):
        click.echo("Some collections are incomplete - re-run with --resume.", err=True)
        sys.exit(1)


@cli.command()
@site_options
@throttle_options
def sitemap(site: str, base_url: str | None, delay: float, timeout: float) -> None:
    """Walk the sitemap index and save every declared URL."""
    config = _build(site, base_url, delay_seconds=delay, timeout_seconds=timeout)
    with RestClient(config) as client:
        result = sitemap_mod.harvest(client, progress=_echo)
    if result["index"] is None:
        raise click.ClickException(f"No sitemap found at {config.base_url}")

    out = config.ensure_output_dir()
    urls_path = out / "sitemap_urls.txt"
    urls_path.write_text("\n".join(result["urls"]) + "\n", encoding="utf-8")
    meta_path = out / "sitemap.json"
    meta_path.write_text(
        json.dumps(
            {
                "index": result["index"],
                "children": result["by_child"],
                "url_count": len(result["urls"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    click.echo(
        f"\n{len(result['urls']):,} URLs across {len(result['children'])} child sitemaps"
    )
    click.echo(f"Wrote {urls_path}")


@cli.command()
@site_options
@throttle_options
@click.option(
    "--against",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="JSONL or text file of stored URLs to compare against the live sitemap.",
)
@click.option(
    "--field", default="legacy_url", show_default=True, help="JSONL field holding the URL."
)
@click.option(
    "--http-check",
    default=0,
    show_default=True,
    help="HTTP-check this many URLs missing from the sitemap (0 = none, -1 = all).",
)
def verify(
    site: str,
    base_url: str | None,
    delay: float,
    timeout: float,
    against: Path,
    field: str,
    http_check: int,
) -> None:
    """Set-compare a stored permalink list against the live sitemap (F16)."""
    config = _build(site, base_url, delay_seconds=delay, timeout_seconds=timeout)

    if against.suffix == ".jsonl":
        rows = read_jsonl(against)
        stored = [str(r[field]) for r in rows if r.get(field)]
        if not stored:
            keys = sorted({k for r in rows[:20] for k in r})
            raise click.ClickException(
                f"No values for field {field!r} in {against.name}. "
                f"Available: {', '.join(keys)}"
            )
    else:
        stored = [
            line.strip()
            for line in against.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    with RestClient(config) as client:
        site_map = sitemap_mod.harvest(client, progress=_echo)
        if site_map["index"] is None:
            raise click.ClickException(f"No sitemap found at {config.base_url}")

        comparison = compare_to_sitemap(
            stored, site_map["urls"], default_host=host_of(config.base_url)
        )
        missing = comparison["missing_from_sitemap"]
        click.echo("")
        click.echo(f"  stored URLs        : {comparison['stored']:,}")
        click.echo(f"  live sitemap URLs  : {comparison['live']:,}")
        click.echo(f"  matched            : {comparison['matched']:,}")
        click.echo(f"  missing from live  : {len(missing):,}")
        click.echo(f"  live but not stored: {len(comparison['not_in_stored_map']):,}")

        checks: list[dict[str, Any]] = []
        if http_check and missing:
            subset = missing if http_check < 0 else missing[:http_check]
            # The permalink map stores paths; HTTP needs absolute URLs.
            subset = [urljoin(config.base_url + "/", u) for u in subset]
            click.echo(f"\nHTTP-checking {len(subset):,} URLs missing from the sitemap...")
            results = check_urls(client, subset, progress=_echo)
            checks = [r.as_dict() for r in results]
            counts = summarise(results)
            click.echo("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

        requests_made, retries = client.request_count, client.retry_count

    payload = {
        "site": config.slug,
        "base_url": config.base_url,
        "stored_source": str(against),
        "sitemap_index": site_map["index"],
        "stored": comparison["stored"],
        "live": comparison["live"],
        "matched": comparison["matched"],
        "missing_from_sitemap": missing,
        "not_in_stored_map": comparison["not_in_stored_map"][:500],
        "http_checks": checks,
        "requests": requests_made,
        "retries": retries,
    }
    path = config.ensure_output_dir() / "url_verification.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"\nWrote {path}")


if __name__ == "__main__":
    cli()
