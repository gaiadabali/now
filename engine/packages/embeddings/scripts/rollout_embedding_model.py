"""Roll a new embedding model out -- or check that one is ready -- without
touching the rows the live model serves from.

    # 1. backfill every registered site under the new model (idempotent,
    #    resumable: a re-run embeds only what is missing or changed)
    uv run python scripts/rollout_embedding_model.py backfill --model intfloat/multilingual-e5-small

    # 2. prove coverage before anyone flips the switch
    uv run python scripts/rollout_embedding_model.py check --model intfloat/multilingual-e5-small

    # 3. flip: set NOW_EMBEDDING_MODEL=<model> for web, engine-api, worker
    #    (and rebuild the classifier centroids -- see below). Roll back by
    #    unsetting it: the previous model's rows were never modified.

Why the order matters. Every reader filters `engine.embeddings` by model
(F42). Flip the switch before step 2 passes and every article without a
new-model row silently gets an empty Read Next rail and no semantic search
hits -- nothing errors, which is exactly why `check` exists and exits
non-zero on any gap.

What this does NOT do:

* Store a model wider than `engine.embeddings.vec` (384-d). `backfill`
  refuses; a 768-/1024-d model needs a migration first (README, "Changing
  model").
* Rebuild `engine/packages/classifier/data/embed_routing_centroids.json`.
  Those centroids were trained on the live model's vectors; after a switch
  run `engine/packages/eval/scripts/build_routing_centroids.py` with the
  same NOW_EMBEDDING_MODEL, and re-measure F120's routed accuracy
  (`f120_routing_report.py`) before trusting it -- the numbers in
  `now_classifier.embed_routing` were measured on bge-small.
* Delete anything. Retiring a model's rows is a deliberate, separate act:
  `DELETE FROM engine.embeddings WHERE model = '<old model>'` per city,
  only after the new model has been live long enough that rollback is off
  the table.
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import text

from now_db.sites_registry import list_sites
from now_embeddings.connections import city_engine, platform_engine
from now_embeddings.models import STORED_DIM, get_spec
from now_embeddings.pipeline import backfill_entity_type
from now_embeddings.store import fetch_articles, fetch_places, fetch_terms

_COVERAGE_SQL = text(
    """
    SELECT count(*) AS published,
           count(e.entity_id) AS embedded,
           count(*) FILTER (WHERE e.entity_id IS NOT NULL AND e.dim <> :dim) AS wrong_dim
      FROM public.articles a
      LEFT JOIN engine.embeddings e
        ON e.entity_type = 'article' AND e.entity_id = a.id::text AND e.model = :model
     WHERE a._status = 'published'
    """
)


def _city_sites():
    with platform_engine().connect() as conn:
        sites = [s for s in list_sites(conn) if s.db_ref]
    out = []
    for s in sites:
        try:
            with city_engine(s.db_ref).connect() as conn:
                conn.execute(text("SELECT 1 FROM public.articles LIMIT 1"))
        except Exception:  # noqa: BLE001 -- a tenant with no Payload schema has nothing to embed
            continue
        out.append(s)
    return out


def cmd_backfill(args) -> int:
    spec = get_spec(args.model)
    if not spec.storable:
        print(f"refusing: {spec.name} is {spec.dim}-d, engine.embeddings.vec is {STORED_DIM}-d (needs a migration first)")
        return 2
    from now_embeddings.providers.local import LocalProvider

    provider = LocalProvider(spec.name)
    with platform_engine().connect() as conn:
        terms = fetch_terms(conn)
    for site in _city_sites():
        engine = city_engine(site.db_ref)
        for entity_type, fetch in (("article", fetch_articles), ("place", fetch_places), ("term", None)):
            t0 = time.time()
            if fetch is None:
                rows = terms
            else:
                with engine.connect() as conn:
                    rows = fetch(conn)
            stats = backfill_entity_type(
                engine, entity_type=entity_type, rows=rows, provider=provider,
                batch_size=args.batch_size, prune_stale=entity_type != "term",
            )
            print(f"[{site.slug}] {entity_type}: total={stats.total} embedded={stats.embedded} "
                  f"skipped_unchanged={stats.skipped_unchanged} errors={len(stats.errors)} ({time.time() - t0:.0f}s)", flush=True)
    return 0


def cmd_check(args) -> int:
    spec = get_spec(args.model)
    ok = True
    for site in _city_sites():
        with city_engine(site.db_ref).connect() as conn:
            r = conn.execute(_COVERAGE_SQL, {"model": spec.name, "dim": spec.dim}).one()
            terms = conn.execute(
                text("SELECT count(*) FROM engine.embeddings WHERE entity_type='term' AND model=:m"), {"m": spec.name}
            ).scalar()
        gap = r.published - r.embedded
        status = "READY" if gap == 0 and r.wrong_dim == 0 and terms > 0 else "NOT READY"
        ok &= status == "READY"
        print(f"[{site.slug}] {spec.name}: {r.embedded}/{r.published} published articles embedded, "
              f"{terms} terms, wrong_dim={r.wrong_dim} -> {status}")
    print("ready to flip NOW_EMBEDDING_MODEL" if ok else "do not flip NOW_EMBEDDING_MODEL yet")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backfill")
    b.add_argument("--model", required=True)
    b.add_argument("--batch-size", type=int, default=32)
    c = sub.add_parser("check")
    c.add_argument("--model", required=True)
    args = ap.parse_args()
    sys.exit(cmd_backfill(args) if args.cmd == "backfill" else cmd_check(args))


if __name__ == "__main__":
    main()
