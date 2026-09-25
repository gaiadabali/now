"""WS6: per-document and per-query embedding cost of each registered model,
on real article text (the exact strings `store.fetch_articles` builds).

    uv run python scripts/bench_embedding_models.py --db-ref <city db> \
        --model BAAI/bge-small-en-v1.5 --model BAAI/bge-m3 --docs 96

Reports model load time, batch throughput (docs/s at the backfill's
threads=16/batch 32) and single-query latency at search's threads=4 --
the two costs a switch changes: backfill/worker time, and the p95 of
every search request. Numbers are only comparable within one run on one
machine; the host's other load is not controlled for (say so when citing).
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

from now_embeddings.connections import city_engine
from now_embeddings.providers.local import LocalProvider
from now_embeddings.store import fetch_articles


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-ref", required=True)
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--docs", type=int, default=96)
    ap.add_argument("--queries", type=int, default=30)
    args = ap.parse_args()

    with city_engine(args.db_ref).connect() as conn:
        rows = fetch_articles(conn)
    step = max(len(rows) // args.docs, 1)
    texts = [r.text for r in rows[::step][: args.docs]]
    queries = ["rooftop bar", "best brunch in the city", "family friendly hotel with pool", "art exhibition this weekend",
               "restoran jepang", "spa and massage", "street food tour", "new restaurant opening"]

    out = {}
    for model in args.model:
        t0 = time.perf_counter()
        batch = LocalProvider(model, threads=16)
        load_s = time.perf_counter() - t0
        batch.embed_batch(texts[:8])  # warm
        t0 = time.perf_counter()
        batch.embed_batch(texts)
        dt = time.perf_counter() - t0
        del batch
        single = LocalProvider(model, threads=4)
        single.embed_queries(["warm up"])
        lat = []
        for i in range(args.queries):
            t1 = time.perf_counter()
            single.embed_queries([queries[i % len(queries)]])
            lat.append((time.perf_counter() - t1) * 1000)
        lat.sort()
        out[model] = {
            "load_s": round(load_s, 1),
            "docs": len(texts),
            "docs_per_s": round(len(texts) / dt, 2),
            "ms_per_doc": round(1000 * dt / len(texts), 1),
            "query_ms_p50": round(statistics.median(lat), 1),
            "query_ms_p95": round(lat[int(0.95 * (len(lat) - 1))], 1),
        }
        print(json.dumps({model: out[model]}), flush=True)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
