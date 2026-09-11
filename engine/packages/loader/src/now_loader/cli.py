"""`now-loader` — E1.8 CLI.

    now-loader load  --city now_jakarta --input-dir jakarta/content/extracted
    now-loader load  --city now_bali    --input-dir jakarta/content/extracted --limit 50
    now-loader verify --city now_jakarta --input-dir jakarta/content/extracted --sample 25

No site name ever appears in this module or anything it imports — `--city`
(a bare `db_ref`) and `--input-dir` are both required, ordinary CLI
arguments. Nothing here defaults to "jakarta".

E4.1 adds one command that targets the shared **platform** DB instead of a
city DB — org candidacy (ARCHITECTURE.md §5) is platform-wide, not
per-city, so it has no `--city` at all:

    now-loader load-orgs --roster jakarta/content/extracted/partner_roster.jsonl
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path

import click
from now_content_clean import clean_article
from now_platform_db.settings import platform_database_url
from sqlalchemy import create_engine, text

from now_loader.dbutil import get_engine, table_count
from now_loader.ledger import EventLedger
from now_loader.load_articles import load_articles
from now_loader.load_authors import load_authors
from now_loader.load_events import load_events
from now_loader.load_media import load_media
from now_loader.load_orgs import load_orgs
from now_loader.load_places import load_places
from now_loader.reportgen import write_report
from now_loader.sources import iter_jsonl

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"

STAGES = ("authors", "media", "articles", "places", "events")


@click.group()
def cli() -> None:
    """now-loader: E1.8 JSONL -> city DB `public` loader."""


@cli.command()
@click.option("--city", required=True, help="Target city db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option(
    "--input-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing the E1.1 extraction JSONL files (articles.jsonl, attachments.jsonl, events.jsonl, venues.jsonl, users.jsonl).",
)
@click.option("--only", default=None, help=f"Comma-separated subset of stages to run: {','.join(STAGES)}")
@click.option("--limit", default=None, type=int, help="Only process the first N rows of each source file (smoke-testing).")
def load(city: str, input_dir: Path, only: str | None, limit: int | None) -> None:
    """Load every configured stage into `--city`. Idempotent — safe to re-run."""
    stages = [s.strip() for s in only.split(",")] if only else list(STAGES)
    for s in stages:
        if s not in STAGES:
            raise click.UsageError(f"unknown stage '{s}' — choose from {', '.join(STAGES)}")

    engine = get_engine(city)
    sections: dict[str, dict] = {}

    author_map: dict[int, int] = {}
    media_map: dict[int, int] = {}
    known_upload_urls: set[str] = set()
    place_map: dict[int, int] = {}

    if "authors" in stages:
        with engine.begin() as conn:
            result = load_authors(conn, _limited(input_dir / "users.jsonl", limit))
        author_map = result.wp_id_to_author_id or {}
        sections["authors"] = _as_dict(result, exclude={"wp_id_to_author_id"})
        click.echo(f"[now-loader] authors: read={result.read} upserted={result.inserted_or_updated}")

    if "media" in stages:
        with engine.begin() as conn:
            result = load_media(conn, _limited(input_dir / "attachments.jsonl", limit))
        media_map = result.wp_id_to_media_id
        known_upload_urls = set(result.wp_id_to_original_url.values())
        sections["media"] = _as_dict(result, exclude={"wp_id_to_media_id", "wp_id_to_original_url"})
        click.echo(f"[now-loader] media: read={result.read} upserted={result.inserted_or_updated}")

    if "articles" in stages:
        with engine.begin() as conn:
            result = load_articles(
                conn,
                _limited(input_dir / "articles.jsonl", limit),
                author_map,
                media_map,
                known_upload_urls,
            )
        sections["articles"] = _as_dict(result, exclude={"wp_id_to_article_id"})
        click.echo(f"[now-loader] articles: read={result.read} upserted={result.inserted_or_updated}")

    if "places" in stages:
        with engine.begin() as conn:
            result = load_places(conn, _limited(input_dir / "venues.jsonl", limit))
        place_map = result.wp_id_to_place_id
        sections["places"] = _as_dict(result, exclude={"wp_id_to_place_id"})
        click.echo(f"[now-loader] places: read={result.read} upserted={result.inserted_or_updated}")

    if "events" in stages:
        with EventLedger(city) as ledger, engine.begin() as conn:
            result = load_events(
                conn,
                _limited(input_dir / "events.jsonl", limit),
                place_map,
                media_map,
                ledger,
            )
        sections["events"] = _as_dict(result)
        click.echo(f"[now-loader] events: read={result.read} inserted={result.inserted} updated={result.updated}")

    with engine.begin() as conn:
        sections["row counts (post-load)"] = {
            table: table_count(conn, table) for table in ("authors", "media", "articles", "places", "events")
        }
        sections["facet-null guard (should be 0 non-null for primary_type/format on every loaded row)"] = {
            "articles.primary_type NOT NULL count": conn.execute(
                text('SELECT count(*) FROM "public"."articles" WHERE primary_type IS NOT NULL')
            ).scalar_one(),
            "articles.format NOT NULL count": conn.execute(
                text('SELECT count(*) FROM "public"."articles" WHERE format IS NOT NULL')
            ).scalar_one(),
        }

    md_path, json_path = write_report(city, sections, REPORTS_DIR)
    click.echo(f"[now-loader] report written: {md_path}")
    click.echo(f"[now-loader]               {json_path}")


@cli.command()
@click.option("--city", required=True, help="Target city db_ref or full DSN.")
@click.option(
    "--input-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--sample", default=25, show_default=True, help="Number of random articles to round-trip-verify.")
@click.option("--seed", default=42, show_default=True)
def verify(city: str, input_dir: Path, sample: int, seed: int) -> None:
    """Re-derive body_blocks for a random sample of already-loaded articles
    and compare field-by-field (never by raw string — jsonb reorders keys)
    against what's stored. Also re-confirms the facet-NULL guard."""
    engine = get_engine(city)
    articles = list(iter_jsonl(input_dir / "articles.jsonl"))
    random.Random(seed).shuffle(articles)
    sample_articles = articles[:sample]

    mismatches = []
    checked = 0
    with engine.connect() as conn:
        for article in sample_articles:
            wp_id = article["wp_id"]
            row = conn.execute(
                text('SELECT body_blocks FROM "public"."articles" WHERE legacy_wp_id = :wp_id'),
                {"wp_id": wp_id},
            ).fetchone()
            if row is None:
                mismatches.append((wp_id, "not found in DB"))
                continue
            stored_blocks = row[0]
            expected_blocks = clean_article(article).blocks
            checked += 1
            if stored_blocks != expected_blocks:
                mismatches.append((wp_id, "body_blocks differ"))

        facet_leak = conn.execute(
            text(
                'SELECT count(*) FROM "public"."articles" WHERE primary_type IS NOT NULL OR format IS NOT NULL'
            )
        ).scalar_one()

    click.echo(f"[now-loader] verify: checked={checked}/{len(sample_articles)} mismatches={len(mismatches)}")
    for wp_id, reason in mismatches:
        click.echo(f"  - wp_id={wp_id}: {reason}")
    click.echo(f"[now-loader] facet leak (primary_type/format non-null count, expect 0): {facet_leak}")

    if mismatches or facet_leak:
        raise SystemExit(1)


@cli.command("load-orgs")
@click.option(
    "--roster",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="E1.5 candidate-org roster JSONL (e.g. jakarta/content/extracted/partner_roster.jsonl).",
)
@click.option(
    "--platform-url",
    default=None,
    help="Override the platform DSN (defaults to now_platform_db.settings.platform_database_url()).",
)
@click.option(
    "--source-tag",
    default=None,
    help="Provenance tag written to orgs.source for every row this run touches "
    "(default: 'partner_roster:<basename>').",
)
def load_orgs_cmd(roster: Path, platform_url: str | None, source_tag: str | None) -> None:
    """Load candidate orgs from an E1.5 roster into `now_platform.engine.orgs`.

    Unlike `load`, this targets the shared **platform** DB, not a city DB --
    org candidacy is platform-wide (ARCHITECTURE.md §5). Creates ONLY
    `orgs` rows (with confidence/provenance retained, nothing promoted to
    a confirmed fact) -- never a `partnerships` row. Idempotent: safe to
    re-run over a re-extracted roster.
    """
    dsn = platform_url or platform_database_url()
    tag = source_tag or f"partner_roster:{roster.name}"
    engine = create_engine(dsn, future=True)

    with engine.begin() as conn:
        result = load_orgs(conn, roster, source_tag=tag)

    click.echo(
        f"[now-loader] orgs: read={result.read} upserted={result.inserted_or_updated} "
        f"parent_links_set={result.parent_links_set} parent_links_missing={result.parent_links_missing}"
    )
    click.echo(
        f"[now-loader] orgs: synthesized={result.synthesized_count} "
        f"low_confidence(<=0.6)={result.low_confidence_count}"
    )
    click.echo(f"[now-loader] orgs: confidence histogram={result.confidence_histogram}")

    if result.parent_links_missing:
        click.echo(
            f"[now-loader] WARNING: {result.parent_links_missing} row(s) referenced a "
            "parent_org_slug not found in this file -- left parent_org_id unresolved.",
            err=True,
        )

    with engine.begin() as conn:
        sections = {
            "orgs load": {
                "read": result.read,
                "upserted": result.inserted_or_updated,
                "parent_links_set": result.parent_links_set,
                "parent_links_missing": result.parent_links_missing,
                "synthesized_count": result.synthesized_count,
                "low_confidence_count (confidence<=0.6)": result.low_confidence_count,
                "confidence_histogram": result.confidence_histogram,
            },
            "row counts (post-load)": {
                "engine.orgs": conn.execute(text("SELECT count(*) FROM engine.orgs")).scalar_one(),
                "engine.orgs (review_status='pending')": conn.execute(
                    text("SELECT count(*) FROM engine.orgs WHERE review_status = 'pending'")
                ).scalar_one(),
                "engine.partnerships (must stay 0 from this loader)": conn.execute(
                    text("SELECT count(*) FROM engine.partnerships")
                ).scalar_one(),
            },
        }
    md_path, json_path = write_report("now_platform_orgs", sections, REPORTS_DIR)
    click.echo(f"[now-loader] report written: {md_path}")
    click.echo(f"[now-loader]               {json_path}")


_TMP_DIR = Path(__file__).resolve().parents[2] / "state" / "tmp"


def _limited(path: Path, limit: int | None) -> Path:
    """When --limit is set, materialize a truncated copy of the JSONL file
    under this package's own `state/tmp/` (never next to the source file —
    this loader does not write outside `engine/packages/loader/**`) so
    downstream readers don't need their own limit-awareness. Smoke-testing
    convenience only."""
    if limit is None:
        return path
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    limited_path = _TMP_DIR / f"{path.stem}.limit{limit}.jsonl"
    with path.open("r", encoding="utf-8") as src, limited_path.open("w", encoding="utf-8") as dst:
        for i, line in enumerate(src):
            if i >= limit:
                break
            dst.write(line)
    return limited_path


def _as_dict(result: object, exclude: set[str] | None = None) -> dict:
    exclude = exclude or set()
    return {k: v for k, v in asdict(result).items() if k not in exclude}


if __name__ == "__main__":
    cli()
