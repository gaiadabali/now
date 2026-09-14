"""Pydantic wire models for `GET /v1/{site}/search` (ARCHITECTURE.md §16).

Mirrors `now_search.models`' dataclasses; this module owns no retrieval
logic, only the wire shape -- the same split `app/domain/rails/schemas.py`
keeps.

`lexical_rank` / `semantic_rank` ride on every hit because they are the
only way, from outside the process, to tell *which rail won a result*.
§7's whole correction (the nDCG 0.7642 -> 0.375 regression) was a lexical
signal silently vanishing from the blend; a response that reports only a
fused score cannot show that happening again. They are debug-grade, not
reader-facing, but they cost two integers.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SearchTimingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    lexical_ms: float
    semantic_ms: float
    fuse_ms: float
    filter_ms: float = Field(description="Hard-filter candidate resolution (§8.G), which runs before retrieval.")
    total_ms: float


class SearchHitOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_type: str = Field(default="article", description="Only 'article' today; places search lands with /places.")
    entity_id: int
    position: int = Field(description="1-indexed slot -- beacon data-nowb-position value.")
    rrf_score: float
    lexical_rank: int | None = Field(default=None, description="Rank in the lexical rail, or null if it did not appear there.")
    semantic_rank: int | None = Field(default=None, description="Rank in the semantic rail, or null if it did not appear there.")
    title: str | None = None
    dek: str | None = None
    legacy_permalink: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    rail: str = Field(default="search", description="Beacon data-nowb-rail value for every card in this response.")
    hits: list[SearchHitOut]
    facet_counts: dict[str, dict[str, int]] = Field(
        description="{facet: {value: n}} over the fused candidate set -- 'if you also filtered by X, how many of these would remain'."
    )
    candidate_count: int = Field(description="Rows surviving the hard filter, i.e. the pool retrieval actually searched.")
    lexical_candidate_count: int
    semantic_candidate_count: int
    timing: SearchTimingOut
    unresolved_facets: list[str] = Field(
        default_factory=list,
        description="Requested facet:term selectors that matched no term in engine.terms -- reported, never silently dropped.",
    )
