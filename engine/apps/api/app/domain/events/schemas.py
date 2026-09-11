"""Pydantic models for the beacon wire contract.

Field names and shapes here are a direct mirror of
`engine/packages/beacon/README.md`'s "Payload contract" section -- do not
rename or drop a field without checking that document first, it is the
beacon's authoritative spec (E0.4) and this endpoint is its only consumer.

Two deliberate divergences from a naive 1:1 mapping of the beacon's JS
objects, both explained in `app/domain/events/normalize.py`:

1. `entity_id`/`anon_id`/`session_id`/`user_id` are typed `str` here, not
   `uuid`, even though `anon_id`/`session_id` are `uuid NOT NULL` and
   `user_id` is `uuid NULL` on the destination Postgres columns.
   `anon_id`/`session_id` are genuine UUID strings as of the beacon's
   `crypto.randomUUID()` change (decision C4) but are still validated as
   plain strings at this layer -- `normalize.parse_uuid` does the actual
   UUID check, once, in one place, rather than duplicating it into a
   Pydantic validator here.
   `entity_id` is deliberately different: as of migration 0007 (F66) the
   destination columns (`interactions.entity_id text NULL`,
   `impressions.entity_id text NOT NULL`) are `text`, not `uuid` -- a real
   entity reference is a Payload integer-serial PK
   (`public.articles.id`/`public.places.id`/`public.events.id`) carried
   verbatim as a numeric string, never a UUID. `normalize.
   parse_native_entity_id` validates that shape. A malformed value in any
   of these four fields is still rejected before any database write; see
   `app/domain/events/service.py::write_events`.
2. There is no `query` or `target_url` field on `InteractionIn` -- the
   beacon still sends the search query as `entity_type="search_query"`,
   `entity_id=<query text>` (decision C1) and an untagged outbound link's
   href as `entity_type="url"`, `entity_id=<href>` (decision C4). Both are
   its own README's documented deviations pending first-class wire fields.
   `normalize.py` is where each gets pulled apart into
   `engine.interactions.query` / `.target_url` on write, leaving `entity_id`
   NULL for both cases.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The client batches at a 10-event flush trigger and queues up to 200 per
# array while the endpoint is unreachable (beacon README, "Transport"): a
# legitimate batch tops out around 210. Anything past that is not a real
# beacon batch -- reject it rather than accepting unbounded arrays.
MAX_EVENTS_PER_ARRAY = 210

# Generous but bounded -- long enough for a real-world URL (outbound clicks
# with no `data-nowb-entity` carry the raw `href`) without accepting
# arbitrary multi-KB strings per event.
_MAX_TEXT_FIELD = 2048

INTERACTION_KINDS = (
    "view",
    "scroll",
    "dwell",
    "click",
    "outbound",
    "search",
    "exit",
    "thumbs_down",
)


class InteractionIn(BaseModel):
    """One `engine.interactions` row as the beacon sends it."""

    model_config = ConfigDict(extra="forbid")

    anon_id: str = Field(min_length=1, max_length=256)
    user_id: str | None = Field(default=None, max_length=256)
    session_id: str = Field(min_length=1, max_length=256)
    entity_type: str = Field(min_length=1, max_length=128)
    entity_id: str = Field(min_length=1, max_length=_MAX_TEXT_FIELD)
    kind: Literal[
        "view", "scroll", "dwell", "click", "outbound", "search", "exit", "thumbs_down"
    ]
    surface: str = Field(min_length=1, max_length=128)
    rail: str | None = Field(default=None, max_length=128)
    position: int | None = Field(default=None, ge=0)
    dwell_ms: int | None = Field(default=None, ge=0)
    scroll_pct: float | None = Field(default=None, ge=0)
    referrer: str | None = Field(default=None, max_length=_MAX_TEXT_FIELD)
    utm: dict[str, str] | None = None
    device: str | None = Field(default=None, max_length=32)
    ts: int = Field(description="client epoch ms at event time")


class ImpressionIn(BaseModel):
    """One `engine.impressions` row. No optional fields -- the beacon
    refuses to enqueue an impression missing `entityId`/`rail`/`position`
    client-side (beacon README), so the server holds the same line."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=256)
    anon_id: str = Field(min_length=1, max_length=256)
    surface: str = Field(min_length=1, max_length=128)
    rail: str = Field(min_length=1, max_length=128)
    entity_id: str = Field(min_length=1, max_length=_MAX_TEXT_FIELD)
    position: int = Field(ge=0)
    ts: int = Field(description="client epoch ms at event time")


class EventsBatchIn(BaseModel):
    """`POST /v1/{site}/events` request body. Either array may be empty."""

    model_config = ConfigDict(extra="forbid")

    interactions: list[InteractionIn] = Field(default_factory=list, max_length=MAX_EVENTS_PER_ARRAY)
    impressions: list[ImpressionIn] = Field(default_factory=list, max_length=MAX_EVENTS_PER_ARRAY)
