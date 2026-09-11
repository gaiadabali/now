"""Shared result types passed between the lexical/semantic/RRF/facet
layers and the outer `SearchEngine` API. Kept dependency-free (plain
dataclasses) so `rrf.py` stays pure and unit-testable with no DB."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RankedHit:
    """One (entity_id, rank) pair from a single retrieval rail.
    `entity_id` is `public.articles.id` as a string -- the same
    stringified-int convention `engine.embeddings.entity_id` already
    uses (see now_embeddings/store.py). `rank` is 1-indexed, best
    result first."""

    entity_id: str
    rank: int
    raw_score: float  # ts_rank_cd or cosine similarity -- NOT comparable across rails, kept only for the Inspector/debug trace


@dataclass(frozen=True)
class FusedHit:
    entity_id: str
    rrf_score: float
    lexical_rank: int | None  # None if this doc was not in the lexical top-N at all
    semantic_rank: int | None
    lexical_raw_score: float | None = None
    semantic_raw_score: float | None = None


@dataclass(frozen=True)
class SearchTiming:
    lexical_ms: float
    semantic_ms: float
    fuse_ms: float
    total_ms: float


@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: list[FusedHit]
    facet_counts: dict[str, dict[str, int]]
    timing: SearchTiming
    lexical_candidate_count: int = 0
    semantic_candidate_count: int = 0


@dataclass(frozen=True)
class ArticleSummary:
    """Just enough to hand-check a result set (§ "hand-check ~10 real
    queries") without a second round trip per hit."""

    id: int
    title: str
    dek: str | None
    legacy_wp_id: int | None
    legacy_permalink: str | None
