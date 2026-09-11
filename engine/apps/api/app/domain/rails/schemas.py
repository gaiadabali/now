"""Pydantic response models for `GET /v1/{site}/articles/{id}/rails`
(ARCHITECTURE.md §16). Field-for-field mirror of `now_rails.models`'
dataclasses -- this module owns no ranking logic, only the wire shape.

`rail` and `position` appear on every item deliberately: the beacon
contract (`engine/packages/beacon`) requires both on every
`impression()` call (`data-nowb-rail`/`data-nowb-position` attributes),
and per §10 "without them stages 3-4 of the ML roadmap are crippled" --
this is the one response shape in the whole API where omitting either
field would silently break impression logging downstream.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ComponentScoreOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    value: float | None
    weight: float
    explanation: str
    available: bool


class RailItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_type: str = Field(description="'place' | 'article'")
    entity_id: int
    rail: str = Field(description="Beacon data-nowb-rail value for this card.")
    position: int = Field(description="1-indexed slot -- beacon data-nowb-position value.")
    score: float
    components: list[ComponentScoreOut]
    title: str | None = None
    slug: str | None = None
    is_paid: bool = False


class RailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rail: str
    items: list[RailItemOut]
    rung_name: str = Field(description="Fallback rung reached (ARCHITECTURE.md §8.F) -- Inspector-facing.")
    rung_index: int
    rungs_evaluated: list[str]
    pool_size: int
    subject_type: str | None
    weights_source: str
    unvalidated_reason: str | None = Field(
        default=None,
        description="Non-null when this rail could not be proven against real content today (F50/F27) -- see PROGRESS.md.",
    )


class CacheInfoOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    hit: bool
    computed_at: datetime


class RailsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    article_id: int
    segment: str
    rails: dict[str, RailOut]
    cache: CacheInfoOut
    synthetic_overlay: bool = Field(
        description="True only for an explicit debug/hand-check request -- never for a real reader, and never cached."
    )
