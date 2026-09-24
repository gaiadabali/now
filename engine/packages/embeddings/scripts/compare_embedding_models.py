"""WS6: measure candidate embedding models against the live one, on real
ground truth, without touching the vectors production reads.

Subcommands (run from engine/packages/embeddings; NOW_PG_* as for backfill):

    embed          embed every published article + every term of every
                   registered site under --model, into a local cache
                   (npz per site/entity). `--from-db` instead reads the
                   vectors already in engine.embeddings for that model --
                   used for the live model, so the baseline is exactly what
                   production serves, not a re-embedding of it.
    eval-search    hybrid search (production lexical leg + this model's
                   semantic leg, fused by production RRF) on Yoast focus
                   keywords, the hand-translated Indonesian query set, and
                   the harness's provisional set.
    eval-related   related-article proxies: same featured venue, series
                   siblings, editor primary category (now_eval's labelled
                   set), classifier-centroid CV accuracy and term zero-shot
                   accuracy on the 253 human-adjudicated labels.
    label-pool     writes the blind pool for the human sanity check.
    score-labels   scores each model against the hand-labelled pool.
    latency        Read Next SQL latency + on-disk size per model, in
                   session-local TEMP tables (the shared table is never
                   altered; see "Why TEMP tables" below).

**Why a local cache and not engine.embeddings.** `vec` is `vector(384)`;
768-d and 1024-d candidates cannot be stored there without a migration.
And a 384-d candidate written to the shared table shares one HNSW graph
with the live model's rows, so its approximate (non-exact) kNN path is
filtered by model after the graph walk -- F67's failure mode. `latency
--coexistence` measures that directly: at 800 + 800 rows per site, k=10,
the default ef_search, 0 of 200 live-model probes came back short in
either city, so this is a scale-dependent risk, not a present one. The
candidates still live in files until a decision is made (the shared DB is
other workstreams' too), and the rollout (scripts/
rollout_embedding_model.py) is where rows enter the shared table.

**The semantic leg here is exact cosine in numpy.** Production search
uses exact cosine too (`now_search.engine` passes `exact=True`, via a
MATERIALIZED CTE), so ranking is identical, not approximated;
`eval-search --check-production N` re-runs N queries through the real
`SearchEngine` for the live model and asserts the same top-10.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sqlalchemy import text

from now_db.sites_registry import list_sites
from now_embeddings.connections import city_engine, platform_engine
from now_embeddings.models import get_spec
from now_embeddings.store import fetch_articles, fetch_terms


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------


def _slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", model).strip("_")


def model_of(label: str) -> str:
    """Cache labels are `<model>` or `<model>@<tag>` (e.g. the live model
    re-embedded on current text, `...@fresh`, next to `--from-db`'s copy of
    what production actually stores). The provider only needs the model."""
    return label.split("@", 1)[0]


def _cache_path(cache: Path, model: str, site: str, entity: str) -> Path:
    return cache / _slug(model) / f"{site}_{entity}.npz"


def save_vectors(path: Path, ids: list[str], vecs: np.ndarray, hashes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, ids=np.array(ids), vecs=vecs.astype(np.float32), hashes=np.array(hashes))


def load_vectors(cache: Path, model: str, site: str, entity: str = "article") -> tuple[list[str], np.ndarray]:
    data = np.load(_cache_path(cache, model, site, entity))
    vecs = data["vecs"]
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return [str(x) for x in data["ids"]], vecs / np.where(norms == 0, 1, norms)


def _sites():
    with platform_engine().connect() as conn:
        return [s for s in list_sites(conn) if s.db_ref]


def _site_has_articles(site) -> bool:
    try:
        with city_engine(site.db_ref).connect() as conn:
            return bool(conn.execute(text("SELECT count(*) FROM public.articles WHERE _status='published'")).scalar())
    except Exception:  # noqa: BLE001 -- the synthetic tenant has no Payload schema
        return False


def _parse_vec(raw: str) -> list[float]:
    return [float(x) for x in raw.strip("[]").split(",")]


def _rows_for(site, entity: str, args, terms_cache: dict) -> list:
    """Embeddable rows (id, exact text, text_hash) for one site/entity:
    from `--texts-file` if given (so a long run does not depend on the
    shared DB staying up -- during WS6 it went into crash recovery twice),
    else live from the DB via the same `store.fetch_*` the backfill uses."""
    from now_embeddings.store import EmbeddableRow

    if args.texts_file:
        doc = json.loads(Path(args.texts_file).read_text(encoding="utf-8"))
        key = "term" if entity == "term" else site.slug
        return [EmbeddableRow(entity, r["id"], r["text"], r["hash"]) for r in doc.get(key, [])]
    if entity == "article":
        with city_engine(site.db_ref).connect() as conn:
            rows = fetch_articles(conn)
    else:
        if "term" not in terms_cache:
            with platform_engine().connect() as conn:
                terms_cache["term"] = fetch_terms(conn)
        rows = terms_cache["term"]
    if args.limit:
        rows = rows[: args.limit]
    if args.slice_file and entity == "article":
        keep = set(json.loads(Path(args.slice_file).read_text(encoding="utf-8")).get(site.slug, []))
        rows = [r for r in rows if r.entity_id in keep]
    return rows


def cmd_dump_texts(args) -> None:
    """Freeze the exact embedding inputs for the slice (and all terms) to one
    file: every model then embeds byte-identical text, and the embed runs
    need no DB."""
    args.texts_file = None
    out: dict = {}
    terms_cache: dict = {}
    for site in _sites():
        if not _site_has_articles(site):
            continue
        out[site.slug] = [{"id": r.entity_id, "text": r.text, "hash": r.text_hash} for r in _rows_for(site, "article", args, terms_cache)]
    out["term"] = [{"id": r.entity_id, "text": r.text, "hash": r.text_hash} for r in _rows_for(None, "term", args, terms_cache)]
    out["_sites"] = [k for k in out if k not in ("term",)]
    args.out.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print({k: len(v) for k, v in out.items() if k != "_sites"})


class _SiteRef:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.db_ref = None


def cmd_embed(args) -> None:
    spec = get_spec(model_of(args.model))
    label = args.model
    report = {"model": label, "dim": spec.dim, "sites": {}}
    provider = None
    if not args.from_db:
        from now_embeddings.providers.local import LocalProvider

        t0 = time.perf_counter()
        provider = LocalProvider(spec.name, threads=args.threads)
        report["model_load_s"] = round(time.perf_counter() - t0, 1)
    if args.texts_file and not args.from_db:
        sites = [_SiteRef(s) for s in json.loads(Path(args.texts_file).read_text(encoding="utf-8"))["_sites"]]
    else:
        sites = [s for s in _sites() if _site_has_articles(s)]
    terms_cache: dict = {}
    for site in sites:
        site_report = {}
        for entity in args.entity:
            rows = _rows_for(site, entity, args, terms_cache)
            t0 = time.perf_counter()
            if args.from_db:
                with city_engine(site.db_ref).connect() as conn:
                    got = dict(
                        conn.execute(
                            text("SELECT entity_id, vec::text FROM engine.embeddings WHERE entity_type=:et AND model=:m"),
                            {"et": entity, "m": spec.name},
                        ).fetchall()
                    )
                rows = [r for r in rows if r.entity_id in got]
                vecs = np.array([_parse_vec(got[r.entity_id]) for r in rows], dtype=np.float32)
            else:
                out: list[list[float]] = []
                for i in range(0, len(rows), args.batch_size):
                    out.extend(provider.embed_batch([r.text for r in rows[i : i + args.batch_size]]))
                    if (i // args.batch_size) % 5 == 0:
                        print(f"[{label}] {site.slug} {entity}: {len(out)}/{len(rows)} ({time.perf_counter() - t0:.0f}s)", flush=True)
                vecs = np.array(out, dtype=np.float32)
            dt = time.perf_counter() - t0
            save_vectors(_cache_path(args.cache, label, site.slug, entity), [r.entity_id for r in rows], vecs, [r.text_hash for r in rows])
            site_report[entity] = {"n": len(rows), "wall_s": round(dt, 1), "per_item_ms": round(1000 * dt / max(len(rows), 1), 1)}
            print(f"[{label}] {site.slug} {entity}: n={len(rows)} wall={dt:.1f}s", flush=True)
        report["sites"][site.slug] = site_report
    out_path = args.cache / _slug(label) / ("timing_from_db.json" if args.from_db else "timing.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def cmd_make_slice(args) -> None:
    """A fixed, deterministic article subset per site, for models too slow
    to embed the whole archive on this machine. Every model -- the live one
    included -- is then evaluated on the SAME subset, so the comparison
    stays like-for-like; absolute numbers are higher than full-corpus ones
    (a smaller haystack), relative ones are what matter.

    Composition, in order: every article a cross-lingual query or a
    human-adjudicated classifier label points at (so those sets are fully
    evaluable), whole same-featured-venue groups up to --venue-articles
    (a group cut in half would be a different test), then a uniform hash
    sample to --per-site."""
    cl = [json.loads(l) for l in open(args.crosslingual, encoding="utf-8") if l.strip()] if args.crosslingual else []
    calib = []
    if args.calibration_dir:
        calib = [json.loads(l) for l in open(Path(args.calibration_dir) / "sample.jsonl", encoding="utf-8") if l.strip()]
    out, report = {}, {}
    for site in _sites():
        if not _site_has_articles(site):
            continue
        with city_engine(site.db_ref).connect() as conn:
            wp_to_db, _ = _wp_maps(conn)
            groups = _groups(conn)["same_featured_venue"]
            all_ids = [str(r[0]) for r in conn.execute(text("SELECT id FROM public.articles WHERE _status='published'"))]
        chosen: list[str] = []
        seen: set[str] = set()

        def add(ids):
            for i in ids:
                if i not in seen and len(chosen) < args.per_site:
                    seen.add(i)
                    chosen.append(i)

        add(wp_to_db[w] for q in cl if q["site"] == site.slug for w in q["relevant_wp_ids"] if w in wp_to_db)
        add(str(it["article_id"]) for it in calib if it["city"] == site.slug)
        forced = len(chosen)
        venue_n = 0
        for g in sorted(groups, key=lambda g: hashlib.sha256(f"ws6-slice-venue:{site.slug}:{min(g)}".encode()).hexdigest()):
            if venue_n + len(g) > args.venue_articles:
                continue
            before = len(chosen)
            add(g)
            venue_n += len(chosen) - before
        add(sorted(all_ids, key=lambda e: hashlib.sha256(f"ws6-slice:{site.slug}:{e}".encode()).hexdigest()))
        out[site.slug] = chosen
        report[site.slug] = {"articles": len(chosen), "forced_by_query_and_label_sets": forced, "venue_group_articles": venue_n}
    args.out.write_text(json.dumps(out), encoding="utf-8")
    print(json.dumps(report, indent=1))


# --------------------------------------------------------------------------
# shared eval plumbing
# --------------------------------------------------------------------------


def topk(matrix: np.ndarray, q: np.ndarray, k: int, exclude: int | None = None) -> list[int]:
    sims = matrix @ q
    if exclude is not None:
        sims[exclude] = -np.inf
    k = min(k, len(sims))
    idx = np.argpartition(-sims, k - 1)[:k]
    return list(idx[np.argsort(-sims[idx], kind="stable")])


def _wp_maps(conn) -> tuple[dict[int, str], dict[str, int]]:
    rows = conn.execute(
        text("SELECT id, legacy_wp_id FROM public.articles WHERE legacy_wp_id IS NOT NULL AND _status='published'")
    ).fetchall()
    wp_to_db = {int(wp): str(i) for i, wp in rows}
    return wp_to_db, {v: k for k, v in wp_to_db.items()}


def _focus_keyword_queries(articles_jsonl: Path, wp_to_db: dict[int, str]) -> list[dict]:
    """One query per distinct (lower-cased) focus keyword; relevant = every
    published article whose own focus keyword is that string (grade 3)."""
    by_kw: dict[str, set[str]] = defaultdict(set)
    shown: dict[str, str] = {}
    with open(articles_jsonl, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            raw = json.loads(line)
            kw = (raw.get("meta") or {}).get("_yoast_wpseo_focuskw")
            if not (isinstance(kw, str) and kw.strip()):
                continue
            db_id = wp_to_db.get(int(raw["wp_id"]))
            if db_id is None:
                continue
            key = kw.strip().lower()
            by_kw[key].add(db_id)
            shown.setdefault(key, kw.strip())
    return [{"query": shown[k], "relevant": {i: 3.0 for i in ids}} for k, ids in sorted(by_kw.items())]


def _metrics(ranked: list[str], relevant: dict[str, float], k: int = 10) -> dict[str, float]:
    from now_eval.metrics.ndcg import ndcg_at_k

    top = ranked[:k]
    hits = [i for i, d in enumerate(top) if relevant.get(d, 0) > 0]
    n_rel = sum(1 for v in relevant.values() if v > 0)
    return {
        "ndcg@10": ndcg_at_k(top, relevant, k),
        "recall@10": (len(hits) / min(n_rel, k)) if n_rel else 0.0,
        "hit@10": 1.0 if hits else 0.0,
        "mrr@10": (1.0 / (hits[0] + 1)) if hits else 0.0,
    }


def _mean(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    return {k: round(statistics.fmean(r[k] for r in rows), 4) for k in rows[0]}


def _paired_bootstrap(a: list[float], b: list[float], n: int = 2000, seed: int = 7) -> dict[str, float]:
    """Paired bootstrap on per-query metric differences (b - a): mean diff
    and a 95% interval -- 'wins clearly' means the interval excludes 0."""
    rng = np.random.default_rng(seed)
    d = np.array(b) - np.array(a)
    if len(d) == 0:
        return {"diff": 0.0, "lo": 0.0, "hi": 0.0}
    means = [float(d[rng.integers(0, len(d), len(d))].mean()) for _ in range(n)]
    return {"diff": round(float(d.mean()), 4), "lo": round(float(np.percentile(means, 2.5)), 4), "hi": round(float(np.percentile(means, 97.5)), 4)}


# --------------------------------------------------------------------------
# eval-search
# --------------------------------------------------------------------------


def cmd_eval_search(args) -> None:
    from now_embeddings.providers.local import LocalProvider
    from now_search import lexical
    from now_search.rrf import DEFAULT_K, reciprocal_rank_fusion, to_ranked_hits

    jsonl_by_site = dict(s.split("=", 1) for s in args.focus_keywords)
    crossling = [json.loads(l) for l in open(args.crosslingual, encoding="utf-8") if l.strip()] if args.crosslingual else []

    results: dict = {"models": args.model, "sites": {}}
    per_query: dict = defaultdict(lambda: defaultdict(dict))  # set -> model -> {qid: metrics}
    providers = {m: LocalProvider(model_of(m), threads=args.threads) for m in args.model}

    for site in _sites():
        if site.slug not in jsonl_by_site:
            continue
        engine = city_engine(site.db_ref)
        with engine.connect() as conn:
            wp_to_db, _ = _wp_maps(conn)
            query_sets: dict[str, list[dict]] = {"focus_keyword": _focus_keyword_queries(Path(jsonl_by_site[site.slug]), wp_to_db)}
            cl = [q for q in crossling if q["site"] == site.slug]
            if cl:
                for lang in ("en", "id"):
                    query_sets[f"crosslingual_{lang}"] = [
                        {"query": q[f"query_{lang}"], "relevant": {wp_to_db[w]: 3.0 for w in q["relevant_wp_ids"] if w in wp_to_db}}
                        for q in cl
                    ]
            if args.provisional and site.slug == args.provisional_site:
                from now_eval.datasets.search_queries import build_provisional_query_set

                query_sets["provisional_harness"] = [
                    {"query": q.query, "relevant": {wp_to_db[int(a[3:])]: g for a, g in q.relevant if int(a[3:]) in wp_to_db}}
                    for q in build_provisional_query_set(Path(jsonl_by_site[site.slug]), Path(args.provisional))
                ]
            # The haystack is the set of articles EVERY compared model has a
            # vector for (the whole archive for a --from-db cache, the frozen
            # slice otherwise). Both legs search exactly that set -- lexical
            # through its own restricted (candidate_ids) path -- and
            # relevance judgments outside it are dropped, so no model is
            # scored against documents it was never given.
            loaded = {m: load_vectors(args.cache, m, site.slug) for m in args.model}
            universe = set.intersection(*(set(v[0]) for v in loaded.values()))
            full_corpus = len(universe) >= len(wp_to_db) * 0.95
            for name in list(query_sets):
                kept = []
                for q in query_sets[name]:
                    rel = {d: g for d, g in q["relevant"].items() if d in universe}
                    if rel:
                        kept.append({"query": q["query"], "relevant": rel})
                query_sets[name] = kept
            cand = None if full_corpus else sorted(int(i) for i in universe)
            lex_cache: dict[str, list] = {}
            for qs in query_sets.values():
                for q in qs:
                    if q["query"] not in lex_cache:
                        lex_cache[q["query"]] = lexical.search_lexical(conn, q["query"], limit=100, candidate_ids=cand)

        site_out = {"haystack_articles": len(universe)}
        for model in args.model:
            ids, mat = loaded[model]
            keep = [i for i, e in enumerate(ids) if e in universe]
            ids, mat = [ids[i] for i in keep], mat[keep]
            prov = providers[model]
            model_out = {}
            for set_name, qs in query_sets.items():
                qvecs = np.array(prov.embed_queries([q["query"] for q in qs]), dtype=np.float32)
                hybrid_rows, sem_rows = [], []
                for qi, (q, qv) in enumerate(zip(qs, qvecs)):
                    idx = topk(mat, qv / np.linalg.norm(qv), 100)
                    sims = mat[idx] @ qv
                    semantic = to_ranked_hits([(ids[i], float(s)) for i, s in zip(idx, sims)])
                    fused = reciprocal_rank_fusion(lex_cache[q["query"]], semantic, k=DEFAULT_K)
                    h = _metrics([f.entity_id for f in fused], q["relevant"])
                    s = _metrics([r.entity_id for r in semantic], q["relevant"])
                    hybrid_rows.append(h)
                    sem_rows.append(s)
                    per_query[f"{site.slug}:{set_name}"][model][qi] = {"hybrid": h, "semantic": s}
                model_out[set_name] = {"n": len(qs), "hybrid": _mean(hybrid_rows), "semantic_only": _mean(sem_rows)}
            site_out[model] = model_out
            print(json.dumps({site.slug: {model: model_out}}, indent=1), flush=True)

        if args.check_production and args.model[0] == args.live_model:
            site_out["production_check"] = _check_production(engine, args, query_sets["focus_keyword"][: args.check_production], lex_cache)
        results["sites"][site.slug] = site_out

    # paired significance vs the first model, per set, per leg, nDCG@10
    base = args.model[0]
    sig = {}
    for set_key, by_model in per_query.items():
        for model in args.model[1:]:
            for leg in ("hybrid", "semantic"):
                qids = sorted(by_model[base])
                a = [by_model[base][q][leg]["ndcg@10"] for q in qids]
                b = [by_model[model][q][leg]["ndcg@10"] for q in qids]
                sig[f"{set_key}|{model}|{leg}"] = _paired_bootstrap(a, b)
    results["paired_vs_" + base] = sig
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(sig, indent=1))


def _check_production(engine, args, queries, lex_cache) -> dict:
    """Same top-10 as the real `SearchEngine` for the live model? If not,
    the offline pipeline is not measuring production and every number above
    is suspect."""
    from now_search.engine import SearchEngine
    from now_search.rrf import DEFAULT_K, reciprocal_rank_fusion, to_ranked_hits
    from now_embeddings.providers.local import LocalProvider

    prov = LocalProvider(model_of(args.live_model), threads=args.threads)
    site_slug = next(s.slug for s in _sites() if s.db_ref == engine.url.database)
    ids, mat = load_vectors(args.cache, args.live_model, site_slug)
    same = 0
    with engine.connect() as conn:
        se = SearchEngine(conn)
        for q in queries:
            prod = [h.entity_id for h in se.search(q["query"], k=10, compute_facets=False).hits]
            qv = np.array(prov.embed_queries([q["query"]])[0], dtype=np.float32)
            idx = topk(mat, qv / np.linalg.norm(qv), 100)
            semantic = to_ranked_hits([(ids[i], float(mat[i] @ qv)) for i in idx])
            ours = [f.entity_id for f in reciprocal_rank_fusion(lex_cache[q["query"]], semantic, k=DEFAULT_K)][:10]
            same += prod == ours
    return {"queries": len(queries), "identical_top10": same}


# --------------------------------------------------------------------------
# eval-related
# --------------------------------------------------------------------------


def _groups(conn) -> dict[str, list[list[str]]]:
    venue = conn.execute(
        text(
            """
            SELECT pm.place_id, array_agg(DISTINCT pm.article_id::text)
              FROM public.place_mentions pm
              JOIN public.articles a ON a.id = pm.article_id AND a._status = 'published'
             WHERE pm.role = 'featured'
             GROUP BY pm.place_id
            HAVING count(DISTINCT pm.article_id) >= 2
            """
        )
    ).fetchall()
    series = conn.execute(
        text(
            """
            SELECT series_key, array_agg(id::text) FROM public.articles
             WHERE _status = 'published' AND series_key IS NOT NULL
             GROUP BY series_key HAVING count(*) >= 2
            """
        )
    ).fetchall()
    return {"same_featured_venue": [list(r[1]) for r in venue], "series_siblings": [list(r[1]) for r in series]}


def _group_eval(ids: list[str], mat: np.ndarray, groups: list[list[str]], k: int = 10) -> tuple[dict, list[dict]]:
    pos = {e: i for i, e in enumerate(ids)}
    rows = []
    for members in groups:
        members = [m for m in members if m in pos]
        for seed in members:
            rel = {m: 1.0 for m in members if m != seed}
            if not rel:
                continue
            nn = topk(mat, mat[pos[seed]], k, exclude=pos[seed])
            rows.append(_metrics([ids[i] for i in nn], rel, k))
    return {"n_seeds": len(rows), **_mean(rows)}, rows


def cmd_eval_related(args) -> None:
    from now_eval.metrics.precision import precision_at_k

    results: dict = {"sites": {}}
    per_seed: dict = defaultdict(dict)
    for site in _sites():
        if not _site_has_articles(site):
            continue
        with city_engine(site.db_ref).connect() as conn:
            groups = _groups(conn)
            wp_to_db, _ = _wp_maps(conn)
        site_out = {}
        for model in args.model:
            ids, mat = load_vectors(args.cache, model, site.slug)
            m_out = {}
            for gname, g in groups.items():
                m_out[gname], rows = _group_eval(ids, mat, g)
                per_seed[f"{site.slug}:{gname}"][model] = [r["ndcg@10"] for r in rows]
            if args.related_labels and site.slug == args.related_labels_site:
                pos = {e: i for i, e in enumerate(ids)}
                precs = []
                for line in open(args.related_labels, encoding="utf-8"):
                    if not line.strip():
                        continue
                    q = json.loads(line)
                    seed = wp_to_db.get(int(q["seed_article_id"][3:]))
                    if seed not in pos:
                        continue
                    rel = {wp_to_db[int(a[3:])] for a in q["relevant_article_ids"] if int(a[3:]) in wp_to_db}
                    nn = [ids[i] for i in topk(mat, mat[pos[seed]], 6, exclude=pos[seed])]
                    precs.append(precision_at_k(nn, rel, 6))
                m_out["primary_category_precision@6"] = {"n_seeds": len(precs), "value": round(statistics.fmean(precs), 4)}
                per_seed[f"{site.slug}:primary_category"][model] = precs
            site_out[model] = m_out
        results["sites"][site.slug] = site_out
        print(json.dumps({site.slug: site_out}, indent=1), flush=True)

    if args.calibration_dir:
        results["classifier_labels"] = _classifier_eval(args)
    base = args.model[0]
    results["paired_vs_" + base] = {
        f"{key}|{m}": _paired_bootstrap(by_model[base], by_model[m])
        for key, by_model in per_seed.items()
        for m in args.model[1:]
    }
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if k != "sites"}, indent=1))


def _classifier_eval(args) -> dict:
    """The classifier routes two confidence bands to an embeddings-centroid
    instrument (F120, `now_classifier.embed_routing`). Re-measure that
    instrument per model on the same 253 human-adjudicated labels with the
    same 5-fold split, plus term zero-shot (article vector -> nearest
    `type`/`format` term vector) since personalization seeds taste vectors
    from term embeddings in the same space."""
    import sys

    sys.path.insert(0, str(Path(args.calibration_dir).resolve().parents[1] / "src"))
    from now_eval.calibration import embed_data as ed
    from now_eval.calibration import embed_instrument as ei

    items = ed.load_labelled_items(Path(args.calibration_dir))
    slug_map = ed.load_term_slug_map()  # term uuid -> (facet, slug)
    sites = {s.slug for s in _sites()}
    out = {}
    for model in args.model:
        vec_by_key = {}
        for site in {it["city"] for it in items} & sites:
            ids, mat = load_vectors(args.cache, model, site)
            pos = {e: i for i, e in enumerate(ids)}
            for it in items:
                if it["city"] == site and str(it["article_id"]) in pos:
                    vec_by_key[it["key"]] = mat[pos[str(it["article_id"])]].tolist()
        any_site = next(iter({it["city"] for it in items} & sites))
        tids, tmat = load_vectors(args.cache, model, any_site, "term")
        term_vecs: dict[str, dict[str, list[float]]] = defaultdict(dict)
        for tid, v in zip(tids, tmat):
            if tid in slug_map:
                facet, slug = slug_map[tid]
                term_vecs[facet][slug] = v.tolist()
        m_out = {}
        for facet in ("type", "format"):
            tuples = [(it["key"], it["true_value"], vec_by_key[it["key"]]) for it in items if it["facet"] == facet and it["key"] in vec_by_key]
            perm = sorted(range(len(tuples)), key=lambda i: hashlib.sha256(f"f118-embed-centroid-cv-v1:{tuples[i][0]}".encode()).hexdigest())
            _, _, cv_acc = ei.overall_accuracy(ei.cv_centroid_predictions(tuples, k_folds=5, seed_perm=perm))
            zs = [ei.zero_shot_predict(v, term_vecs[facet])[0] == true for _, true, v in tuples]
            m_out[facet] = {"n": len(tuples), "centroid_cv_accuracy": round(cv_acc, 4), "term_zero_shot_accuracy": round(sum(zs) / len(zs), 4)}
        out[model] = m_out
    return out


# --------------------------------------------------------------------------
# hand-labelled sanity check
# --------------------------------------------------------------------------


def cmd_label_pool(args) -> None:
    """Blind pool: for `--seeds-per-site` deterministic seeds per site, the
    union of every model's top-`--depth` neighbours, shuffled, with no model
    attribution in the file the labeller reads. Model provenance goes to a
    separate key file."""
    from now_content_clean.metrics import visible_text_out

    pool, key = [], []
    for site in _sites():
        if not _site_has_articles(site):
            continue
        mats = {m: load_vectors(args.cache, m, site.slug) for m in args.model}
        ids0 = mats[args.model[0]][0]
        common = set(ids0).intersection(*[set(v[0]) for v in mats.values()])
        seeds = sorted(common, key=lambda e: hashlib.sha256(f"ws6-label-v1:{site.slug}:{e}".encode()).hexdigest())[: args.seeds_per_site]
        with city_engine(site.db_ref).connect() as conn:
            def info(eid: str) -> dict:
                r = conn.execute(text("SELECT title, dek, primary_type::text, body_blocks FROM public.articles WHERE id=:i"), {"i": int(eid)}).first()
                body = visible_text_out(r[3] or [])[:240]
                return {"id": eid, "title": r[0], "dek": (r[1] or "")[:200], "type": r[2], "lead": body}

            for seed in seeds:
                cands: dict[str, list[str]] = defaultdict(list)
                for m, (ids, mat) in mats.items():
                    pos = {e: i for i, e in enumerate(ids)}
                    for i in topk(mat, mat[pos[seed]], args.depth, exclude=pos[seed]):
                        cands[ids[i]].append(m)
                order = sorted(cands, key=lambda e: hashlib.sha256(f"shuffle:{seed}:{e}".encode()).hexdigest())
                s_info = info(seed)
                for c in order:
                    pid = hashlib.sha256(f"{site.slug}:{seed}:{c}".encode()).hexdigest()[:10]
                    pool.append({"pair_id": pid, "site": site.slug, "seed": s_info, "candidate": info(c), "label": None})
                    key.append({"pair_id": pid, "site": site.slug, "seed": seed, "candidate": c,
                                "ranks": {m: None for m in args.model}, "proposed_by": cands[c]})
    args.out.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in pool) + "\n", encoding="utf-8")
    args.key.write_text("\n".join(json.dumps(k) for k in key) + "\n", encoding="utf-8")
    print(f"pool: {len(pool)} pairs -> {args.out}; key -> {args.key}")


def cmd_score_labels(args) -> None:
    labels = {}
    for line in open(args.labels, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            labels[r["pair_id"]] = r["label"]
    by_model: dict[str, list[float]] = defaultdict(list)
    by_model_site: dict[str, list[float]] = defaultdict(list)
    for line in open(args.key, encoding="utf-8"):
        if not line.strip():
            continue
        k = json.loads(line)
        lab = labels.get(k["pair_id"])
        if lab is None:
            continue
        for m in k["proposed_by"]:
            by_model[m].append(lab)
            by_model_site[f"{k['site']}|{m}"].append(lab)
    out = {
        "labelled_pairs": sum(1 for v in labels.values() if v is not None),
        "per_model": {m: {"n": len(v), "mean_grade": round(statistics.fmean(v), 3), "share_grade>=1": round(sum(1 for x in v if x >= 1) / len(v), 3), "share_grade2": round(sum(1 for x in v if x == 2) / len(v), 3)} for m, v in by_model.items()},
        "per_site_model": {m: {"n": len(v), "mean_grade": round(statistics.fmean(v), 3)} for m, v in sorted(by_model_site.items())},
    }
    print(json.dumps(out, indent=1))
    if args.out:
        args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# latency / size (TEMP tables only)
# --------------------------------------------------------------------------


def _read_next_sql(table: str) -> str:
    """`apps/web/src/lib/recommendSql.ts`'s READ_NEXT_SQL verbatim, with
    `engine.embeddings` swapped for `table` -- the query shape (MATERIALIZED
    eligibility CTE, PK join, exact `<=>` sort) is what is being timed."""
    return f"""
  WITH subj AS (
    SELECT vec FROM {table}
     WHERE entity_type = 'article' AND entity_id = %(aid)s::text AND model = %(model)s
  ),
  eligible AS MATERIALIZED (
    SELECT a.id, a.primary_type::text AS primary_type, a.series_key
      FROM public.articles a
     WHERE a.id != %(aid)s::int
       AND a._status = 'published'
       AND a.published_at IS NOT NULL AND a.published_at <= now()
       AND (
         cardinality(%(excl)s::text[]) = 0
         OR (a.primary_type IS NOT NULL AND a.primary_type::text != ALL(%(excl)s::text[]))
       )
       AND (
         cardinality(%(excl)s::text[]) = 0
         OR NOT EXISTS (
           SELECT 1 FROM engine.hidden_rival_flags hrf
            WHERE hrf.article_id = a.id::text AND hrf.matched_type = ANY(%(excl)s::text[])
         )
       )
       AND a.id NOT IN (
         SELECT entity_id::int FROM engine.quality_scores
          WHERE entity_type = 'article' AND score < %(floor)s
       )
  )
  SELECT e.entity_id::int AS id, el.primary_type, el.series_key
    FROM eligible el
    JOIN {table} e ON e.entity_type = 'article' AND e.entity_id = el.id::text AND e.model = %(model)s
   CROSS JOIN subj
   ORDER BY e.vec <=> subj.vec ASC
   LIMIT %(limit)s
"""


def _vec_lit(v) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"


def cmd_latency(args) -> None:
    import psycopg

    from now_db.settings import city_database_url

    results: dict = {"sites": {}}
    for site in _sites():
        if not _site_has_articles(site):
            continue
        dsn = city_database_url(site.db_ref).replace("postgresql+psycopg://", "postgresql://")
        site_out = {}
        with psycopg.connect(dsn, autocommit=True) as conn:
            # Serial HNSW builds only. A parallel build of a 1024-d TEMP-table
            # index took the whole shared dev server into crash recovery
            # during WS6 (backend exit code 2, every connection dropped) --
            # parallel maintenance workers allocate the graph in dynamic
            # shared memory, which a default Docker /dev/shm does not have
            # room for. A serial build is slower and cannot do that.
            conn.execute("SET max_parallel_maintenance_workers = 0")
            conn.execute("SET maintenance_work_mem = '64MB'")
            aids = [
                str(r[0])
                for r in conn.execute("SELECT id FROM public.articles WHERE _status='published' ORDER BY md5(id::text) LIMIT %s", (args.subjects,)).fetchall()
            ]
            all_ids = [str(r[0]) for r in conn.execute("SELECT id FROM public.articles WHERE _status='published'").fetchall()]
            for model in args.model:
                if model.startswith("synthetic:"):
                    # Cost by WIDTH, at the real row count: the Read Next
                    # sort is exact, so its latency and the table/index size
                    # depend on dimension and rows, not on what the vectors
                    # mean -- this is how a model that was only embedded on
                    # the eval slice gets a full-archive cost figure.
                    d = int(model.split(":", 1)[1])
                    rng = np.random.default_rng(d)
                    mat = rng.normal(size=(len(all_ids), d)).astype(np.float32)
                    mat /= np.linalg.norm(mat, axis=1, keepdims=True)
                    ids = all_ids
                else:
                    ids, mat = load_vectors(args.cache, model, site.slug)
                dim = mat.shape[1]
                tbl = f"ws6_emb_{_slug(model).lower()[:40]}"
                conn.execute(f"DROP TABLE IF EXISTS pg_temp.{tbl}")
                conn.execute(
                    f"CREATE TEMP TABLE {tbl} (entity_type text NOT NULL, entity_id text NOT NULL, model text NOT NULL, "
                    f"dim int NOT NULL, vec vector({dim}) NOT NULL, text_hash text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(), "
                    f"PRIMARY KEY (entity_type, entity_id, model))"
                )
                # Same per-column storage as the real table (`vec` EXTERNAL),
                # so TOAST behaviour for wide vectors is measured, not assumed.
                conn.execute(f"ALTER TABLE {tbl} ALTER COLUMN vec SET STORAGE EXTERNAL")
                with conn.cursor().copy(f"COPY {tbl} (entity_type, entity_id, model, dim, vec, text_hash) FROM STDIN") as cp:
                    for eid, v in zip(ids, mat):
                        cp.write_row(("article", eid, model, dim, _vec_lit(v), "x"))
                t0 = time.perf_counter()
                conn.execute(f"CREATE INDEX ON {tbl} USING hnsw (vec vector_cosine_ops)")
                index_build_s = time.perf_counter() - t0
                conn.execute(f"ANALYZE {tbl}")
                heap = conn.execute(f"SELECT pg_table_size('pg_temp.{tbl}'), pg_indexes_size('pg_temp.{tbl}'), pg_total_relation_size('pg_temp.{tbl}')").fetchone()
                sql = _read_next_sql(tbl)
                for aid in aids[:5]:  # warm cache
                    conn.execute(sql, {"aid": aid, "model": model, "excl": [], "floor": 0.35, "limit": 24})
                lat = []
                for aid in aids:
                    t0 = time.perf_counter()
                    conn.execute(sql, {"aid": aid, "model": model, "excl": ["stay"], "floor": 0.35, "limit": 24}).fetchall()
                    lat.append((time.perf_counter() - t0) * 1000)
                lat.sort()
                site_out[model] = {
                    "dim": dim,
                    "rows": len(ids),
                    "table_bytes": heap[0], "index_bytes": heap[1], "total_bytes": heap[2],
                    "per_row_bytes": round(heap[2] / max(len(ids), 1)),
                    "hnsw_build_s": round(index_build_s, 2),
                    "read_next_ms": {"p50": round(lat[len(lat) // 2], 2), "p95": round(lat[int(0.95 * (len(lat) - 1))], 2), "n": len(lat)},
                }
                print(json.dumps({site.slug: {model: site_out[model]}}), flush=True)
                conn.execute(f"DROP TABLE pg_temp.{tbl}")
            if args.coexistence:
                site_out["coexistence"] = _coexistence(conn, args, site.slug)
        results["sites"][site.slug] = site_out
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")


def _coexistence(conn, args, site_slug: str) -> dict:
    """What happens to the LIVE model's approximate kNN (the non-exact
    `search_semantic` path, `store.knn`, the Inspector) when a second 384-d
    model's rows share its HNSW graph -- i.e. what writing candidate rows
    into the shared table would do to other readers. Rebuilt in a TEMP
    table: live rows alone, then live + candidate rows."""
    live, cand = args.coexistence
    lids, lmat = load_vectors(args.cache, live, site_slug)
    cids, cmat = load_vectors(args.cache, cand, site_slug)
    out = {}
    conn.execute("DROP TABLE IF EXISTS pg_temp.ws6_coexist")
    conn.execute("CREATE TEMP TABLE ws6_coexist (entity_type text, entity_id text, model text, vec vector(384))")
    probes = list(range(0, len(lids), max(len(lids) // args.subjects, 1)))[: args.subjects]
    for label, rows in (("live_only", [(live, lids, lmat)]), ("live_plus_candidate", [(live, lids, lmat), (cand, cids, cmat)])):
        conn.execute("TRUNCATE ws6_coexist")
        conn.execute("DROP INDEX IF EXISTS pg_temp.ws6_coexist_hnsw")
        with conn.cursor().copy("COPY ws6_coexist FROM STDIN") as cp:
            for model, ids, mat in rows:
                for eid, v in zip(ids, mat):
                    cp.write_row(("article", eid, model, _vec_lit(v)))
        conn.execute("CREATE INDEX ws6_coexist_hnsw ON ws6_coexist USING hnsw (vec vector_cosine_ops)")
        conn.execute("ANALYZE ws6_coexist")
        short, got_total = 0, 0
        for p in probes:
            got = conn.execute(
                "SELECT entity_id FROM ws6_coexist WHERE entity_type='article' AND model=%s ORDER BY vec <=> %s::vector LIMIT 10",
                (live, _vec_lit(lmat[p])),
            ).fetchall()
            got_total += len(got)
            short += len(got) < 10
        out[label] = {"probes": len(probes), "queries_returning_<10": short, "mean_rows_returned": round(got_total / len(probes), 2)}
    conn.execute("DROP TABLE pg_temp.ws6_coexist")
    print(json.dumps({site_slug: {"coexistence": out}}), flush=True)
    return out


# --------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("embed")
    e.add_argument("--model", required=True)
    e.add_argument("--cache", type=Path, required=True)
    e.add_argument("--entity", action="append", choices=["article", "term"], default=None)
    e.add_argument("--from-db", action="store_true")
    e.add_argument("--limit", type=int, default=0)
    e.add_argument("--slice-file", default=None, help="JSON {site_slug: [article ids]} from make-slice")
    e.add_argument("--texts-file", default=None, help="frozen inputs from dump-texts (no DB needed)")

    dt = sub.add_parser("dump-texts")
    dt.add_argument("--slice-file", required=True)
    dt.add_argument("--limit", type=int, default=0)
    dt.add_argument("--out", type=Path, required=True)

    ms = sub.add_parser("make-slice")
    ms.add_argument("--per-site", type=int, required=True)
    ms.add_argument("--venue-articles", type=int, default=300, help="whole same-venue groups, up to this many articles")
    ms.add_argument("--crosslingual", type=Path, default=None)
    ms.add_argument("--calibration-dir", default=None)
    ms.add_argument("--out", type=Path, required=True)
    e.add_argument("--batch-size", type=int, default=32)
    e.add_argument("--threads", type=int, default=16)

    s = sub.add_parser("eval-search")
    s.add_argument("--model", action="append", required=True, help="repeatable; the first is the baseline")
    s.add_argument("--live-model", default=None)
    s.add_argument("--cache", type=Path, required=True)
    s.add_argument("--focus-keywords", action="append", required=True, help="site_slug=path/to/articles.jsonl")
    s.add_argument("--crosslingual", type=Path, default=None)
    s.add_argument("--provisional", default=None, help="taxonomy-mapping.json path; runs now_eval's provisional set")
    s.add_argument("--provisional-site", default=None)
    s.add_argument("--check-production", type=int, default=0)
    s.add_argument("--threads", type=int, default=8)
    s.add_argument("--out", type=Path, required=True)

    r = sub.add_parser("eval-related")
    r.add_argument("--model", action="append", required=True)
    r.add_argument("--cache", type=Path, required=True)
    r.add_argument("--related-labels", default=None)
    r.add_argument("--related-labels-site", default=None)
    r.add_argument("--calibration-dir", default=None)
    r.add_argument("--out", type=Path, required=True)

    lp = sub.add_parser("label-pool")
    lp.add_argument("--model", action="append", required=True)
    lp.add_argument("--cache", type=Path, required=True)
    lp.add_argument("--seeds-per-site", type=int, default=20)
    lp.add_argument("--depth", type=int, default=2)
    lp.add_argument("--out", type=Path, required=True)
    lp.add_argument("--key", type=Path, required=True)

    sl = sub.add_parser("score-labels")
    sl.add_argument("--labels", type=Path, required=True)
    sl.add_argument("--key", type=Path, required=True)
    sl.add_argument("--out", type=Path, default=None)

    la = sub.add_parser("latency")
    la.add_argument("--model", action="append", required=True)
    la.add_argument("--cache", type=Path, required=True)
    la.add_argument("--subjects", type=int, default=200)
    la.add_argument("--coexistence", nargs=2, metavar=("LIVE", "CANDIDATE"), default=None)
    la.add_argument("--out", type=Path, required=True)

    args = ap.parse_args()
    if args.cmd == "dump-texts":
        cmd_dump_texts(args)
    elif args.cmd == "make-slice":
        cmd_make_slice(args)
    elif args.cmd == "embed":
        args.entity = args.entity or ["article", "term"]
        cmd_embed(args)
    elif args.cmd == "eval-search":
        args.live_model = args.live_model or args.model[0]
        cmd_eval_search(args)
    elif args.cmd == "eval-related":
        cmd_eval_related(args)
    elif args.cmd == "label-pool":
        cmd_label_pool(args)
    elif args.cmd == "score-labels":
        cmd_score_labels(args)
    else:
        cmd_latency(args)


if __name__ == "__main__":
    main()
