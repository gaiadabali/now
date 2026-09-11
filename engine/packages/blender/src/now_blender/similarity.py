"""Real embedding cosine similarity for MMR -- the piece
`now_filters.diversity`'s own docstring asks for: "callers with real
vectors pass a cosine-similarity closure over `engine.embeddings`;
`default_facet_similarity` ... is a zero-dependency fallback ... not a
recommended production similarity measure." This module IS that closure.

**Bulk-fetch, not per-pair query.** MMR's greedy loop calls
`similarity_fn(candidate, selected)` up to `O(k * pool_size)` times for a
`k`-slot, `pool_size`-candidate diversify() call (ARCHITECTURE.md Sec.7:
re-rank "top ~40" -- so at most ~40*10 calls for a 10-slot result). Firing
one SQL query per call would be 40x-400x more round trips than
necessary; instead `EmbeddingSimilarity.load` issues ONE query for every
candidate's vector up front (`entity_type`/`entity_id`/`model`-filtered,
per F42's "always filter WHERE model = :model" -- an unfiltered query
would return meaningless cross-model neighbours) and every subsequent
`similarity_fn` call is a pure in-memory dot product.

**Graceful, documented fallback -- never a silent zero.** A candidate
with no embedding row under this model (should not happen for a
published article post-E2.4's backfill, but this module does not assume
it never happens) falls back to `now_filters.diversity.
default_facet_similarity` for that one pair, logged via `missing_ids` so
a caller can see how often the fallback fired rather than discovering it
only by a suspiciously-low diversity score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_filters.diversity import SimilarityFn, default_facet_similarity
from now_filters.models import Candidate

_SELECT_VECS_SQL = text(
    """
    SELECT entity_type, entity_id, vec::text AS vec_text
      FROM engine.embeddings
     WHERE model = :model AND (entity_type, entity_id) = ANY(:keys)
    """
)


def _parse_vec(vec_text: str) -> list[float]:
    # pgvector's text form is "[0.1,0.2,...]" -- no whitespace, no
    # exponent-free guarantee needed since Python's float() parses
    # scientific notation the same as fixed-point.
    return [float(x) for x in vec_text.strip("[]").split(",")]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return _dot(a, a) ** 0.5


@dataclass
class EmbeddingSimilarity:
    """Holds one model's worth of pre-fetched, pre-normalized vectors for
    a fixed candidate set and exposes a `SimilarityFn` closure over them."""

    model: str
    vectors: dict[tuple[str, int], list[float]] = field(default_factory=dict)
    norms: dict[tuple[str, int], float] = field(default_factory=dict)
    missing_keys: list[tuple[str, int]] = field(default_factory=list)
    fallback_calls: int = 0

    @classmethod
    def load(cls, conn: Connection, candidates: list[Candidate], *, model: str) -> "EmbeddingSimilarity":
        keys = [(c.entity_type, c.entity_id) for c in candidates]
        wanted = set(keys)
        self = cls(model=model)
        if not keys:
            return self
        # SQLAlchemy needs a list of tuples for `= ANY(:keys)` against a
        # composite -- Postgres wants ROW(...) pairs; simplest robust
        # form given psycopg's adaptation is per-entity_type batching,
        # since entity_type is one of two known short strings.
        by_type: dict[str, list[int]] = {}
        for entity_type, entity_id in keys:
            by_type.setdefault(entity_type, []).append(entity_id)
        for entity_type, ids in by_type.items():
            rows = conn.execute(
                text(
                    """
                    SELECT entity_id, vec::text AS vec_text
                      FROM engine.embeddings
                     WHERE model = :model AND entity_type = :entity_type
                       AND entity_id = ANY(:ids)
                    """
                ),
                {"model": model, "entity_type": entity_type, "ids": [str(i) for i in ids]},
            ).fetchall()
            for entity_id_text, vec_text in rows:
                key = (entity_type, int(entity_id_text))
                vec = _parse_vec(vec_text)
                self.vectors[key] = vec
                self.norms[key] = _norm(vec)
        self.missing_keys = sorted(wanted - set(self.vectors.keys()))
        return self

    def cosine(self, a_key: tuple[str, int], b_key: tuple[str, int]) -> float | None:
        va, vb = self.vectors.get(a_key), self.vectors.get(b_key)
        if va is None or vb is None:
            return None
        na, nb = self.norms[a_key], self.norms[b_key]
        if na == 0.0 or nb == 0.0:
            return 0.0
        return _dot(va, vb) / (na * nb)

    def similarity_fn(self) -> SimilarityFn:
        def _fn(a: Candidate, b: Candidate) -> float:
            sim = self.cosine(a.key, b.key)
            if sim is not None:
                return sim
            self.fallback_calls += 1
            return default_facet_similarity(a, b)

        return _fn


def build_similarity_fn(conn: Connection, candidates: list[Candidate], *, model: str) -> tuple[SimilarityFn, EmbeddingSimilarity]:
    """Convenience one-liner for `reranker.py`: returns the closure to
    hand to `now_filters.diversity.diversify(..., similarity_fn=...)`
    plus the `EmbeddingSimilarity` instance itself (so a caller can log
    `missing_keys`/`fallback_calls` for observability)."""
    loader = EmbeddingSimilarity.load(conn, candidates, model=model)
    return loader.similarity_fn(), loader
