"""Display-oriented dataclasses for the Inspector. Deliberately separate
from `now_search.models` (which stays untouched, per scope): those types
carry exactly what the search engine needs internally; these carry
exactly what the Inspector's templates need to *explain* a result --
every field here exists because some panel prints a label next to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArticleRow:
    id: int
    title: str
    dek: str | None
    legacy_wp_id: int | None
    legacy_permalink: str | None
    primary_type: str | None
    format: str | None
    series_key: str | None
    status: str | None
    published_at: str | None


@dataclass(frozen=True)
class ComponentExplained:
    """One labelled number in the "why did this rank here" breakdown."""

    key: str
    label: str
    value: float | None
    explanation: str
    available: bool = True


@dataclass(frozen=True)
class QualityBreakdown:
    entity_id: str
    score: float | None
    components: dict | None
    found: bool
    note: str = ""


@dataclass(frozen=True)
class FreshnessResult:
    format: str | None
    half_life_label: str
    days_old: float | None
    decay_component: float | None
    note: str


@dataclass(frozen=True)
class FilterTraceEntry:
    """One filter rule's verdict on one candidate."""

    rule: str
    rule_source: str  # e.g. "ARCHITECTURE.md §8.A"
    removed: bool
    reason: str
    data_status: str = "available"  # "available" | "not classified yet" | "not applicable"


@dataclass(frozen=True)
class CandidateTrace:
    article: ArticleRow | None
    entity_id: str
    lexical_rank: int | None
    lexical_raw_score: float | None
    semantic_rank: int | None
    semantic_raw_score: float | None
    rrf_score: float
    quality: QualityBreakdown | None
    freshness: FreshnessResult | None
    blended_score: float | None
    blend_components: list[ComponentExplained] = field(default_factory=list)
    filter_trace: list[FilterTraceEntry] = field(default_factory=list)
    survived: bool = True
    survival_reason: str = ""


@dataclass(frozen=True)
class FallbackRungInfo:
    rail: str
    rung_reached: int | None
    rung_label: str | None
    available: bool
    note: str


@dataclass(frozen=True)
class GeneratorPanel:
    """Raw, pre-fusion output of one candidate generator."""

    name: str
    description: str
    hits: list[dict]  # [{rank, entity_id, raw_score, title}]
    candidate_count: int
    warning: str = ""
