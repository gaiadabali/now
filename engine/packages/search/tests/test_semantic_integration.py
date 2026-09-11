"""Real-Postgres tests for the pgvector kNN side. Deliberately does NOT
load the fastembed model (that's `query_embedder`'s job, exercised in
test_engine_integration.py) -- these tests fetch an existing vector
straight out of `engine.embeddings` as the "query vector", which is
enough to prove the kNN SQL, the `entity_id::int` join, and -- most
importantly -- the model filter, all against real data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from now_search import semantic

REAL_MODEL = "BAAI/bge-small-en-v1.5"


def _any_embedded_article(conn) -> tuple[int, list[float]]:
    row = conn.execute(
        text(
            "SELECT entity_id::int, vec::text FROM engine.embeddings "
            "WHERE entity_type = 'article' AND model = :model LIMIT 1"
        ),
        {"model": REAL_MODEL},
    ).first()
    assert row is not None, "expected at least one article embedding under BAAI/bge-small-en-v1.5"
    article_id, vec_text = row
    vec = [float(x) for x in vec_text.strip("[]").split(",")]
    return article_id, vec


def test_knn_returns_the_source_article_as_top_hit(conn):
    article_id, vec = _any_embedded_article(conn)
    hits = semantic.search_semantic(conn, vec, model=REAL_MODEL, limit=5)
    assert hits[0].entity_id == str(article_id)
    assert hits[0].raw_score == pytest.approx(1.0, abs=1e-4)


def test_ranked_best_first_by_cosine_similarity(conn):
    _, vec = _any_embedded_article(conn)
    hits = semantic.search_semantic(conn, vec, model=REAL_MODEL, limit=10)
    sims = [h.raw_score for h in hits]
    assert sims == sorted(sims, reverse=True)


def test_model_filter_excludes_other_models(conn):
    """The single most important behavioural guarantee this module
    makes (task brief): a query without `WHERE model = :model` returns
    cross-model garbage the moment a second model exists. Proven here by
    querying with a model name guaranteed not to exist -- zero rows,
    not an error, not a fallback to "any model"."""
    _, vec = _any_embedded_article(conn)
    hits = semantic.search_semantic(conn, vec, model="not-a-real-model-xyz", limit=5)
    assert hits == []


def test_candidate_id_restriction(conn):
    article_id, vec = _any_embedded_article(conn)
    hits = semantic.search_semantic(conn, vec, model=REAL_MODEL, limit=10, candidate_ids=[article_id])
    assert len(hits) == 1
    assert hits[0].entity_id == str(article_id)


def test_candidate_id_restriction_empty_returns_empty_not_error(conn):
    """An empty `candidate_ids` list is a legitimately empty restriction
    (e.g. an upstream hard filter found nothing eligible) -- distinct from
    F67, which is an approximation artefact on a *non-empty* restriction.
    Zero rows here is correct, not a bug."""
    _, vec = _any_embedded_article(conn)
    hits = semantic.search_semantic(conn, vec, model=REAL_MODEL, limit=10, candidate_ids=[])
    assert hits == []


def test_f67_small_restriction_far_from_query_does_not_silently_return_zero(conn):
    """F67 repro, root-caused with `EXPLAIN (ANALYZE, BUFFERS)`:
    `_KNN_SQL_RESTRICTED`'s old shape (`WHERE entity_id::int = ANY(ids)
    ORDER BY vec <=> :qvec LIMIT :limit`) planned as an `Index Scan using
    ix_embeddings_hnsw ... Filter: (... = ANY(...))` -- HNSW is
    *approximate*: at this DB's default `hnsw.ef_search = 40`
    (`hnsw.iterative_scan` off), the scan visits ~40 graph nodes nearest
    the query vector and filters *after*, so a restriction with no
    overlap among those ~40 nodes came back **empty** even though every
    id in the restriction genuinely exists in the table.

    This test builds exactly that adversarial case against real data: the
    40 ids *farthest* (least similar, by real cosine distance -- computed
    here with the ANN index explicitly disabled so this ground-truth
    query cannot itself be approximate) from a real subject vector. Under
    the old query shape this returned 0 rows for a restriction that is
    ~0.8% of the table and 100% present. The fixed query
    (`WITH candidates AS MATERIALIZED (...)`, see semantic.py's module
    docstring) must return real, correctly-ranked hits instead."""
    subject_id, vec = _any_embedded_article(conn)
    qvec_literal = semantic._vec_literal(vec)

    conn.execute(text("SET LOCAL enable_indexscan = off"))
    conn.execute(text("SET LOCAL enable_indexonlyscan = off"))
    farthest_ids = [
        r[0]
        for r in conn.execute(
            text(
                "SELECT entity_id::int FROM engine.embeddings "
                "WHERE entity_type = 'article' AND model = :model AND entity_id::int <> :sid "
                "ORDER BY vec <=> CAST(:qvec AS vector) DESC LIMIT 40"
            ),
            {"model": REAL_MODEL, "sid": subject_id, "qvec": qvec_literal},
        ).fetchall()
    ]
    assert len(farthest_ids) == 40, "need a real, non-trivial adversarial restriction to prove anything"

    # Ground truth query above deliberately disabled the ANN index so it
    # can't itself be approximate; re-enable it before exercising
    # `search_semantic` so this test hits the real, default-configured
    # planner behaviour (same GUCs a normal caller would see), not a
    # sandbox where the bug can't occur because the index is off.
    conn.execute(text("SET LOCAL enable_indexscan = on"))
    conn.execute(text("SET LOCAL enable_indexonlyscan = on"))

    # Ground truth: these 40 ids really are in the table under this model.
    present = conn.execute(
        text(
            "SELECT count(*) FROM engine.embeddings "
            "WHERE entity_type = 'article' AND model = :model AND entity_id::int = ANY(:ids)"
        ),
        {"model": REAL_MODEL, "ids": farthest_ids},
    ).scalar()
    assert present == 40

    hits = semantic.search_semantic(conn, vec, model=REAL_MODEL, limit=10, candidate_ids=farthest_ids)

    assert len(hits) > 0, (
        "F67 regressed: a non-empty, fully-present restriction came back "
        "empty from the restricted kNN path"
    )
    assert len(hits) == 10
    assert {int(h.entity_id) for h in hits}.issubset(set(farthest_ids))
    # Best-first ordering must still hold on the exact path.
    sims = [h.raw_score for h in hits]
    assert sims == sorted(sims, reverse=True)
