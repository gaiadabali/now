"""`now-taxonomy-evidence build` -- produce the evidence pack for both cities.

No env vars are needed: the city DB is reached through `now_db.settings`
(which reads the project `.env`, F31) and the LLM key through the env file
named in llm.py. Nothing is ever written to a database.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click

from . import llm as llm_mod
from .decide import LLM_TITLES, CityBuild, _spread, assemble
from .features import compute_features
from .render import render_json, render_markdown
from .sources import CITIES, find_repo_root, load_articles, load_categories, load_e14_mapping, load_seed, load_tags
from .vectors import vectors_for
from .vocabulary import analyse_vocabulary
from .vocabulary_delta import build_delta, render_delta_markdown

PACKAGE_ROOT = Path(__file__).resolve().parents[2]  # engine/packages/taxonomy-evidence


def _log(msg: str) -> None:
    click.echo(f"[{time.strftime('%H:%M:%S')}] {msg}", err=True)


@click.group()
def cli() -> None:
    """Taxonomy evidence pack (blocker #3 / F50)."""


@cli.command()
@click.option("--city", "cities", multiple=True, type=click.Choice(CITIES), help="default: both")
@click.option("--no-llm", is_flag=True, help="skip the LLM second opinion (heuristic path only)")
@click.option("--no-db", is_flag=True, help="do not read engine.embeddings; use the TF-IDF proxy for every city")
@click.option("--no-cache", is_flag=True, help="recompute per-article features (ignores .cache)")
@click.option("--out-dir", type=click.Path(path_type=Path), default=None, help="override output root (default: <repo>/<city>/site/)")
@click.option("--delta-dir", type=click.Path(path_type=Path), default=None, help="where vocabulary-delta.{json,md} go (default: the package root)")
def build(cities: tuple[str, ...], no_llm: bool, no_db: bool, no_cache: bool, out_dir: Path | None, delta_dir: Path | None) -> None:
    root = find_repo_root()
    cities = tuple(cities) or CITIES
    if len(cities) < 2:
        _log("note: cross-city checks need both cities; running one city only")
    seed = load_seed(root)
    e14 = load_e14_mapping(root)
    builds: dict[str, CityBuild] = {}
    articles_by_city = {}
    tags_by_city = {}
    for city in cities:
        t0 = time.time()
        arts = load_articles(city, root)
        cats = load_categories(city, arts, root)
        _log(f"{city}: {len(arts)} articles, {len(cats)} categories loaded ({time.time() - t0:.1f}s)")
        feats = compute_features(city, arts, seed, use_cache=not no_cache)
        _log(f"{city}: features ready ({time.time() - t0:.1f}s)")
        space = vectors_for(city, arts, use_db=not no_db)
        _log(f"{city}: vectors = {space.source} ({space.matrix.shape if space.matrix.size else 'none'})")
        b = CityBuild(city, arts, cats, feats, space, seed, e14 if city == "jakarta" else None)
        b.build_records()
        b.run_coherence()
        _log(f"{city}: coherence done ({time.time() - t0:.1f}s)")
        builds[city] = b
        articles_by_city[city] = arts
        tags_by_city[city] = load_tags(city, root)

    t0 = time.time()
    vocab = analyse_vocabulary(articles_by_city, seed, tags_by_city)
    # keep every candidate row available to the decision evidence (report shows only the frequent ones)
    from .lexicons import CANDIDATES  # noqa: F401  (documentation: the candidate lists live there)
    _log(f"vocabulary scan done ({time.time() - t0:.1f}s): {len(vocab['seed_unused'])} unused seed terms, {len(vocab['candidates'])} frequent candidates")

    # ---- LLM second opinion ------------------------------------------------
    llm_meta = {"used": False, "path": "heuristic-only (LLM disabled with --no-llm)", "model": None, "calls": 0}
    if not no_llm:
        cfg = llm_mod.load_config()
        if cfg is None:
            llm_meta["path"] = "heuristic-only (provider unavailable: no OLLAMA_CLOUD_API_KEY in the env file or environment)"
        else:
            probe = llm_mod._chat(cfg, [{"role": "user", "content": "Reply with the JSON {\"ok\": true}."}], max_tokens=200, timeout=60)
            if probe is None:
                llm_meta["path"] = f"heuristic-only (provider unreachable or not answering: {cfg.safe_repr})"
            else:
                jobs = {}
                for city, b in builds.items():
                    for name, rec in b.records.items():
                        if rec["published"] < 3:
                            continue
                        titles = [a.title for a in _spread(b.members[name], LLM_TITLES)]
                        jobs[f"{city}|{name}"] = llm_mod.category_prompt(city, name, rec["description"], rec["published"], f"{rec['first_year']}-{rec['last_year']}", titles, rec["proposal"], rec["parent"])
                _log(f"LLM: {len(jobs)} category prompts via {cfg.safe_repr}")
                t0 = time.time()
                results = llm_mod.second_opinions(cfg, jobs, workers=4)
                ok = 0
                for key, res in results.items():
                    city, name = key.split("|", 1)
                    if res and res.get("result"):
                        builds[city].records[name]["llm"] = {"model": res.get("model"), "result": res["result"]}
                        ok += 1
                llm_meta = {"used": True, "path": f"llm second opinion: {cfg.model} via {cfg.base_url} ({ok}/{len(jobs)} categories answered; responses cached in .cache/llm)", "model": cfg.model, "calls": len(jobs)}
                _log(f"LLM: {ok}/{len(jobs)} answered ({time.time() - t0:.1f}s)")

    # Evidence phase ends here: statuses + flags are computed against the E2.0
    # proposal. Then Hansel's answers (resolutions.py) are applied on top.
    for b in builds.values():
        b.assign_status()
        pre = sum(1 for r in b.records.values() if r["status"] in ("decision-needed", "flagged-by-evidence"))
        b.apply_resolutions()
        post = sum(1 for r in b.records.values() if r["status"] in ("decision-needed", "flagged-by-evidence"))
        changed = sum(1 for r in b.records.values() if (r.get("resolution") or {}).get("changed"))
        _log(f"{b.city}: resolutions applied -- {pre} categories were awaiting a decision, {post} still are; {changed} proposals changed vs E2.0")

    delta = build_delta(vocab, seed)
    _log(f"vocabulary delta: {delta['counts']['add_term']} terms to add, {delta['counts']['add_alias_sets']} alias sets, {delta['counts']['drop_term']} drop, {delta['counts']['trim_alias']} trims, {delta['counts']['approve']} approvals")

    sources_meta = {
        "articles": {c: f"{c}/content/extracted/articles.jsonl ({len(a)} published posts)" for c, a in articles_by_city.items()},
        "categories": "content/harvested/categories.jsonl (REST harvest: ids, parents, descriptions) with published counts recomputed from articles",
        "e14_prior": "jakarta/site/taxonomy-mapping.json (E1.4 draft, carried and amended)",
        "seed": seed["seed_dir"],
        "embeddings": {c: b.space.source for c, b in builds.items()},
        "resolutions": "src/now_taxonomy_evidence/resolutions.py (Hansel's 27 answers, 2026-09-10)",
    }
    models = assemble(builds, vocab, llm_meta, sources_meta, delta)
    for city, model in models.items():
        out = (out_dir / city / "site") if out_dir else (root / city / "site")
        out.mkdir(parents=True, exist_ok=True)
        (out / "taxonomy-review.md").write_text(render_markdown(model), encoding="utf-8")
        (out / "taxonomy-review.json").write_text(render_json(model), encoding="utf-8")
        t = model["totals"]
        _log(f"{city}: wrote {out / 'taxonomy-review.md'} and .json -- {t['decisions_for_city']} decisions ({t['decisions_resolved']} resolved), "
             f"{t['decision_needed_categories']} decision-needed, {t['resolved_categories']} resolved ({t['changed_categories']} changed vs E2.0), {t['empty_categories']} empty")
    delta["generated"] = next(iter(models.values()))["generated"]
    ddir = delta_dir or PACKAGE_ROOT
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / "vocabulary-delta.json").write_text(json.dumps(delta, ensure_ascii=False, indent=1), encoding="utf-8")
    (ddir / "vocabulary-delta.md").write_text(render_delta_markdown(delta), encoding="utf-8")
    _log(f"wrote {ddir / 'vocabulary-delta.json'} and .md")
    _log(f"LLM path: {llm_meta['path']}")


if __name__ == "__main__":
    sys.exit(cli())
