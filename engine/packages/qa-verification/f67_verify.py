"""QA.5 independent re-verification of F67 (silent-zero-rows restricted kNN fix).

Throwaway verification script. Does NOT modify product code. Talks directly
to now_jakarta via the real now_search engine/connections helper, and issues
both the OLD (pre-fix, naive ANY()) query shape and the REAL current
`search_semantic` function from now_search.semantic, so we can compare them
head to head against the same live HNSW index.
"""
from __future__ import annotations

import sys
import numpy as np
from sqlalchemy import text

sys.path.insert(0, r"C:\Users\Hansel\Documents\Hansel\Projects\now\engine\packages\search\src")

from now_search.connections import city_engine
from now_search.semantic import search_semantic, _vec_literal

MODEL = "BAAI/bge-small-en-v1.5"
ENTITY_TYPE = "article"

engine = city_engine("now_jakarta")


def warm(conn):
    # Custom GUCs (hnsw.*) are only registered once vector's shared lib is
    # touched in this backend; do one cheap vector op to make SET/SHOW work.
    conn.execute(text("SELECT entity_id::int FROM engine.embeddings LIMIT 1"))


def get_all_vecs(conn):
    rows = conn.execute(text(
        "SELECT entity_id::int AS id, vec FROM engine.embeddings "
        "WHERE entity_type = :et AND model = :m"
    ), {"et": ENTITY_TYPE, "m": MODEL}).fetchall()
    return {r.id: np.array([float(x) for x in r.vec[1:-1].split(",")]) for r in rows}


def cosine_sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def old_naive_query(conn, qvec_literal, candidate_ids, limit=10, explain=False):
    sql = """
        SELECT entity_id::int AS article_id, 1 - (vec <=> CAST(:qvec AS vector)) AS cosine_sim
          FROM engine.embeddings
         WHERE entity_type = :entity_type
           AND model = :model
           AND entity_id::int = ANY(:candidate_ids)
         ORDER BY vec <=> CAST(:qvec AS vector)
         LIMIT :limit
    """
    params = {"qvec": qvec_literal, "entity_type": ENTITY_TYPE, "model": MODEL,
              "candidate_ids": candidate_ids, "limit": limit}
    if explain:
        plan = conn.execute(text("EXPLAIN (ANALYZE, BUFFERS) " + sql), params).fetchall()
        return "\n".join(r[0] for r in plan)
    return conn.execute(text(sql), params).fetchall()


print("=" * 70)
print("STEP 1: confirm defaults + index shape")
print("=" * 70)
with engine.connect() as conn:
    warm(conn)
    ef = conn.execute(text("SHOW hnsw.ef_search")).scalar()
    it = conn.execute(text("SHOW hnsw.iterative_scan")).scalar()
    idxdef = conn.execute(text(
        "SELECT indexdef FROM pg_indexes WHERE indexname='ix_embeddings_hnsw'"
    )).scalar()
    total = conn.execute(text(
        "SELECT count(*) FROM engine.embeddings WHERE entity_type=:et AND model=:m"
    ), {"et": ENTITY_TYPE, "m": MODEL}).scalar()
    print("hnsw.ef_search =", ef)
    print("hnsw.iterative_scan =", it)
    print("index def:", idxdef)
    print("total article embeddings for model:", total)

    vecs = get_all_vecs(conn)

# pick a "subject" query vector: use an arbitrary real article's embedding as query.
subject_id = sorted(vecs)[0]
qvec = vecs[subject_id]
qvec_literal = _vec_literal(list(qvec))

# rank ALL ids by exact cosine sim to subject vector (ground truth ranking).
all_ids = [i for i in vecs if i != subject_id]
ranked_all = sorted(all_ids, key=lambda i: -cosine_sim(qvec, vecs[i]))
farthest_40 = ranked_all[-40:]  # least similar 40 -- old docstring's adversarial repro

print()
print("=" * 70)
print("STEP 2: reproduce ORIGINAL failure -- naive ANY() restricted query,")
print("restriction = 40 FARTHEST (least similar) ids from subject vector")
print("=" * 70)
with engine.connect() as conn:
    warm(conn)
    plan = old_naive_query(conn, qvec_literal, farthest_40, limit=10, explain=True)
    print(plan)
    rows = old_naive_query(conn, qvec_literal, farthest_40, limit=10, explain=False)
    print("naive query returned rows:", rows)
    # confirm all 40 actually exist in the table
    cnt = conn.execute(text(
        "SELECT count(*) FROM engine.embeddings WHERE entity_type=:et AND model=:m "
        "AND entity_id::int = ANY(:ids)"
    ), {"et": ENTITY_TYPE, "m": MODEL, "ids": farthest_40}).scalar()
    print(f"plain WHERE-only count confirms {cnt}/{len(farthest_40)} of the 40 ids exist in table")

print()
print("=" * 70)
print("STEP 3: same restriction through REAL search_semantic (fixed path)")
print("=" * 70)
with engine.connect() as conn:
    warm(conn)
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=farthest_40)
    print("search_semantic returned", len(hits), "hits:")
    for h in hits:
        print(" ", h)
    expected_top10 = sorted(farthest_40, key=lambda i: -cosine_sim(qvec, vecs[i]))[:10]
    got_ids = [int(h.entity_id) for h in hits]
    print("expected top-10 (by our own exact cosine, restricted set):", expected_top10)
    print("got:                                                     ", got_ids)
    print("MATCH:", got_ids == expected_top10)
