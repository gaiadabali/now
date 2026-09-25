"""WS5 tagging calibration: build a stratified sample of (article, facet,
term, band) candidates for Hansel's own hand-labelling (see
docs/EDITION-2-PLAN.md's WS5 section for exactly how this was used).

Not part of the installed package (`now-classifier`'s CLI) -- this is a
one-off tool that produces the *inputs* to calibration, run once per
facet before `calibration.py`'s measured tables are filled in. Re-running
it after calibration is safe (idempotent output) but pointless unless the
candidate-generation logic itself changes.

Usage: `uv run python scripts/build_calibration_sample.py <facet> --n 100 --out <path>.jsonl`
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from now_classifier.facet_tagging.candidates import ALL_BANDS, candidates_for_article
from now_classifier.facet_tagging.embed import load_term_vectors
from now_classifier.facet_tagging.lexicon import build_term_matcher
from now_classifier.facet_tagging.price_cues import score_price_band
from now_classifier.facet_tagging.scope import in_scope
from now_classifier.vocabulary import load_term_index
from now_db.settings import city_database_url
from now_taxonomy_evidence.sources import find_repo_root, load_articles, load_seed
from now_taxonomy_evidence.vectors import load_embeddings
from sqlalchemy import create_engine, text

CITIES = ("jakarta", "bali")
CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}
SEED = 20260924  # today's date, for a reproducible sample


def _primary_types(engine, id_by_wp: dict[int, int]) -> dict[int, str | None]:
    ids = list(id_by_wp.values())
    if not ids:
        return {}
    rows = engine.connect().execute(
        text("select id, primary_type::text from public.articles where id = any(:ids)"),
        {"ids": ids},
    ).fetchall()
    by_article_id = {r[0]: r[1] for r in rows}
    return {wp: by_article_id.get(aid) for wp, aid in id_by_wp.items()}


def _fetch_id_by_wp_id(engine) -> dict[int, int]:
    rows = engine.connect().execute(text("select id, legacy_wp_id from public.articles where legacy_wp_id is not null")).fetchall()
    return {int(r[1]): r[0] for r in rows}


def sample_lexical_facet(facet: str, n: int, out_path: Path) -> None:
    root = find_repo_root()
    seed = load_seed(root)
    matcher = build_term_matcher(seed["terms"][facet])
    terms = load_term_index()
    slug_to_id = {slug: uid for slug, (uid, _p) in terms.by_facet.get(facet, {}).items()}
    facet_term_ids = list(slug_to_id.values())

    pool: list[dict] = []
    for city in CITIES:
        articles = load_articles(city, root)
        eng = create_engine(city_database_url(CITY_DB[city]))
        id_by_wp = _fetch_id_by_wp_id(eng)
        ptypes = _primary_types(eng, id_by_wp)
        vec_space = load_embeddings(city)
        vec_by_wp = {}
        if vec_space is not None and vec_space.matrix.size:
            idx = vec_space.index()
            vec_by_wp = {wp: vec_space.matrix[i].tolist() for wp, i in idx.items()}
        term_vec_by_id = load_term_vectors(eng, facet_term_ids)

        for a in articles:
            if not in_scope(facet, ptypes.get(a.wp_id)):
                continue
            cands = candidates_for_article(
                facet, a.title, a.excerpt, a.text, matcher,
                vec_by_wp.get(a.wp_id), slug_to_id, term_vec_by_id, None,
            )
            for c in cands:
                pool.append({
                    "facet": facet, "city": city, "wp_id": a.wp_id, "slug": c.slug, "band": c.band,
                    "direct_sim": round(c.direct_sim, 3), "centroid_sim": round(c.centroid_sim, 3),
                    "title": a.title, "excerpt": a.excerpt[:220], "lead": a.text[:260],
                })
        eng.dispose()

    _write_stratified(pool, n, out_path)


def sample_price_band(n: int, out_path: Path) -> None:
    root = find_repo_root()
    pool: list[dict] = []
    for city in CITIES:
        articles = load_articles(city, root)
        eng = create_engine(city_database_url(CITY_DB[city]))
        id_by_wp = _fetch_id_by_wp_id(eng)
        ptypes = _primary_types(eng, id_by_wp)
        for a in articles:
            if not in_scope("price_band", ptypes.get(a.wp_id)):
                continue
            r = score_price_band(a.title, a.text)
            if r.value is None:
                continue
            band = "cue_confident" if r.confident else "cue_fired"
            pool.append({
                "facet": "price_band", "city": city, "wp_id": a.wp_id, "slug": r.value, "band": band,
                "margin": round(r.margin, 2), "scores": {k: round(v, 2) for k, v in r.scores.items()},
                "title": a.title, "excerpt": a.excerpt[:220], "lead": a.text[:260],
            })
        eng.dispose()
    _write_stratified(pool, n, out_path, band_key="band", bands=("cue_confident", "cue_fired"))


def _write_stratified(pool: list[dict], n: int, out_path: Path, band_key: str = "band", bands: tuple[str, ...] = ALL_BANDS) -> None:
    rng = random.Random(SEED)
    by_band: dict[str, list[dict]] = {b: [] for b in bands}
    for row in pool:
        by_band.setdefault(row[band_key], []).append(row)
    per_band = max(1, n // len(bands))
    sample: list[dict] = []
    for b in bands:
        items = by_band.get(b, [])
        rng.shuffle(items)
        sample.extend(items[:per_band])
    # top up from whichever band has spare capacity if we're short (some
    # bands, e.g. a facet with very few embed_only candidates, may not
    # have per_band available)
    if len(sample) < n:
        leftovers = [row for b in bands for row in by_band.get(b, [])[per_band:]]
        rng.shuffle(leftovers)
        sample.extend(leftovers[: n - len(sample)])
    rng.shuffle(sample)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for i, row in enumerate(sample):
            row["_id"] = i
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    counts = {b: len(by_band.get(b, [])) for b in bands}
    print(f"pool size per band: {counts}")
    print(f"wrote {len(sample)} candidates to {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("facet", choices=["topic", "audience", "vibe", "cuisine", "occasion", "price_band"])
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.facet == "price_band":
        sample_price_band(args.n, args.out)
    else:
        sample_lexical_facet(args.facet, args.n, args.out)


if __name__ == "__main__":
    main()
