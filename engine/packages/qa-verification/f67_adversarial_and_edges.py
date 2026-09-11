"""QA.5: (4) own adversarial restriction unrelated to vector similarity,
and (5) edge cases for the materialized-CTE fix in now_search.semantic.
Throwaway, read/query-only against now_jakarta. No product code touched."""
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
    conn.execute(text("SELECT entity_id::int FROM engine.embeddings LIMIT 1"))


def get_all_vecs(conn):
    rows = conn.execute(text(
        "SELECT entity_id::int AS id, vec FROM engine.embeddings "
        "WHERE entity_type = :et AND model = :m"
    ), {"et": ENTITY_TYPE, "m": MODEL}).fetchall()
    return {r.id: np.array([float(x) for x in r.vec[1:-1].split(",")]) for r in rows}


def cosine_sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def is_prime(n):
    if n < 2:
        return False
    for p in range(2, int(n ** 0.5) + 1):
        if n % p == 0:
            return False
    return True


with engine.connect() as conn:
    warm(conn)
    vecs = get_all_vecs(conn)
    max_id = conn.execute(text(
        "SELECT max(entity_id::int) FROM engine.embeddings WHERE entity_type=:et AND model=:m"
    ), {"et": ENTITY_TYPE, "m": MODEL}).scalar()

subject_id = sorted(vecs)[len(vecs) // 2]
qvec = vecs[subject_id]
qvec_literal = _vec_literal(list(qvec))
all_ids = [i for i in vecs if i != subject_id]

print("=" * 70)
print("(4) OWN adversarial restriction: prime-numbered entity_ids (unrelated")
print("    to vector similarity by construction), subject_id =", subject_id)
print("=" * 70)
prime_ids = [i for i in all_ids if is_prime(i)]
print(f"prime candidate_ids count: {len(prime_ids)} (of {len(all_ids)} total)")

with engine.connect() as conn:
    warm(conn)
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=prime_ids)
got_ids = [int(h.entity_id) for h in hits]
expected = sorted(prime_ids, key=lambda i: -cosine_sim(qvec, vecs[i]))[:10]
print("search_semantic top-10:", got_ids)
print("independently computed exact top-10 (restricted to primes):", expected)
print("MATCH:", got_ids == expected)
print()

print("=" * 70)
print("(5) Edge cases")
print("=" * 70)

with engine.connect() as conn:
    warm(conn)

    # (a) empty candidate_ids
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=[])
    print("(a) empty candidate_ids -> hits:", hits, "  [expect 0, correctly -- nothing to restrict to]")

    # (b) single id, which is a genuine match (should return exactly 1 row)
    one_id = [all_ids[0]]
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=one_id)
    print(f"(b) single existing id {one_id} -> hits:", hits, "  [expect exactly 1 row]")

    # (c) candidate_ids larger than whole table (all real ids + far-out fake ones)
    fake_ids = list(range(max_id + 1, max_id + 5001))
    big_list = all_ids + fake_ids
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=big_list)
    got = [int(h.entity_id) for h in hits]
    expected_big = sorted(all_ids, key=lambda i: -cosine_sim(qvec, vecs[i]))[:10]
    print(f"(c) candidate_ids larger than table (n={len(big_list)}, incl. {len(fake_ids)} nonexistent)")
    print("    got:", got)
    print("    expected (exact, full real set):", expected_big)
    print("    MATCH:", got == expected_big)

    # (d) duplicate ids in candidate list
    dup_id = all_ids[3]
    dup_list = [dup_id] * 50 + all_ids[:5]
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=dup_list)
    got_dup = [int(h.entity_id) for h in hits]
    print(f"(d) duplicate ids ({dup_id} x50 + 5 others) -> got {len(hits)} hits, ids: {got_dup}",
          "  [expect no duplicate rows in output despite duplicate input ids]")
    print("    no dup rows:", len(got_dup) == len(set(got_dup)))

    # (e) ids that don't exist at all, mixed with a few real ones
    nonexist = [max_id + 100, max_id + 200, max_id + 300]
    mixed = nonexist + all_ids[:3]
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=mixed)
    got_mixed = [int(h.entity_id) for h in hits]
    expected_mixed = sorted(all_ids[:3], key=lambda i: -cosine_sim(qvec, vecs[i]))
    print(f"(e) 3 nonexistent ids + 3 real ids -> got: {got_mixed}, expected: {expected_mixed}",
          "  MATCH:", got_mixed == expected_mixed)

    # (f) candidate_ids entirely nonexistent -- must be legitimately empty result
    all_fake = [max_id + 1000, max_id + 1001, max_id + 1002]
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=10, candidate_ids=all_fake)
    print(f"(f) all-nonexistent candidate_ids {all_fake} -> hits:", hits,
          "  [expect 0 -- legitimately no match, not a bug]")

    # (g) None (unrestricted path) still works / sanity baseline
    hits = search_semantic(conn, list(qvec), model=MODEL, limit=5, candidate_ids=None)
    print("(g) candidate_ids=None (unrestricted global path) top-5:", [h.entity_id for h in hits])
