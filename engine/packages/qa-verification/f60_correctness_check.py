"""QA.5 F60 verification: embedding correctness check.
Run from engine/packages/search's own venv:
  cd engine/packages/search && .venv/Scripts/python.exe ../qa-verification/f60_correctness_check.py
"""
from __future__ import annotations

import numpy as np

from now_search import query_embedder

query_embedder.warm_up()

pairs_similar = [
    ("rooftop bar senopati", "rooftop bar in senopati jakarta"),
    ("best italian restaurant", "top italian restaurants nearby"),
]
pairs_dissimilar = [
    ("rooftop bar senopati", "pediatric dentist insurance claim"),
    ("best italian restaurant", "quarterly tax filing deadline"),
]

texts = [t for pair in (pairs_similar + pairs_dissimilar) for t in pair]
vecs = {}
for t in set(texts):
    v = np.array(query_embedder.embed_query(t))
    vecs[t] = v
    print(f"dim={v.shape[0]} norm={np.linalg.norm(v):.6f}  text={t!r}")

def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

print()
print("SIMILAR pairs:")
for a, b in pairs_similar:
    print(f"  cos({a!r}, {b!r}) = {cos(vecs[a], vecs[b]):.4f}")

print("DISSIMILAR pairs:")
for a, b in pairs_dissimilar:
    print(f"  cos({a!r}, {b!r}) = {cos(vecs[a], vecs[b]):.4f}")
