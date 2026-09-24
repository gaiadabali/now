"""`now-embeddings backfill|knn|sanity-check|worker` -- see README.md for a
full walkthrough. Provider selection is explicit everywhere (`--provider
local|offline`, default `local`) so a CI run or a quick smoke test can
choose `offline` and never touch the network or download a model, and a
real backfill can never accidentally run against the meaningless offline
vectors without saying so.
"""

from __future__ import annotations

import logging
import time

import click
from sqlalchemy import text

from now_embeddings.connections import city_engine, platform_engine
from now_embeddings.pipeline import backfill_entity_type
from now_embeddings.providers.base import EmbeddingProvider
from now_embeddings.models import REGISTRY, active_model_name, get_spec
from now_embeddings.providers.offline import OfflineProvider
from now_embeddings.store import fetch_articles, fetch_places, fetch_terms, knn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


def _provider(name: str, model: str | None = None) -> EmbeddingProvider:
    """`model=None` is the configured model (`now_embeddings.models`:
    NOW_EMBEDDING_MODEL, else DEFAULT_MODEL) -- what the worker and a plain
    `backfill` use. An explicit `--model` is for the rollout backfill of a
    model that is not live yet."""
    if name == "offline":
        return OfflineProvider()
    if name == "local":
        from now_embeddings.providers.local import LocalProvider

        spec = get_spec(model or active_model_name())
        if not spec.storable:
            raise click.UsageError(
                f"{spec.name} is {spec.dim}-d; engine.embeddings.vec holds 384-d vectors only "
                "(migration 0004). Storing it needs a migration first -- see the README, 'Changing model'."
            )
        return LocalProvider(spec.name)
    raise click.UsageError(f"unknown provider {name!r}")


def _model_name_for(provider: str, model: str | None = None) -> str:
    """Resolves `--provider`/`--model` to the `model` value stored in
    `engine.embeddings` -- used by the read-only commands (`knn`,
    `sanity-check`) that look up an *existing* row and must never construct
    a full provider (and pay `LocalProvider`'s model-load cost) just to ask
    it its own name."""
    if provider == "offline":
        return OfflineProvider.name
    return get_spec(model or active_model_name()).name


_model_option = click.option(
    "--model",
    type=click.Choice(sorted(REGISTRY)),
    default=None,
    help="Registered model to use (default: NOW_EMBEDDING_MODEL, else now_embeddings.models.DEFAULT_MODEL). local provider only.",
)


@click.group()
def cli() -> None:
    """now-embeddings: E2.4 provider-abstracted embeddings for engine.embeddings."""


@cli.command()
@click.option("--city", required=True, help="City db_ref, e.g. now_jakarta (bare name or full DSN).")
@click.option(
    "--entity-type",
    "entity_types",
    multiple=True,
    type=click.Choice(["article", "place", "term"]),
    default=("article", "place", "term"),
    help="Repeatable. Default: all three.",
)
@click.option("--provider", type=click.Choice(["local", "offline"]), default="local", show_default=True)
@click.option("--batch-size", default=32, show_default=True)
@click.option("--no-prune", is_flag=True, help="Skip deleting embeddings for entities no longer in the source table.")
@_model_option
def backfill(city: str, entity_types: tuple[str, ...], provider: str, batch_size: int, no_prune: bool, model: str | None) -> None:
    """Embed every article/place/term in CITY that is new or has changed
    text since its last embedding. Idempotent: a rerun with nothing changed
    embeds nothing (every row is skipped on the text_hash check) and exits
    fast."""
    prov = _provider(provider, model)
    click.echo(f"[now-embeddings] provider={prov.name} dim={prov.dim}")
    engine = city_engine(city)

    for entity_type in entity_types:
        t0 = time.time()
        if entity_type == "article":
            with engine.connect() as conn:
                rows = fetch_articles(conn)
        elif entity_type == "place":
            with engine.connect() as conn:
                rows = fetch_places(conn)
        else:  # term
            with platform_engine().connect() as conn:
                rows = fetch_terms(conn)

        stats = backfill_entity_type(
            engine,
            entity_type=entity_type,
            rows=rows,
            provider=prov,
            batch_size=batch_size,
            prune_stale=not no_prune and entity_type != "term",
        )
        dt = time.time() - t0
        click.echo(
            f"[now-embeddings] {entity_type}: total={stats.total} embedded={stats.embedded} "
            f"skipped_unchanged={stats.skipped_unchanged} deleted_stale={stats.deleted_stale} "
            f"errors={len(stats.errors)} ({dt:.1f}s)"
        )
        for err in stats.errors:
            click.echo(f"[now-embeddings]   ERROR: {err}", err=True)


@cli.command("knn")
@click.option("--city", required=True)
@click.option("--entity-type", required=True, type=click.Choice(["article", "place", "term"]))
@click.option("--entity-id", required=True)
@click.option("--k", default=6, show_default=True)
@click.option("--provider", type=click.Choice(["local", "offline"]), default="local", show_default=True)
@click.option("--runs", default=5, show_default=True, help="Repeat the query this many times and report min/median latency.")
@_model_option
def knn_cmd(city: str, entity_type: str, entity_id: str, k: int, provider: str, runs: int, model: str | None) -> None:
    """kNN against an existing embedded entity, with real measured latency
    (per ARCHITECTURE.md §7's <20ms target and the E2.4 acceptance
    criterion)."""
    prov_name = _model_name_for(provider, model)
    engine = city_engine(city)
    with engine.connect() as conn:
        qvec_row = conn.execute(
            text(
                "SELECT vec::text FROM engine.embeddings WHERE entity_type=:et AND entity_id=:eid AND model=:m"
            ),
            {"et": entity_type, "eid": entity_id, "m": prov_name},
        ).first()
        if qvec_row is None:
            raise click.ClickException(f"no embedding for {entity_type}:{entity_id} under model={prov_name}")
        qvec = [float(x) for x in qvec_row[0].strip("[]").split(",")]

        latencies = []
        neighbors = None
        for _ in range(runs):
            t0 = time.perf_counter()
            neighbors = knn(conn, entity_type=entity_type, model=prov_name, query_vec=qvec, k=k, exclude_entity_id=entity_id)
            latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    click.echo(
        f"[now-embeddings] kNN latency over {runs} run(s): "
        f"min={latencies[0]:.2f}ms median={latencies[len(latencies)//2]:.2f}ms max={latencies[-1]:.2f}ms"
    )
    for n in neighbors or []:
        click.echo(f"  {n.entity_id}\tcos_sim={n.cosine_similarity:.4f}")


@cli.command("sanity-check")
@click.option("--city", required=True)
@click.option("--provider", type=click.Choice(["local", "offline"]), default="local", show_default=True)
@click.option("--k", default=5, show_default=True)
@click.option("--article-id", "article_ids", multiple=True, help="Repeatable. Default: 5 evenly spread real articles.")
@_model_option
def sanity_check(city: str, provider: str, k: int, article_ids: tuple[str, ...], model: str | None) -> None:
    """Human-readable nearest-neighbour report: title in, titles out. This
    is the honesty check the task requires -- cosine numbers alone prove
    nothing; read the titles."""
    prov_name = _model_name_for(provider, model)
    engine = city_engine(city)
    with engine.connect() as conn:
        if not article_ids:
            ids = [r[0] for r in conn.execute(text("SELECT id FROM public.articles ORDER BY id")).fetchall()]
            if not ids:
                raise click.ClickException("no articles in this city DB")
            step = max(len(ids) // 5, 1)
            article_ids = tuple(str(ids[i]) for i in range(0, len(ids), step)[:5])

        for aid in article_ids:
            title_row = conn.execute(text("SELECT title FROM public.articles WHERE id=:id"), {"id": int(aid)}).first()
            if title_row is None:
                click.echo(f"article {aid}: not found")
                continue
            qvec_row = conn.execute(
                text("SELECT vec::text FROM engine.embeddings WHERE entity_type='article' AND entity_id=:eid AND model=:m"),
                {"eid": aid, "m": prov_name},
            ).first()
            if qvec_row is None:
                click.echo(f"article {aid} ({title_row[0]!r}): NOT EMBEDDED under model={prov_name}")
                continue
            qvec = [float(x) for x in qvec_row[0].strip("[]").split(",")]
            neighbors = knn(conn, entity_type="article", model=prov_name, query_vec=qvec, k=k, exclude_entity_id=aid)
            click.echo(f"\n=== article {aid}: {title_row[0]!r} ===")
            for n in neighbors:
                ntitle = conn.execute(text("SELECT title FROM public.articles WHERE id=:id"), {"id": int(n.entity_id)}).scalar()
                click.echo(f"  [{n.cosine_similarity:.4f}] {n.entity_id}\t{ntitle!r}")


@cli.command()
@click.option("--redis-url", default=None, help="Overrides REDIS_URL env var.")
@click.option("--provider", type=click.Choice(["local", "offline"]), default="local", show_default=True)
@click.option("--once", is_flag=True, help="Process whatever is currently pending, then exit (default: run forever).")
@click.option("--block-ms", default=5000, show_default=True)
def worker(redis_url: str | None, provider: str, once: bool, block_ms: int) -> None:
    """Consume `article.published` (+ republished, + the place equivalents)
    off `now:domain-events:stream` and re-embed the referenced entity."""
    from now_embeddings.worker import ReembedWorker

    prov = _provider(provider)
    w = ReembedWorker(prov, redis_url=redis_url)
    click.echo(f"[now-embeddings] worker started, provider={prov.name}, once={once}")
    if once:
        result = w.run_once(block_ms=block_ms)
        click.echo(
            f"[now-embeddings] processed={result.processed} reembedded={result.reembedded} "
            f"skipped_unchanged={result.skipped_unchanged} ignored={result.ignored} errors={result.errors}"
        )
        return
    w.run_forever()


if __name__ == "__main__":
    cli()
