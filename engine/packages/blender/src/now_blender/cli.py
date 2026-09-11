from __future__ import annotations

import json

import click

from now_blender.connections import city_engine, platform_engine
from now_blender.reranker import BlenderReranker
from now_blender.weights import DEFAULT_WEIGHTS, load_blend_weights, seed_default_blend_weights

HAND_CHECK_QUERIES = [
    "rooftop bar senopati",
    "best italian restaurant",
    "things to do in ubud with kids",
    "cheap eats jakarta",
    "spa jakarta selatan",
    "coworking space jakarta",
    "hotel with pool jakarta",
    "brunch spots kemang",
    "live music venue jakarta",
    "yoga studio jakarta",
]


@click.group()
def cli() -> None:
    """now-blender -- E3.3 blend + MMR re-ranker. See ARCHITECTURE.md §7/§8.D."""


@cli.command("search")
@click.argument("query")
@click.option("--db", "db_ref", required=True)
@click.option("--site", "site_slug", default=None, help="Site slug for live sites.ranking_weights (e.g. jakarta).")
@click.option("-k", "k", default=10, show_default=True)
@click.option("--synthetic-formats", is_flag=True, help="Overlay a deterministic synthetic `format` (F50) to exercise type-aware decay.")
@click.option("--json", "as_json", is_flag=True)
def search_cmd(query: str, db_ref: str, site_slug: str | None, k: int, synthetic_formats: bool, as_json: bool) -> None:
    """Run one query through the blend + MMR re-ranker and print the
    final top-k with per-component scores."""
    city = city_engine(db_ref)
    platform = platform_engine() if site_slug else None
    city_conn = city.connect()
    platform_conn = platform.connect() if platform is not None else None
    try:
        reranker = BlenderReranker.build(city_conn, platform_conn=platform_conn, site_slug=site_slug)
        result = reranker.rerank(query, k=k, synthetic_format_overlay=synthetic_formats)

        if as_json:
            payload = {
                "query": result.query,
                "weights_source": result.weights_source,
                "decay_source": result.decay_source,
                "synthetic_format_overlay": result.synthetic_format_overlay,
                "hits": [
                    {
                        "article_id": h.entity_id,
                        "final_rank": h.final_rank,
                        "blend_score": h.blend_score,
                        "format": h.format_,
                        "format_is_synthetic": h.format_is_synthetic,
                        "components": [
                            {"key": c.key, "value": c.value, "weight": c.weight, "available": c.available}
                            for c in h.components
                        ],
                    }
                    for h in result.hits
                ],
            }
            click.echo(json.dumps(payload, indent=2))
            return

        click.echo(f"query: {query!r}   weights: {result.weights_source}   decay: {result.decay_source}")
        click.echo(f"rerank_pool={result.rerank_pool_size}  mmr_missing_embeddings={result.mmr_missing_embeddings}  mmr_fallback_calls={result.mmr_fallback_calls}")
        click.echo(f"synthetic_format_overlay={result.synthetic_format_overlay}")
        click.echo(f"timing: {result.timing}")
        click.echo("")
        for h in result.hits:
            comp_str = " ".join(f"{c.key}={c.value:.3f}" if c.value is not None else f"{c.key}=None" for c in h.components)
            click.echo(f"{h.final_rank:2d}. [{h.entity_id:>6}] blend={h.blend_score:.4f} format={h.format_}  {comp_str}")
    finally:
        city_conn.close()
        if platform_conn is not None:
            platform_conn.close()


@cli.command("handcheck")
@click.option("--db", "db_ref", required=True)
@click.option("--site", "site_slug", default=None)
@click.option("-k", "k", default=10, show_default=True)
@click.option("--synthetic-formats", is_flag=True)
def handcheck_cmd(db_ref: str, site_slug: str | None, k: int, synthetic_formats: bool) -> None:
    """Run the ~10 canonical hand-check queries and print full results
    for a human to eyeball -- 'metrics can pass while results are
    useless', so this exists to actually look (same rationale as
    now-search's handcheck command)."""
    city = city_engine(db_ref)
    platform = platform_engine() if site_slug else None
    city_conn = city.connect()
    platform_conn = platform.connect() if platform is not None else None
    try:
        reranker = BlenderReranker.build(city_conn, platform_conn=platform_conn, site_slug=site_slug)
        for q in HAND_CHECK_QUERIES:
            result = reranker.rerank(q, k=k, synthetic_format_overlay=synthetic_formats, log_features=False)
            summaries = reranker.fetch_summaries([h.entity_id for h in result.hits])
            click.echo(f"=== {q!r}  (total {result.timing.total_ms:.1f}ms) ===")
            for h in result.hits:
                title = summaries[h.entity_id].title if h.entity_id in summaries else "(missing)"
                click.echo(f"  {h.final_rank:2d}. [{h.entity_id:>6}] blend={h.blend_score:.4f} format={h.format_}  {title}")
            click.echo("")
    finally:
        city_conn.close()
        if platform_conn is not None:
            platform_conn.close()


@cli.command("show-weights")
@click.option("--site", "site_slug", required=True)
def show_weights_cmd(site_slug: str) -> None:
    """Prove weights are live-editable: prints exactly what
    `sites.ranking_weights['blend']` resolves to right now, with source."""
    platform = platform_engine()
    conn = platform.connect()
    try:
        resolved = load_blend_weights(conn, site_slug)
        click.echo(f"site: {site_slug}")
        click.echo(f"source: {resolved.source}")
        click.echo(json.dumps(resolved.weights.as_dict(), indent=2))
    finally:
        conn.close()


@cli.command("seed-weights")
@click.option("--site", "site_slug", required=True)
def seed_weights_cmd(site_slug: str) -> None:
    """Writes this package's default blend weights into
    `sites.ranking_weights['blend']` for one site, unless already
    present (idempotent -- see weights.py)."""
    platform = platform_engine()
    conn = platform.connect()
    try:
        with conn.begin():
            written = seed_default_blend_weights(conn, site_slug)
        click.echo(f"site={site_slug} written={written} defaults={json.dumps(DEFAULT_WEIGHTS.as_dict())}")
    finally:
        conn.close()


@cli.command("eval")
@click.option("--db", "db_ref", required=True)
@click.option("--baseline", "baseline_path", type=click.Path(exists=True), default=None)
def eval_cmd(db_ref: str, baseline_path: str | None) -> None:
    """Wire the blend + MMR re-ranker into now_eval's harness (real
    data only, no synthetic format overlay -- see eval_sut.py's
    docstring) and report nDCG@10 vs. the recorded trivial-random
    baseline, same shape as `now-search eval`."""
    from pathlib import Path

    from now_eval.baseline import load_baseline
    from now_eval.datasets.search_queries import build_provisional_query_set
    from now_eval.datasets.sources import load_articles
    from now_eval.harness import evaluate_search

    from now_blender.eval_sut import BlenderEvalSUT

    if baseline_path is None:
        baseline_path = str(Path(__file__).resolve().parents[3] / "eval" / "data" / "baseline.json")

    click.echo("Loading now_eval's provisional search query set + article corpus...")
    queries = build_provisional_query_set()
    all_articles = load_articles()
    all_article_ids = [a.article_id for a in all_articles]
    click.echo(f"  {len(queries)} queries, {len(all_article_ids)} candidate article ids")

    engine = city_engine(db_ref)
    conn = engine.connect()
    try:
        click.echo("Warming up BlenderReranker (embedding model load)...")
        sut = BlenderEvalSUT.build(conn)

        click.echo("Running evaluate_search()...")
        result = evaluate_search(sut, queries, all_article_ids, k=10)

        baseline_doc = load_baseline(Path(baseline_path))
        baseline_value = None
        if baseline_doc is not None:
            baseline_value = baseline_doc.get("results", {}).get("search", {}).get("value")

        click.echo("")
        click.echo(f"surface:  {result.surface}")
        click.echo(f"metric:   {result.metric}")
        click.echo(f"n:        {result.n}")
        click.echo(f"value:    {result.value:.6f}")
        if baseline_value is not None:
            click.echo(f"baseline: {baseline_value:.6f}")
            click.echo(f"delta:    {result.value - baseline_value:+.6f}")
    finally:
        conn.close()


if __name__ == "__main__":
    cli()
