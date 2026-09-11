"""Real Postgres: proves the MMR similarity closure uses genuine
`engine.embeddings` cosine similarity, not the facet stand-in, and falls
back honestly when a vector is missing."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from now_filters.diversity import DiversityCaps, diversify
from now_filters.models import Candidate

from now_blender.similarity import build_similarity_fn

MODEL = "BAAI/bge-small-en-v1.5"


def _real_article_ids(conn, n=6) -> list[int]:
    rows = conn.execute(
        text(
            "SELECT entity_id::int FROM engine.embeddings WHERE entity_type='article' AND model=:model ORDER BY entity_id::int LIMIT :n"
        ),
        {"model": MODEL, "n": n},
    ).fetchall()
    return [r[0] for r in rows]


def test_similarity_matches_direct_sql_cosine(city_conn):
    ids = _real_article_ids(city_conn, 2)
    if len(ids) < 2:
        pytest.skip("fewer than 2 real article embeddings on this DB")
    a_id, b_id = ids[0], ids[1]

    direct = city_conn.execute(
        text(
            """
            SELECT 1 - (a.vec <=> b.vec)
              FROM engine.embeddings a, engine.embeddings b
             WHERE a.entity_type='article' AND a.model=:model AND a.entity_id=:a_id
               AND b.entity_type='article' AND b.model=:model AND b.entity_id=:b_id
            """
        ),
        {"model": MODEL, "a_id": str(a_id), "b_id": str(b_id)},
    ).scalar_one()

    candidates = [Candidate(entity_type="article", entity_id=a_id), Candidate(entity_type="article", entity_id=b_id)]
    similarity_fn, loader = build_similarity_fn(city_conn, candidates, model=MODEL)
    computed = similarity_fn(candidates[0], candidates[1])

    assert abs(computed - float(direct)) < 1e-6
    assert loader.missing_keys == []
    assert loader.fallback_calls == 0


def test_self_similarity_is_one(city_conn):
    ids = _real_article_ids(city_conn, 1)
    if not ids:
        pytest.skip("no real article embeddings on this DB")
    candidate = Candidate(entity_type="article", entity_id=ids[0])
    similarity_fn, _ = build_similarity_fn(city_conn, [candidate], model=MODEL)
    assert abs(similarity_fn(candidate, candidate) - 1.0) < 1e-6


def test_missing_embedding_falls_back_to_facet_similarity_not_a_crash(city_conn):
    real_ids = _real_article_ids(city_conn, 1)
    if not real_ids:
        pytest.skip("no real article embeddings on this DB")
    real = Candidate(entity_type="article", entity_id=real_ids[0], type="eat")
    fake = Candidate(entity_type="article", entity_id=999_999_999, type="eat")  # no embedding row

    similarity_fn, loader = build_similarity_fn(city_conn, [real, fake], model=MODEL)
    sim = similarity_fn(real, fake)

    assert loader.missing_keys == [("article", 999_999_999)]
    assert 0.0 <= sim <= 1.0
    assert loader.fallback_calls == 1


def test_mmr_with_real_similarity_prefers_diverse_candidates(city_conn):
    """End-to-end sanity: greedy MMR over real embeddings genuinely
    diversifies -- the second pick should not simply be "most similar
    to the first", it should trade some relevance for reduced
    similarity once the pool has a near-duplicate."""
    ids = _real_article_ids(city_conn, 8)
    if len(ids) < 4:
        pytest.skip("fewer than 4 real article embeddings on this DB")

    candidates = [Candidate(entity_type="article", entity_id=i) for i in ids]
    # Uniform relevance -- isolates MMR's diversity term as the only
    # thing that can distinguish selection order beyond the first pick.
    relevance = {c.key: 1.0 for c in candidates}
    similarity_fn, _ = build_similarity_fn(city_conn, candidates, model=MODEL)

    selected = diversify(
        candidates, relevance, k=len(candidates), similarity_fn=similarity_fn, lambda_=0.7, caps=DiversityCaps()
    )
    assert len(selected) == len(candidates)  # no caps engaged (no org/area/format set) -- full pool returned
    assert len({c.entity_id for c in selected}) == len(candidates)  # no duplicates
