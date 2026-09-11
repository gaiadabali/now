from __future__ import annotations

import json
import time

import click

from now_rails.connections import city_engine, platform_engine
from now_rails.orchestrator import ArticleNotFoundError, RailsOrchestrator


@click.group()
def cli() -> None:
    """now-rails -- E3.5-E3.8 rails + rails API backing package. See
    ARCHITECTURE.md Sec.7/Sec.16."""


@cli.command("show")
@click.option("--db", "db_ref", required=True)
@click.option("--article-id", "article_id", required=True, type=int)
@click.option("--site", "site_slug", default=None, help="Site slug for live sites.ranking_weights (e.g. jakarta).")
@click.option("-k", "k", default=6, show_default=True)
@click.option("--synthetic-overlay", is_flag=True, help="Overlay deterministic primary_type/format (F50) to exercise competitor exclusion + freshness end to end.")
@click.option("--force-refresh", is_flag=True, help="Bypass engine.rail_cache and recompute.")
@click.option("--json", "as_json", is_flag=True)
def show_cmd(db_ref: str, article_id: int, site_slug: str | None, k: int, synthetic_overlay: bool, force_refresh: bool, as_json: bool) -> None:
    """Compute (or read from cache) all three rails for one article and
    print them, with rung + timing."""
    city = city_engine(db_ref)
    platform = platform_engine() if site_slug else None
    with city.connect() as city_conn, (platform.connect() if platform is not None else _NullConn()) as platform_conn:
        orch = RailsOrchestrator.build(city_conn, platform_conn=platform_conn if site_slug else None, site_slug=site_slug)
        t0 = time.perf_counter()
        try:
            bundle = orch.compute_rails(article_id, k=k, synthetic_overlay=synthetic_overlay, force_refresh=force_refresh)
        except ArticleNotFoundError as exc:
            raise click.ClickException(str(exc)) from exc
        wall_ms = (time.perf_counter() - t0) * 1000

        if as_json:
            out = {
                "article_id": bundle.article_id,
                "segment": bundle.segment,
                "cache_hit": bundle.cache_hit,
                "wall_ms": round(wall_ms, 2),
                "synthetic_overlay": bundle.synthetic_overlay,
                "rails": {name: r.as_dict() for name, r in bundle.rails.items()},
            }
            click.echo(json.dumps(out, indent=2, default=str))
            return

        click.echo(f"article_id={bundle.article_id} segment={bundle.segment} cache_hit={bundle.cache_hit} wall_ms={wall_ms:.2f}")
        if bundle.timing is not None:
            t = bundle.timing
            click.echo(f"  timing: subject={t.subject_ms:.2f}ms row1={t.row1_ms:.2f}ms row2={t.row2_ms:.2f}ms row3={t.row3_ms:.2f}ms total={t.total_ms:.2f}ms")
        for name, result in bundle.rails.items():
            click.echo(f"\n== {name} == rung={result.rung_name}({result.rung_index}) pool={result.pool_size} subject_type={result.subject_type}")
            if result.unvalidated_reason:
                click.echo(f"  UNVALIDATED: {result.unvalidated_reason}")
            for item in result.items:
                click.echo(f"  #{item.position} {item.entity_type}:{item.entity_id} score={item.score:.4f} title={item.title!r}")


class _NullConn:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False
