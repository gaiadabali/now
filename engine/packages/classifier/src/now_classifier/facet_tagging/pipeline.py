"""Ties the WS5 tagging signals together into one re-runnable pass per
city: load articles + vocabulary + vectors, score every in-scope
(article, facet, term) candidate, keep only the bands `calibration.py`
measured at or above the ship bar, and hand the result to `db.write_tags`.

Deliberately mirrors `now_classifier.cli`'s own shape (load once, loop
articles, connect once, write once) rather than introducing a second
pipeline style for the same repo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from now_db.settings import city_database_url
from now_taxonomy_evidence.sources import find_repo_root, load_articles, load_seed
from now_taxonomy_evidence.vectors import load_embeddings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..vocabulary import TermIndex, load_term_index
from .calibration import ALIAS_EXCLUSIONS, confidence_for, shipped_bands
from .candidates import candidates_for_article
from .db import TagWriteStats, write_tags
from .embed import load_term_vectors
from .lexicon import build_term_matcher
from .price_cues import score_price_band
from .scope import ALL_FACETS, in_scope

CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}

LEXICAL_FACETS = ("topic", "audience", "vibe", "cuisine", "occasion")
PRICE_BAND_CONFIDENCE = {"cue_confident": confidence_for("price_band", "cue_confident"),
                          "cue_fired": confidence_for("price_band", "cue_fired")}


@dataclass
class TaggingRun:
    city: str
    proposals: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)  # entity_id -> facet -> {term_id: conf}
    articles_seen: int = 0
    articles_missing_row: int = 0
    facet_term_ids: dict[str, list[str]] = field(default_factory=dict)


def _fetch_id_and_type_by_wp_id(engine: Engine) -> dict[int, tuple[int, str | None]]:
    rows = engine.connect().execute(
        text("select legacy_wp_id, id, primary_type::text from public.articles where legacy_wp_id is not null")
    ).fetchall()
    return {int(r[0]): (r[1], r[2]) for r in rows}


def build_run(city: str, root: Path | None = None, limit: int | None = None) -> tuple[TaggingRun, Engine]:
    root = root or find_repo_root()
    seed = load_seed(root)
    terms: TermIndex = load_term_index()

    facet_term_ids: dict[str, list[str]] = {}
    slug_to_id: dict[str, dict[str, str]] = {}
    for facet in ALL_FACETS:
        by_slug = terms.by_facet.get(facet, {})
        slug_to_id[facet] = {slug: uid for slug, (uid, _p) in by_slug.items()}
        facet_term_ids[facet] = list(slug_to_id[facet].values())

    matchers = {
        facet: build_term_matcher(seed["terms"][facet], facet_key=facet, alias_exclusions=ALIAS_EXCLUSIONS)
        for facet in LEXICAL_FACETS
    }

    articles = load_articles(city, root)
    if limit:
        articles = articles[:limit]

    engine = create_engine(city_database_url(CITY_DB[city]))
    id_and_type_by_wp = _fetch_id_and_type_by_wp_id(engine)

    vec_space = load_embeddings(city)
    vector_by_wp_id: dict[int, list[float]] = {}
    if vec_space is not None and vec_space.matrix.size:
        idx = vec_space.index()
        vector_by_wp_id = {wp: vec_space.matrix[i].tolist() for wp, i in idx.items()}

    all_term_ids = sorted({uid for facet in LEXICAL_FACETS for uid in facet_term_ids[facet]}
                           | set(facet_term_ids.get("price_band", [])))
    term_vec_by_id = load_term_vectors(engine, all_term_ids)

    run = TaggingRun(city=city, facet_term_ids=facet_term_ids)

    for a in articles:
        run.articles_seen += 1
        row = id_and_type_by_wp.get(a.wp_id)
        if row is None:
            run.articles_missing_row += 1
            continue
        article_id, ptype = row
        entity_id = str(article_id)
        article_vec = vector_by_wp_id.get(a.wp_id)
        by_facet: dict[str, dict[str, float]] = {}

        # A facet key is added to `by_facet` -- even with an EMPTY {term:
        # confidence} dict -- for every facet this article is in scope for
        # and that has at least one shipped band. `db.write_tags` always
        # runs its stale-retraction pass for every facet key present here,
        # regardless of whether this run proposes anything for it -- an
        # article that no longer matches (text edited, alias exclusion
        # added) must have its PREVIOUS run's row retracted, not just skip
        # silently because this run's proposal set happens to be empty.
        for facet in LEXICAL_FACETS:
            if not in_scope(facet, ptype):
                continue
            shipped = shipped_bands(facet)
            if not shipped:
                continue
            cands = candidates_for_article(
                facet, a.title, a.excerpt, a.text, matchers[facet],
                article_vec, slug_to_id[facet], term_vec_by_id, None,
            )
            by_facet[facet] = {
                slug_to_id[facet][c.slug]: confidence_for(facet, c.band)
                for c in cands if c.band in shipped
            }

        if in_scope("price_band", ptype) and shipped_bands("price_band"):
            r = score_price_band(a.title, a.text)
            proposed: dict[str, float] = {}
            if r.value:
                band = "cue_confident" if r.confident else "cue_fired"
                conf = PRICE_BAND_CONFIDENCE.get(band)
                uid = slug_to_id["price_band"].get(r.value)
                if conf is not None and uid:
                    proposed = {uid: conf}
            by_facet["price_band"] = proposed

        if by_facet:
            run.proposals[entity_id] = by_facet

    return run, engine


def run_tagging(city: str, dry_run: bool = False, limit: int | None = None, root: Path | None = None) -> TagWriteStats:
    run, engine = build_run(city, root=root, limit=limit)
    try:
        return write_tags(engine, run.proposals, run.facet_term_ids, dry_run=dry_run)
    finally:
        engine.dispose()


def run_llm_refine(
    city: str, dry_run: bool = False, limit: int | None = None, root: Path | None = None,
) -> tuple["TagWriteStats | None", int]:
    """The optional LLM pass (deliverable #4): reviews ONLY the `lead`
    band -- the borderline band every one of the five alias-based facets
    measured just under the 0.80 ship bar (0.44-0.72; see
    `calibration.py`'s `MEASURED_PRECISION` table and
    docs/EDITION-2-PLAN.md) -- and writes `source='ai'` for whichever
    candidates the model judges `applies: true`. `price_band` has no
    borderline band (both its bands already ship), so it is not touched
    here. Returns `(None, 0)` immediately, doing no DB work at all, if no
    LLM key is configured -- the expected result today.
    """
    from .candidates import BAND_LEAD
    from .llm_refine import judge_one, load_llm_config, LLM_CONFIDENCE

    cfg = load_llm_config()
    if cfg is None:
        return None, 0

    root = root or find_repo_root()
    seed = load_seed(root)
    terms: TermIndex = load_term_index()
    label_by_slug = {
        facet: {t["slug"]: t.get("label", t["slug"]) for t in seed["terms"][facet]}
        for facet in LEXICAL_FACETS
    }

    facet_term_ids: dict[str, list[str]] = {}
    slug_to_id: dict[str, dict[str, str]] = {}
    for facet in LEXICAL_FACETS:
        by_slug = terms.by_facet.get(facet, {})
        slug_to_id[facet] = {slug: uid for slug, (uid, _p) in by_slug.items()}
        facet_term_ids[facet] = list(slug_to_id[facet].values())

    matchers = {
        facet: build_term_matcher(seed["terms"][facet], facet_key=facet, alias_exclusions=ALIAS_EXCLUSIONS)
        for facet in LEXICAL_FACETS
    }

    articles = load_articles(city, root)
    if limit:
        articles = articles[:limit]

    engine = create_engine(city_database_url(CITY_DB[city]))
    id_and_type_by_wp = _fetch_id_and_type_by_wp_id(engine)

    proposals: dict[str, dict[str, dict[str, float]]] = {}
    judged = 0
    for a in articles:
        row = id_and_type_by_wp.get(a.wp_id)
        if row is None:
            continue
        article_id, ptype = row
        entity_id = str(article_id)
        by_facet: dict[str, dict[str, float]] = {}
        for facet in LEXICAL_FACETS:
            if not in_scope(facet, ptype):
                continue
            cands = candidates_for_article(
                facet, a.title, a.excerpt, a.text, matchers[facet], None, slug_to_id[facet], {}, None,
            )
            proposed: dict[str, float] = {}
            for c in cands:
                if c.band != BAND_LEAD:
                    continue
                judged += 1
                verdict = judge_one(cfg, facet, label_by_slug[facet][c.slug], a.title, a.excerpt or a.text[:400])
                if verdict:
                    proposed[slug_to_id[facet][c.slug]] = LLM_CONFIDENCE
            by_facet[facet] = proposed
        if by_facet:
            proposals[entity_id] = by_facet

    try:
        stats = write_tags(engine, proposals, facet_term_ids, dry_run=dry_run, source="ai")
    finally:
        engine.dispose()
    return stats, judged
