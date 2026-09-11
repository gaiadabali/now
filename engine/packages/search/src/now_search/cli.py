from __future__ import annotations

import json
import statistics
import time

import click

from now_search.connections import city_engine
from now_search.engine import SearchEngine

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
    """now-search -- E3.1 hybrid search (BM25 + pgvector + RRF). See ARCHITECTURE.md §7."""


@cli.command("search")
@click.argument("query")
@click.option("--db", "db_ref", required=True, help="City db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option("-k", "k", default=10, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def search_cmd(query: str, db_ref: str, k: int, as_json: bool) -> None:
    """Run one query and print the fused top-k with per-rail scores."""
    engine = city_engine(db_ref)
    se = SearchEngine.from_engine_dedicated_connection(engine)
    try:
        se.warm_up()
        result = se.search(query, k=k)
        summaries = se.fetch_summaries([int(h.entity_id) for h in result.hits])
        if as_json:
            payload = {
                "query": result.query,
                "timing_ms": result.timing.__dict__,
                "hits": [
                    {
                        "article_id": h.entity_id,
                        "title": summaries[int(h.entity_id)].title if int(h.entity_id) in summaries else None,
                        "rrf_score": h.rrf_score,
                        "lexical_rank": h.lexical_rank,
                        "semantic_rank": h.semantic_rank,
                    }
                    for h in result.hits
                ],
                "facet_counts": result.facet_counts,
            }
            click.echo(json.dumps(payload, indent=2))
            return

        click.echo(f"query: {query!r}")
        click.echo(
            f"timing: lexical={result.timing.lexical_ms:.1f}ms "
            f"semantic={result.timing.semantic_ms:.1f}ms "
            f"fuse={result.timing.fuse_ms:.1f}ms "
            f"total={result.timing.total_ms:.1f}ms"
        )
        click.echo(f"candidates: lexical={result.lexical_candidate_count} semantic={result.semantic_candidate_count}")
        click.echo("")
        for i, h in enumerate(result.hits, start=1):
            aid = int(h.entity_id)
            title = summaries[aid].title if aid in summaries else "(missing)"
            click.echo(
                f"{i:2d}. [{aid:>6}] rrf={h.rrf_score:.5f} "
                f"lex_rank={h.lexical_rank} sem_rank={h.semantic_rank}  {title}"
            )
        click.echo("")
        click.echo(f"facet_counts: {result.facet_counts}")
    finally:
        se.close()


@cli.command("handcheck")
@click.option("--db", "db_ref", required=True, help="City db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option("-k", "k", default=10, show_default=True)
def handcheck_cmd(db_ref: str, k: int) -> None:
    """Run the ~10 canonical hand-check queries from the task brief and
    print full results for a human to eyeball -- 'metrics can pass while
    results are useless', so this exists to actually look."""
    engine = city_engine(db_ref)
    se = SearchEngine.from_engine_dedicated_connection(engine)
    try:
        se.warm_up()
        for q in HAND_CHECK_QUERIES:
            result = se.search(q, k=k)
            summaries = se.fetch_summaries([int(h.entity_id) for h in result.hits])
            click.echo(f"=== {q!r}  (total {result.timing.total_ms:.1f}ms) ===")
            for i, h in enumerate(result.hits, start=1):
                aid = int(h.entity_id)
                title = summaries[aid].title if aid in summaries else "(missing)"
                click.echo(f"  {i:2d}. [{aid:>6}] rrf={h.rrf_score:.5f} lex={h.lexical_rank} sem={h.semantic_rank}  {title}")
            click.echo("")
    finally:
        se.close()


@cli.command("bench")
@click.option("--db", "db_ref", required=True, help="City db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option("-k", "k", default=10, show_default=True)
@click.option("--queries", "queries_path", type=click.Path(exists=True), default=None,
              help="Newline-delimited query file. Defaults to the 10 hand-check queries repeated to --n.")
@click.option("-n", "n", default=100, show_default=True, help="Number of timed queries to run.")
def bench_cmd(db_ref: str, k: int, queries_path: str | None, n: int) -> None:
    """Measure p50/p95/p99 latency over N queries. Warm-up (fastembed
    ONNX model load only, post-F41 -- the lexical side has no warm-up
    cost anymore, see engine.py/lexical.py) happens first and is reported
    separately, never mixed into the per-query timings this reports."""
    if queries_path:
        with open(queries_path, "r", encoding="utf-8") as fh:
            base_queries = [line.strip() for line in fh if line.strip()]
    else:
        base_queries = HAND_CHECK_QUERIES

    queries = [base_queries[i % len(base_queries)] for i in range(n)]

    engine = city_engine(db_ref)
    se = SearchEngine.from_engine_dedicated_connection(engine)
    try:
        warm = se.warm_up()
        click.echo(f"warm-up: embed_model_load={warm.embedding_model_load_ms:.1f}ms")

        totals: list[float] = []
        for q in queries:
            t0 = time.perf_counter()
            se.search(q, k=k)
            totals.append((time.perf_counter() - t0) * 1000)

        totals.sort()
        click.echo(f"n={len(totals)}")
        click.echo(f"p50={statistics.median(totals):.2f}ms")
        click.echo(f"p95={totals[int(len(totals) * 0.95) - 1]:.2f}ms")
        click.echo(f"p99={totals[int(len(totals) * 0.99) - 1]:.2f}ms")
        click.echo(f"max={max(totals):.2f}ms")
        click.echo(f"min={min(totals):.2f}ms")
    finally:
        se.close()


@cli.command("eval")
@click.option("--db", "db_ref", required=True, help="City db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option("--baseline", "baseline_path", type=click.Path(exists=True), default=None,
              help="Path to now-eval's baseline.json. Defaults to engine/packages/eval/data/baseline.json.")
def eval_cmd(db_ref: str, baseline_path: str | None) -> None:
    """Wire this package's hybrid search into now_eval's harness as a
    real SystemUnderTest and report nDCG@10 vs. the recorded
    trivial-random baseline. Imports now_eval's public API only
    (evaluate_search, dataset builders, baseline loader) -- no eval file
    is created or modified; see now_search/eval_sut.py's docstring for
    why the adapter itself lives in this package instead of under
    now_eval/sut/."""
    from pathlib import Path

    from now_eval.baseline import load_baseline
    from now_eval.datasets.search_queries import build_provisional_query_set
    from now_eval.datasets.sources import load_articles
    from now_eval.harness import evaluate_search

    from now_search.eval_sut import SearchEvalSUT

    if baseline_path is None:
        # cli.py -> now_search -> src -> search -> packages (parents[3])
        baseline_path = str(Path(__file__).resolve().parents[3] / "eval" / "data" / "baseline.json")

    click.echo("Loading now_eval's provisional search query set + article corpus...")
    queries = build_provisional_query_set()
    all_articles = load_articles()
    all_article_ids = [a.article_id for a in all_articles]
    click.echo(f"  {len(queries)} queries, {len(all_article_ids)} candidate article ids")

    engine = city_engine(db_ref)
    conn = engine.connect()
    try:
        click.echo("Warming up SearchEngine (embedding model load)...")
        sut = SearchEvalSUT.build(conn)

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
            delta = result.value - baseline_value
            click.echo(f"baseline: {baseline_value:.6f}  (trivial-random, {baseline_doc.get('recorded_at')})")
            click.echo(f"delta:    {delta:+.6f}  ({'PASS' if delta >= -1e-9 else 'FAIL'} no-regression gate)")
        else:
            click.echo("baseline: (none found / could not load)")
    finally:
        conn.close()


@cli.command("backfill-tsv")
@click.option("--db", "db_ref", required=True, help="City db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option("--batch-size", default=200, show_default=True)
@click.option("--no-prune", is_flag=True, help="Skip deleting article_search rows for articles no longer published.")
def backfill_tsv_cmd(db_ref: str, batch_size: int, no_prune: bool) -> None:
    """F41: build/refresh `engine.article_search` for every published
    article in DB using the real `now_content_clean.metrics.visible_text_out`
    extractor (handles list/gallery/columns blocks -- the F40 fix).
    Idempotent: rerun with nothing changed rewrites nothing."""
    from now_search.tsv_pipeline import backfill_tsv

    engine = city_engine(db_ref)
    t0 = time.time()
    stats = backfill_tsv(engine, batch_size=batch_size, prune_stale=not no_prune)
    dt = time.time() - t0
    click.echo(
        f"[now-search] tsv backfill: total={stats.total} updated={stats.updated} "
        f"skipped_unchanged={stats.skipped_unchanged} deleted_stale={stats.deleted_stale} ({dt:.1f}s)"
    )


@cli.command("tsv-worker")
@click.option("--redis-url", default=None, help="Overrides REDIS_URL env var.")
@click.option("--once", is_flag=True, help="Process whatever is currently pending, then exit (default: run forever).")
@click.option("--block-ms", default=5000, show_default=True)
def tsv_worker_cmd(redis_url: str | None, once: bool, block_ms: int) -> None:
    """F41: consume `article.published`/`article.republished` off
    `now:domain-events:stream` (own consumer group `now-search-tsv-worker`,
    distinct from now-embeddings' worker) and refresh
    `engine.article_search` for the referenced article."""
    from now_search.tsv_worker import GROUP, TsvRefreshWorker

    w = TsvRefreshWorker(redis_url=redis_url)
    click.echo(f"[now-search] tsv worker started, group={GROUP}, once={once}")
    if once:
        result = w.run_once(block_ms=block_ms)
        click.echo(
            f"[now-search] processed={result.processed} updated={result.updated} "
            f"skipped_unchanged={result.skipped_unchanged} ignored={result.ignored} errors={result.errors}"
        )
        return
    w.run_forever()


if __name__ == "__main__":
    cli()
