from __future__ import annotations

import json
from pathlib import Path

import click
from sqlalchemy import create_engine

from now_db import provisioning
from now_db.partitions import drop_partitions_older_than, ensure_daily_partitions
from now_db.schema_hash import compute_hash, diff_structures
from now_db.settings import city_database_url
from now_db.facet_sync import find_facet_drift, format_facet_drift_report, has_facet_drift
from now_db.term_refs import find_orphaned_term_refs, format_orphan_report, has_live_orphans
from now_platform_db.settings import platform_database_url

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = PACKAGE_ROOT / "schema_baseline.json"


@click.group()
def cli() -> None:
    """now-db: the city-DB migration runner — site:create, site:migrate, schema hash gate."""


@cli.command("create")
@click.argument("slug")
@click.option("--hostname", required=True)
@click.option("--name", required=True)
@click.option("--locale", default="en", show_default=True)
@click.option("--timezone", default="Asia/Jakarta", show_default=True)
@click.option("--currency", default="IDR", show_default=True)
@click.option("--module", "modules", multiple=True, help="enabled_modules entry (repeatable)")
def create(slug: str, hostname: str, name: str, locale: str, timezone: str, currency: str, modules: tuple[str, ...]) -> None:
    """Provision <slug>: create DB, migrate, seed, register, scaffold dirs.

    Idempotent — safe to re-run against an already-provisioned slug.
    """
    result = provisioning.create_site(
        slug,
        hostname=hostname,
        name=name,
        locale=locale,
        timezone=timezone,
        currency=currency,
        enabled_modules=list(modules),
    )
    click.echo(f"[now-db] database: {result.db_name} ({'created' if result.created_database else 'already existed'})")
    click.echo(f"[now-db] migrated to head: {result.dsn}")
    click.echo(
        "[now-db] partitions created: "
        + (", ".join(result.partitions_created) if result.partitions_created else "(none needed)")
    )
    click.echo(
        "[now-db] scaffolded: "
        + (", ".join(str(p) for p in result.scaffolded_dirs) if result.scaffolded_dirs else "(already present)")
    )
    click.echo(f"[now-db] site:create {slug} — done")


@cli.command("migrate")
@click.option("--all", "all_sites", is_flag=True, help="Iterate the sites registry and migrate every city.")
@click.option("--url", default=None, help="Migrate exactly one DSN, or a bare db_ref (e.g. now_jakarta).")
def migrate(all_sites: bool, url: str | None) -> None:
    """site:migrate — apply pending migrations to one or every city (idempotent)."""
    if url and all_sites:
        raise click.UsageError("pass either --all or --url, not both")
    if url:
        dsn = city_database_url(url)
        provisioning.migrate_city(dsn)
        created = provisioning.ensure_city_partitions(dsn)
        click.echo(f"[now-db] migrated {url} to head")
        click.echo("[now-db] partitions created: " + (", ".join(created) if created else "(none needed)"))
        _echo_term_ref_orphans({url: _safe_find_term_ref_orphans(url, dsn)})
        _echo_facet_drift({url: _safe_find_facet_drift(url, dsn)})
        return
    if not all_sites:
        raise click.UsageError("pass --all to migrate every registered city, or --url for a single DSN")
    result = provisioning.migrate_all()
    click.echo(f"[now-db] migrated {len(result.migrated)} site(s): {', '.join(result.migrated) or '(none registered)'}")
    for slug, created in result.partitions_created.items():
        click.echo(f"[now-db]   {slug}: partitions created = " + (", ".join(created) if created else "(none needed)"))
    _echo_term_ref_orphans(result.term_ref_orphans)
    _echo_facet_drift(result.facet_drift)


def _safe_find_term_ref_orphans(label: str, dsn: str) -> list | None:
    """F92 check for `migrate --url`, best-effort: a platform-DB
    connectivity hiccup here must not fail an otherwise-successful
    migration run (the migration itself already committed above by the
    time this runs) — mirrors `migrate_all()`'s own defensiveness in
    `now_db.provisioning`. Returns `None` (not `[]`) on failure, so the
    caller can tell "checked, clean" apart from "could not check" instead
    of misreporting the latter as the former."""
    platform_engine = create_engine(platform_database_url())
    city_engine = create_engine(dsn)
    try:
        with platform_engine.connect() as platform_conn, city_engine.connect() as city_conn:
            return find_orphaned_term_refs(city_conn, platform_conn)
    except Exception as exc:
        click.echo(f"[now-db] vocabulary integrity check skipped for {label} — could not complete: {exc}", err=True)
        return None
    finally:
        platform_engine.dispose()
        city_engine.dispose()


def _echo_term_ref_orphans(orphans_by_label: dict[str, list | None]) -> None:
    """F92 — print a loud, NON-FATAL vocabulary-integrity summary after a
    migration run, one line of status per site checked. Non-fatal
    deliberately: see `now_db.term_refs` module docstring for why a
    pre-existing data problem in `entity_terms`/`embeddings` must not
    block `migrate`/`migrate --all` from completing successfully. A
    `None` entry means the check itself could not run (already reported
    by whoever produced it) — skipped here, not reported as "clean"."""
    for label, orphans in orphans_by_label.items():
        if orphans is None:
            continue
        if orphans:
            click.echo(f"[now-db] VOCABULARY INTEGRITY WARNING (F92) — {label}:", err=True)
            for line in format_orphan_report(label, orphans):
                click.echo(f"[now-db]   {line}", err=True)
        else:
            click.echo(f"[now-db] vocabulary integrity: OK — {label} has no orphaned term references")


def _safe_find_facet_drift(label: str, dsn: str) -> list | None:
    """F132 check for `migrate --url`, best-effort — same defensiveness as
    `_safe_find_term_ref_orphans` above (a platform-DB hiccup here must not
    fail an otherwise-successful migration)."""
    platform_engine = create_engine(platform_database_url())
    city_engine = create_engine(dsn)
    try:
        with platform_engine.connect() as platform_conn, city_engine.connect() as city_conn:
            return find_facet_drift(city_conn, platform_conn)
    except Exception as exc:
        click.echo(f"[now-db] facet-sync check skipped for {label} — could not complete: {exc}", err=True)
        return None
    finally:
        platform_engine.dispose()
        city_engine.dispose()


def _echo_facet_drift(drift_by_label: dict[str, list | None]) -> None:
    """F132 — print a loud, NON-FATAL articles/entity_terms drift summary
    after a migration run. Non-fatal for the same reason as F92's
    equivalent: this is a pre-existing data problem, not something
    `migrate`/`migrate --all` caused or should refuse to complete over.
    `None` means the check itself could not run."""
    for label, groups in drift_by_label.items():
        if groups is None:
            continue
        if groups:
            click.echo(f"[now-db] FACET SYNC WARNING (F132) — {label}:", err=True)
            for line in format_facet_drift_report(label, groups):
                click.echo(f"[now-db]   {line}", err=True)
        else:
            click.echo(f"[now-db] facet sync: OK — {label} articles/entity_terms agree on type+format")


@cli.command("hash")
@click.option("--url", required=True, help="City DSN, or a bare db_ref (e.g. now_jakarta).")
@click.option("--write-baseline", is_flag=True)
def hash_cmd(url: str, write_baseline: bool) -> None:
    """Print (and optionally record) the structural hash of a city's `engine` schema."""
    dsn = city_database_url(url)
    engine = create_engine(dsn)
    with engine.connect() as conn:
        digest, structure = compute_hash(conn)
    click.echo(digest)
    if write_baseline:
        BASELINE_PATH.write_text(json.dumps({"hash": digest, "structure": structure}, indent=2, sort_keys=True))
        click.echo(f"[now-db] wrote baseline to {BASELINE_PATH}")


@cli.command("check")
@click.option("--url", required=True, help="City DSN, or a bare db_ref (e.g. now_jakarta).")
def check(url: str) -> None:
    """Fail (exit 1) if a city's live schema differs from schema_baseline.json."""
    if not BASELINE_PATH.exists():
        raise click.ClickException(f"no baseline at {BASELINE_PATH}; run `hash --write-baseline` first")
    baseline = json.loads(BASELINE_PATH.read_text())
    dsn = city_database_url(url)
    engine = create_engine(dsn)
    with engine.connect() as conn:
        digest, structure = compute_hash(conn)
    if digest == baseline["hash"]:
        click.echo(f"[now-db] OK — {url}: schema matches baseline ({digest[:12]})")
        return
    diffs = diff_structures(baseline["structure"], structure)
    click.echo(f"[now-db] DRIFT DETECTED in {url} — expected {baseline['hash'][:12]}, got {digest[:12]}", err=True)
    for line in diffs:
        click.echo(f"  - {line}", err=True)
    raise SystemExit(1)


@cli.command("check-term-refs")
@click.option("--url", required=True, help="City DSN, or a bare db_ref (e.g. now_jakarta).")
@click.option("--platform-url", default=None, help="Override the platform DSN (default: NOW_PLATFORM_DATABASE_URL / now-platform-db's usual resolution).")
def check_term_refs(url: str, platform_url: str | None) -> None:
    """F92 — fail (exit 1) if this city references a now_platform.engine.terms
    id that no longer exists (checked across every known source — see
    now_db.term_refs module docstring). A "historical" (Payload review-queue
    snapshot) orphan is reported but does not affect the exit code; a
    "live" one (engine.entity_terms, engine.embeddings) does."""
    dsn = city_database_url(url)
    p_dsn = platform_url or platform_database_url()
    city_engine = create_engine(dsn)
    platform_engine = create_engine(p_dsn)
    try:
        with city_engine.connect() as city_conn, platform_engine.connect() as platform_conn:
            orphans = find_orphaned_term_refs(city_conn, platform_conn)
    finally:
        city_engine.dispose()
        platform_engine.dispose()

    if not orphans:
        click.echo(f"[now-db] OK — {url}: every known term reference resolves in the platform vocabulary")
        return

    click.echo(f"[now-db] TERM REFERENCE ISSUE(S) in {url}:", err=True)
    for line in format_orphan_report(url, orphans):
        click.echo(f"  {line}", err=True)

    if has_live_orphans(orphans):
        raise SystemExit(1)
    click.echo(f"[now-db] no LIVE orphans — exit 0 (historical/snapshot-only references reported above)")


@cli.command("check-facet-sync")
@click.option("--url", required=True, help="City DSN, or a bare db_ref (e.g. now_jakarta).")
@click.option("--platform-url", default=None, help="Override the platform DSN (default: NOW_PLATFORM_DATABASE_URL / now-platform-db's usual resolution).")
def check_facet_sync(url: str, platform_url: str | None) -> None:
    """F132 — fail (exit 1) if this city's `public.articles.primary_type`/
    `.format` disagrees with `engine.entity_terms`, or is set with no
    corresponding `entity_terms` row at all. Unlike `check-term-refs`,
    every finding here is LIVE (this is the actual CMS-facing data, not a
    historical snapshot), so any finding fails the check."""
    dsn = city_database_url(url)
    p_dsn = platform_url or platform_database_url()
    city_engine = create_engine(dsn)
    platform_engine = create_engine(p_dsn)
    try:
        with city_engine.connect() as city_conn, platform_engine.connect() as platform_conn:
            groups = find_facet_drift(city_conn, platform_conn)
    finally:
        city_engine.dispose()
        platform_engine.dispose()

    if not groups:
        click.echo(f"[now-db] OK — {url}: articles.{{primary_type,format}} agrees with entity_terms everywhere")
        return

    click.echo(f"[now-db] FACET SYNC ISSUE(S) in {url}:", err=True)
    for line in format_facet_drift_report(url, groups):
        click.echo(f"  {line}", err=True)

    if has_facet_drift(groups):
        raise SystemExit(1)


@cli.command("ensure-partitions")
@click.option("--url", required=True)
@click.option("--days-ahead", default=7, show_default=True)
def ensure_partitions(url: str, days_ahead: int) -> None:
    dsn = city_database_url(url)
    engine = create_engine(dsn)
    with engine.begin() as conn:
        created = ensure_daily_partitions(conn, days_ahead=days_ahead)
    click.echo(f"[now-db] {url}: " + (f"created {', '.join(created)}" if created else "no new partitions needed"))


@cli.command("drop-old-partitions")
@click.option("--url", required=True)
@click.option("--retention-days", required=True, type=int)
def drop_old_partitions(url: str, retention_days: int) -> None:
    dsn = city_database_url(url)
    engine = create_engine(dsn)
    with engine.begin() as conn:
        dropped = drop_partitions_older_than(conn, retention_days=retention_days)
    click.echo(f"[now-db] {url}: " + (f"dropped {', '.join(dropped)}" if dropped else "nothing older than retention window"))


if __name__ == "__main__":
    cli()
