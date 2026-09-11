"""A numpy-backed drop-in for `now_blender.similarity.build_similarity_fn`
-- same contract (`now_filters.diversity.SimilarityFn`), same graceful
`default_facet_similarity` fallback for a candidate with no embedding row,
same batched-fetch-then-compute-in-memory shape. The only difference is
*how* the per-pair cosine is computed.

**Measured necessity, not a style preference.** `now_blender.similarity
.EmbeddingSimilarity.cosine` computes `sum(x*y for x, y in zip(...))`
over 384-dim vectors in plain Python. Profiled with `cProfile` composing
this package's own rails: MMR's `O(k * pool_size)` call pattern (up to
~400 pairwise calls for a 10-slot pick from a 40-candidate pool, per that
module's own docstring) turns a ~90us-per-call cost into tens of
milliseconds -- material against this ticket's p95 < 120ms target,
alongside `row3_similar.py`'s own discovery that a pure-Python cosine
loop was Row 3's single largest cost before being replaced with numpy.
Pre-normalizing every vector once at load time and taking a plain numpy
dot product per pair does the identical arithmetic through a compiled
loop instead of a Python-level generator.

Not a claim that `now_blender.similarity` is wrong -- its one demonstrated
caller (`now_blender.reranker`, plain keyword search) does not compose
kNN + MMR at this call volume in one request. `now_blender/` is out of
this ticket's scope to edit (see the package README), so this rail
composes the identical *contract* with its own, faster implementation
rather than the slower one.

**F70 update.** `row3_similar.py`'s own semantic-kNN ranking used to be a
sibling numpy workaround in this same spirit (`_restricted_semantic_knn`,
worked around a since-fixed `now_search` bug -- see F67/PROGRESS.md); that
ranking is now `now_search.semantic.search_semantic`'s job, done exactly
in SQL. This module's job was never that ranking -- it is, and remains,
pairwise candidate-to-candidate similarity for MMR diversification, which
`search_semantic` does not and should not provide. Nothing about that job
changed; only how `row3_similar.py` supplies this module its candidates
did (`.load()` now, not a preloaded batch -- see `from_preloaded`'s own
docstring).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from now_filters.diversity import SimilarityFn, default_facet_similarity
from now_filters.models import Candidate
from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass
class FastEmbeddingSimilarity:
    model: str
    vectors: dict[tuple[str, int], np.ndarray] = field(default_factory=dict)  # pre-normalized (unit L2 norm)
    missing_keys: list[tuple[str, int]] = field(default_factory=list)
    fallback_calls: int = 0

    @classmethod
    def from_preloaded(
        cls,
        entity_type: str,
        preloaded: dict[int, np.ndarray],
        candidates: list[Candidate],
        *,
        model: str,
        conn: Connection | None = None,
    ) -> "FastEmbeddingSimilarity":
        """Builds a similarity source from vectors a caller already
        fetched (already unit-normalized) for THIS entity type, saving a
        second, otherwise-identical round trip against `engine.embeddings`
        for the same id set a caller's own ranking step already queried.

        F70: `row3_similar.py` used to be exactly such a caller (its own
        now-removed `_restricted_semantic_knn` numpy workaround fetched
        and ranked candidate vectors itself, then handed them here). Now
        that ranking is `now_search.semantic.search_semantic`'s job (a
        pure SQL/`RankedHit` API that does not -- and should not -- hand
        back vectors), `row3_similar.py` uses `.load()` instead. Kept as a
        constructor on this class for any future caller that similarly
        already holds a preloaded, unit-normalized vector batch --
        `.load()` remains the right choice for a caller (like
        `row3_similar.py` today) that does not.

        Any candidate not covered by `preloaded` (should not happen when
        every candidate came from the same kNN call that produced
        `preloaded`, but not assumed) falls back to a live query via
        `conn` if given, else is simply treated as missing (graceful
        `default_facet_similarity` fallback, same as `.load()`)."""
        self = cls(model=model)
        self.vectors = {(entity_type, eid): vec for eid, vec in preloaded.items()}
        wanted = {(c.entity_type, c.entity_id) for c in candidates}
        missing = wanted - set(self.vectors.keys())
        if missing and conn is not None:
            missing_ids = [eid for (_, eid) in missing]
            rows = conn.execute(
                text(
                    """
                    SELECT entity_id, vec::text AS vec_text
                      FROM engine.embeddings
                     WHERE model = :model AND entity_type = :entity_type AND entity_id = ANY(:ids)
                    """
                ),
                {"model": model, "entity_type": entity_type, "ids": [str(i) for i in missing_ids]},
            ).fetchall()
            for entity_id_text, vec_text in rows:
                arr = np.array([float(x) for x in vec_text.strip("[]").split(",")], dtype=np.float32)
                norm = float(np.linalg.norm(arr))
                self.vectors[(entity_type, int(entity_id_text))] = arr / norm if norm > 0 else arr
            missing = wanted - set(self.vectors.keys())
        self.missing_keys = sorted(missing)
        return self

    @classmethod
    def load(cls, conn: Connection, candidates: list[Candidate], *, model: str) -> "FastEmbeddingSimilarity":
        self = cls(model=model)
        if not candidates:
            return self
        by_type: dict[str, list[int]] = {}
        for c in candidates:
            by_type.setdefault(c.entity_type, []).append(c.entity_id)
        for entity_type, ids in by_type.items():
            rows = conn.execute(
                text(
                    """
                    SELECT entity_id, vec::text AS vec_text
                      FROM engine.embeddings
                     WHERE model = :model AND entity_type = :entity_type AND entity_id = ANY(:ids)
                    """
                ),
                {"model": model, "entity_type": entity_type, "ids": [str(i) for i in ids]},
            ).fetchall()
            for entity_id_text, vec_text in rows:
                arr = np.array([float(x) for x in vec_text.strip("[]").split(",")], dtype=np.float32)
                norm = float(np.linalg.norm(arr))
                self.vectors[(entity_type, int(entity_id_text))] = arr / norm if norm > 0 else arr
        wanted = {(c.entity_type, c.entity_id) for c in candidates}
        self.missing_keys = sorted(wanted - set(self.vectors.keys()))
        return self

    def cosine(self, a_key: tuple[str, int], b_key: tuple[str, int]) -> float | None:
        va, vb = self.vectors.get(a_key), self.vectors.get(b_key)
        if va is None or vb is None:
            return None
        return float(np.dot(va, vb))  # both pre-normalized -- dot product IS cosine similarity

    def similarity_fn(self) -> SimilarityFn:
        def _fn(a: Candidate, b: Candidate) -> float:
            sim = self.cosine(a.key, b.key)
            if sim is not None:
                return sim
            self.fallback_calls += 1
            return default_facet_similarity(a, b)

        return _fn


def build_fast_similarity_fn(
    conn: Connection, candidates: list[Candidate], *, model: str
) -> tuple[SimilarityFn, FastEmbeddingSimilarity]:
    loader = FastEmbeddingSimilarity.load(conn, candidates, model=model)
    return loader.similarity_fn(), loader
