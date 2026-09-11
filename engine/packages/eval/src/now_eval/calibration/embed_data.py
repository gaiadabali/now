"""DB-touching data loading for the F118(a) embeddings instrument
(`embed_instrument.py`). Kept separate from that module the same way
`db_frame.py` is kept separate from `analyze.py`/`stats.py` -- so the
scoring logic stays importable and unit-testable with zero DB dependency.

Read-only everywhere: `engine.embeddings` (already backfilled by E2.4/
E2.4b -- this module never calls an embedding provider or writes a row),
`engine.terms` (platform vocabulary), and `public.articles` (for the
bulk/contaminated-centroid corpus, `primary_type`/`format` columns
E2.1 already wrote).
"""
from __future__ import annotations

import json
from pathlib import Path

MODEL = "BAAI/bge-small-en-v1.5"
CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}


def _parse_vec(raw: str) -> list[float]:
    return json.loads(raw)


def load_labelled_items(calibration_dir: Path) -> list[dict]:
    """Returns one dict per adjudicated type/format item (253 total):
    city, wp_id, article_id, facet, true_value, classifier_value,
    original_confidence, kind. `true_value` is derived exactly as
    `analyze.build_cell_estimates` derives classifier-correctness --
    see this package's module docstring for the full argument."""
    from .adjudication import merge

    sample_rows = [json.loads(l) for l in open(calibration_dir / "sample.jsonl", encoding="utf-8") if l.strip()]
    llm_labels = [json.loads(l) for l in open(calibration_dir / "llm_labels.jsonl", encoding="utf-8") if l.strip()]
    merged = merge(sample_rows, llm_labels)
    verdicts = json.loads((calibration_dir / "calibration_verdicts.json").read_text(encoding="utf-8"))

    out = []
    n_neither = 0
    for row in merged:
        kind = "disagreement" if not row["agree"] else "control"
        item_id = row["key"] + f":{kind}"
        verdict = verdicts.get(item_id)
        if verdict is None:
            continue
        if verdict == "classifier":
            true_value = row["proposed_value"]
        elif verdict == "llm":
            true_value = row["llm_value"]
        else:
            n_neither += 1
            continue
        out.append({
            "key": row["key"],
            "city": row["city"],
            "wp_id": row["wp_id"],
            "article_id": row["article_id"],
            "facet": row["facet"],
            "true_value": true_value,
            "classifier_value": row["proposed_value"],
            "original_confidence": row["confidence"],
            "kind": kind,
        })
    if n_neither:
        # Disclosed, not silently dropped -- see module docstring; as of
        # this writing there are zero of these (verified: 211 "llm" + 42
        # "classifier", 0 "neither"/"both_wrong" in calibration_verdicts.json).
        print(f"WARNING: {n_neither} adjudicated items ruled 'neither' -- excluded, true label unknown")
    return out


def fetch_article_vectors(items: list[dict]) -> dict[tuple[str, int], list[float]]:
    """(city, article_id) -> 384-dim vector, read from each city's
    `engine.embeddings` (entity_type='article', model=bge-small)."""
    from sqlalchemy import create_engine, text

    from now_db.settings import city_database_url

    by_city: dict[str, set[int]] = {}
    for it in items:
        by_city.setdefault(it["city"], set()).add(it["article_id"])

    out: dict[tuple[str, int], list[float]] = {}
    for city, article_ids in by_city.items():
        eng = create_engine(city_database_url(CITY_DB[city]))
        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT entity_id, vec FROM engine.embeddings "
                    "WHERE entity_type = 'article' AND model = :model "
                    "AND entity_id = ANY(:ids)"
                ),
                {"model": MODEL, "ids": [str(a) for a in article_ids]},
            ).fetchall()
            for entity_id, vec in rows:
                out[(city, int(entity_id))] = _parse_vec(vec)
    return out


def load_term_slug_map() -> dict[str, tuple[str, str]]:
    """platform term_id -> (facet_key, slug)."""
    from sqlalchemy import create_engine, text

    from now_platform_db.settings import platform_database_url

    eng = create_engine(platform_database_url())
    with eng.connect() as conn:
        rows = conn.execute(
            text("SELECT t.id::text, f.key, t.slug FROM engine.terms t JOIN engine.facets f ON f.id = t.facet_id")
        ).fetchall()
    return {tid: (fkey, slug) for tid, fkey, slug in rows}


def fetch_stored_term_vectors(facet: str) -> dict[str, list[float]]:
    """slug -> vector for `facet` in {'type','format'}, reading the term
    vectors E2.4 already wrote (bare `"{facet}: {label} ({slug})"` text --
    see `now_embeddings.textbuild.build_term_text`). Read from Jakarta's
    city DB only: term embeddings are per-city rows but the *input text* is
    identical across cities and the model is deterministic, so both cities'
    vectors for the same term_id are bit-identical -- reading one city is
    not an approximation."""
    from sqlalchemy import create_engine, text

    from now_db.settings import city_database_url

    term_map = load_term_slug_map()
    term_ids_for_facet = [tid for tid, (fkey, slug) in term_map.items() if fkey == facet]

    eng = create_engine(city_database_url(CITY_DB["jakarta"]))
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT entity_id, vec FROM engine.embeddings "
                "WHERE entity_type = 'term' AND model = :model AND entity_id = ANY(:ids)"
            ),
            {"model": MODEL, "ids": term_ids_for_facet},
        ).fetchall()

    out = {}
    for entity_id, vec in rows:
        fkey, slug = term_map[entity_id]
        out[slug] = _parse_vec(vec)
    return out


def fetch_bulk_corpus(facet: str, exclude_wp_ids_by_city: dict[str, set[int]]) -> list[tuple[str, list[float]]]:
    """(auto-applied proposed_value, article vector) pairs across the FULL
    corpus (both cities), excluding the labelled-set articles, for the
    contaminated-centroid variant (F118 approach 3's circularity warning).
    `proposed_value` here is the classifier's own primary_type/format
    column -- exactly the 0.66/0.45-accurate labels the brief warns not to
    treat as clean ground truth. Only rows with a non-null value (i.e.
    already classified, accepted OR review -- we want every already-written
    proposal, not just the auto-applied slice, to get a large enough
    per-class pool) are included."""
    from sqlalchemy import create_engine, text

    from now_db.settings import city_database_url

    column = "primary_type" if facet == "type" else "format"
    out: list[tuple[str, list[float]]] = []
    for city, db_ref in CITY_DB.items():
        exclude = exclude_wp_ids_by_city.get(city, set())
        eng = create_engine(city_database_url(db_ref))
        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT a.id, a.{column}::text
                      FROM public.articles a
                     WHERE a._status = 'published' AND a.{column} IS NOT NULL
                    """
                )
            ).fetchall()
            article_ids = [str(r[0]) for r in rows if int(r[0]) not in exclude]
            value_by_id = {str(r[0]): r[1] for r in rows}
            if not article_ids:
                continue
            vec_rows = conn.execute(
                text(
                    "SELECT entity_id, vec FROM engine.embeddings "
                    "WHERE entity_type = 'article' AND model = :model AND entity_id = ANY(:ids)"
                ),
                {"model": MODEL, "ids": article_ids},
            ).fetchall()
            for entity_id, vec in vec_rows:
                val = value_by_id.get(entity_id)
                if val:
                    out.append((val, _parse_vec(vec)))
    return out


def load_rich_term_vectors(path: Path) -> dict[str, dict[str, list[float]]]:
    """facet -> slug -> vector, precomputed offline by
    `scripts/embed_rich_terms.py` (run once, in the `now-embeddings`
    package's venv, the only one with `fastembed` installed) from the
    hand-authored descriptions in that script. See its module docstring
    for the exact text and why it is not reused from `engine.terms.attrs`
    (empty for every type/format row -- verified live)."""
    return json.loads(path.read_text(encoding="utf-8"))
