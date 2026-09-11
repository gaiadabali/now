"""Reciprocal Rank Fusion (ARCHITECTURE.md §7 "Search"):

    score(doc) = sum over rails r containing doc of  1 / (k + rank_r(doc))

`rank_r` is 1-indexed (best result in a rail = rank 1). A document
missing from a rail simply does not contribute that rail's term -- it is
NOT scored as if it were at some very low rank, and it is NOT excluded
from the fused list (a doc found by only one rail still surfaces, just
lower, unless MMR/E3.3 later decides otherwise).

RRF (not score-normalisation) is the fusion method **because BM25's
ts_rank_cd and pgvector's cosine similarity live on incomparable scales**
(§7): ts_rank_cd is an unbounded, corpus- and query-length-dependent
number; cosine similarity is bounded [-1, 1] and, for this embedding
model, empirically clusters tightly (~0.4-0.9) regardless of match
quality. Min-max normalising either onto [0,1] and summing would let
whichever rail happens to have wider spread on a given query dominate
the fused score -- RRF sidesteps that entirely by working in rank-space
instead.

Pure functions, no I/O, no DB -- unit-tested directly against the
canonical RRF formula and against hand-built rank lists.
"""

from __future__ import annotations

from now_search.models import FusedHit, RankedHit

DEFAULT_K = 60


def _rrf_term(rank: int | None, k: float) -> float:
    return 0.0 if rank is None else 1.0 / (k + rank)


def reciprocal_rank_fusion(
    lexical: list[RankedHit],
    semantic: list[RankedHit],
    *,
    k: float = DEFAULT_K,
) -> list[FusedHit]:
    """Fuse two ranked lists (lexical, semantic), best-first each, into one
    RRF-scored, best-first list. Every entity_id appearing in EITHER input
    list appears exactly once in the output -- RRF fusion is a union over
    rails, not an intersection."""
    lex_by_id = {h.entity_id: h for h in lexical}
    sem_by_id = {h.entity_id: h for h in semantic}
    all_ids = dict.fromkeys([*lex_by_id.keys(), *sem_by_id.keys()])  # de-dup, preserve first-seen order

    fused: list[FusedHit] = []
    for entity_id in all_ids:
        lex_hit = lex_by_id.get(entity_id)
        sem_hit = sem_by_id.get(entity_id)
        lex_rank = lex_hit.rank if lex_hit else None
        sem_rank = sem_hit.rank if sem_hit else None
        score = _rrf_term(lex_rank, k) + _rrf_term(sem_rank, k)
        fused.append(
            FusedHit(
                entity_id=entity_id,
                rrf_score=score,
                lexical_rank=lex_rank,
                semantic_rank=sem_rank,
                lexical_raw_score=lex_hit.raw_score if lex_hit else None,
                semantic_raw_score=sem_hit.raw_score if sem_hit else None,
            )
        )

    # Stable sort by score desc; ties broken by entity_id so output order
    # is deterministic (matters for reproducible eval runs and tests).
    fused.sort(key=lambda h: (-h.rrf_score, h.entity_id))
    return fused


def to_ranked_hits(pairs: list[tuple[str, float]]) -> list[RankedHit]:
    """Helper: (entity_id, raw_score) pairs, already best-first, -> RankedHit
    with 1-indexed rank assigned by position. Used by lexical.py/semantic.py
    so callers don't hand-roll `enumerate(..., start=1)` at every call site."""
    return [RankedHit(entity_id=eid, rank=i, raw_score=score) for i, (eid, score) in enumerate(pairs, start=1)]
