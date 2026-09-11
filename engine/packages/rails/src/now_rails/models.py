"""Shared result types for the three rails. Kept dependency-light
(dataclasses only) so `cache.py`'s JSON (de)serialization and the API's
Pydantic mapping both have one stable shape to target.

`RailName` is the literal set ARCHITECTURE.md Sec.7's table names and
Sec.16's endpoint returns "all three rows" for -- also the exact
`surface`/`rail` strings that should end up in `engine.impressions.rail`
via the beacon (Sec.10), so the FE's `data-nowb-rail` attribute and this
package's own `now_blender.feature_log` `surface` field
(`"row1_complementary" | "row2_nearby" | "row3_similar"`, already named in
that module's own docstring) both point at the same three strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

ROW1 = "row1_complementary"
ROW2 = "row2_nearby"
ROW3 = "row3_similar"
RAIL_NAMES: tuple[str, ...] = (ROW1, ROW2, ROW3)

DEFAULT_SEGMENT = "default"  # ARCHITECTURE.md Sec.7: "~20 coarse taste segments" -- E7.4, not built.
# One default segment now, read/written explicitly everywhere a real segment
# id would go (`cache.py`'s PK, `RailsBundle.segment`) so wiring a real
# segmenter later is a value change, not a shape change.


@dataclass(frozen=True)
class ComponentScoreOut:
    """Field-for-field mirror of `now_blender.components.ComponentScore`
    (itself mirroring `now_inspector.models.ComponentExplained`) -- kept as
    its own type here rather than importing `now_blender`'s dataclass
    directly so `cache.py` can round-trip it through jsonb without any
    producer-package import at read time (a cache HIT must not need a live
    `now_blender` object graph, only plain data)."""

    key: str
    label: str
    value: float | None
    weight: float
    explanation: str
    available: bool

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "weight": self.weight,
            "explanation": self.explanation,
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComponentScoreOut":
        return cls(
            key=data["key"],
            label=data["label"],
            value=data.get("value"),
            weight=data["weight"],
            explanation=data.get("explanation", ""),
            available=bool(data.get("available", False)),
        )


@dataclass(frozen=True)
class RailItem:
    """One serve-ready rail slot -- entity + score + why (per-component
    breakdown, for the Inspector, E3.4) + display metadata (best-effort;
    `title`/`name` are for a hand-check or a FE with no other lookup, not
    part of the ranking decision)."""

    entity_type: str  # "place" | "article"
    entity_id: int
    rail: str
    position: int  # 1-indexed final serve slot -- the beacon's data-nowb-position
    score: float
    components: list[ComponentScoreOut]
    title: str | None = None
    slug: str | None = None
    is_paid: bool = False

    def as_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "rail": self.rail,
            "position": self.position,
            "score": self.score,
            "components": [c.as_dict() for c in self.components],
            "title": self.title,
            "slug": self.slug,
            "is_paid": self.is_paid,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RailItem":
        return cls(
            entity_type=data["entity_type"],
            entity_id=int(data["entity_id"]),
            rail=data["rail"],
            position=int(data["position"]),
            score=float(data["score"]),
            components=[ComponentScoreOut.from_dict(c) for c in data.get("components", [])],
            title=data.get("title"),
            slug=data.get("slug"),
            is_paid=bool(data.get("is_paid", False)),
        )


@dataclass(frozen=True)
class RailResult:
    """One rail's full, self-explaining output -- ARCHITECTURE.md Sec.8.F
    "record the rung reached" + Sec.17 "which fallback rung each rail
    landed on", both satisfied by `rung_name`/`rung_index` living on every
    `RailResult`, cached or fresh, never only in a log line."""

    rail: str
    items: list[RailItem]
    rung_name: str
    rung_index: int
    rungs_evaluated: list[str]
    pool_size: int  # candidates considered before diversify/truncation
    subject_type: str | None
    weights_source: str
    unvalidated_reason: str | None = None  # non-None -> this result is real-data structurally empty/limited; see field docstring below
    # `unvalidated_reason`: plain-language note for why this rail cannot
    # prove itself against real content today (F50/F27) -- e.g. "no active
    # places exist yet (F27)" -- `None` when the rail ran against real,
    # unaugmented data end to end. Never silently blank: a rail that is
    # empty for a real, honest reason says so in the response, rather than
    # looking identical to a rail that is empty because nothing matched.

    def as_dict(self) -> dict:
        return {
            "rail": self.rail,
            "items": [i.as_dict() for i in self.items],
            "rung_name": self.rung_name,
            "rung_index": self.rung_index,
            "rungs_evaluated": self.rungs_evaluated,
            "pool_size": self.pool_size,
            "subject_type": self.subject_type,
            "weights_source": self.weights_source,
            "unvalidated_reason": self.unvalidated_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RailResult":
        return cls(
            rail=data["rail"],
            items=[RailItem.from_dict(i) for i in data.get("items", [])],
            rung_name=data["rung_name"],
            rung_index=int(data["rung_index"]),
            rungs_evaluated=list(data.get("rungs_evaluated", [])),
            pool_size=int(data.get("pool_size", 0)),
            subject_type=data.get("subject_type"),
            weights_source=data.get("weights_source", "unknown"),
            unvalidated_reason=data.get("unvalidated_reason"),
        )


@dataclass(frozen=True)
class RailTiming:
    subject_ms: float
    row1_ms: float
    row2_ms: float
    row3_ms: float
    total_ms: float


@dataclass(frozen=True)
class RailsBundle:
    """`GET /v1/{site}/articles/{id}/rails`'s full payload, one level
    above the wire (the API's Pydantic schema maps this 1:1, per
    `app/domain/rails/schemas.py`)."""

    article_id: int
    segment: str
    rails: dict[str, RailResult]
    cache_hit: bool
    computed_at: datetime
    timing: RailTiming | None = None  # None on a cache hit that skipped recomputation entirely
    synthetic_overlay: bool = False
