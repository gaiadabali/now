"""Shared types for the filter pipeline. Kept dependency-light (dataclasses
+ stdlib) so `diversity.py`/`contextual.py`/`soft.py`/`ladder.py` stay
unit-testable without a DB connection -- only `hard.py` (and the
`fetch_*` helpers that populate a `Candidate`) touch Postgres.

`Candidate` is intentionally the same shape whether the underlying row is
`public.places` or `public.articles`: both compete for the same rail slots
(ARCHITECTURE.md Sec.7 "The three rails"), and every filter class in Sec.8
after the SQL hard-filter stage (contextual/soft/diversity) operates on
this shape, not on raw DB rows, per Sec.8.G ("per-user checks in memory
over ~40 rows")."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EntityType(str, Enum):
    ARTICLE = "article"
    PLACE = "place"


@dataclass(frozen=True)
class Candidate:
    """One rail candidate, enriched enough for every filter stage after
    the SQL hard filter to run entirely in memory.

    `type` is the L1 taxonomy type (ARCHITECTURE.md Sec.4) driving
    competitor exclusion -- for a place, `public.places.type`; for an
    article, `public.articles.primary_type`. `status` is the
    place/article lifecycle status (`places.status` /
    `articles._status`) -- F27's enforcement point reads this field.
    """

    entity_type: str  # "place" | "article" -- see EntityType
    entity_id: int
    type: str | None = None
    subtype: str | None = None
    status: str | None = None
    area_term: str | None = None
    org_id: str | None = None
    price_band: str | None = None
    format: str | None = None
    series_key: str | None = None
    quality_score: float | None = None
    lat: float | None = None
    lng: float | None = None
    distance_m: float | None = None  # populated by a radius query (Row 2); None otherwise
    amenities: frozenset[str] = field(default_factory=frozenset)
    hours: tuple[tuple[str, str, str], ...] = ()  # (day, opens 'HH:MM', closes 'HH:MM')
    ends_at: datetime | None = None  # events only -- expiry hard filter
    is_paid: bool = False  # active `paid`-tier partnership -- Sec.8.D "max 1 paid per rail"
    published_at: datetime | None = None  # freshness-cutoff rung input

    @property
    def key(self) -> tuple[str, int]:
        return (self.entity_type, self.entity_id)


@dataclass(frozen=True)
class ActiveFacetFilters:
    """Reader-chosen self-filters (ARCHITECTURE.md Sec.9) plus the two
    user-chosen signals Sec.8.C permits as HARD filters -- explicit
    thumbs-down and user-muted facets. Everything else in personalization
    is soft (down-weight only); this dataclass is deliberately the only
    place a "hard-filter from personalization" input can enter the
    pipeline, so that invariant is enforced by the type, not just by
    convention."""

    thumbs_down_ids: frozenset[tuple[str, int]] = field(default_factory=frozenset)
    muted_facet_values: frozenset[str] = field(default_factory=frozenset)  # e.g. "cuisine:padang"
    candidate_facet_values: dict[tuple[str, int], frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionState:
    """Contextual inputs (Sec.8.B). All resolved by the caller (beacon /
    itinerary tables live outside this package's single-DB scope, matching
    now-search's precedent of not reaching into a second database) and
    handed in as plain data -- this package only applies the predicates."""

    already_read: dict[tuple[str, int], datetime] = field(default_factory=dict)  # for decay
    already_shown_this_session: frozenset[tuple[str, int]] = field(default_factory=frozenset)
    already_in_itinerary: frozenset[tuple[str, int]] = field(default_factory=frozenset)
    trip_start: datetime | None = None
    trip_end: datetime | None = None
    party_kids: bool = False
    party_accessibility: bool = False
    party_halal: bool = False
    party_vegetarian: bool = False
    party_budget_ceiling: str | None = None  # one of places.price_band
    now: datetime | None = None  # injectable for tests; defaults to utcnow()
    open_at: datetime | None = None  # if set, filter to venues open at this instant


@dataclass(frozen=True)
class RungSpec:
    """One fallback-ladder rung (ARCHITECTURE.md Sec.8.F). Rungs relax
    successively more of the SQL hard-filter's optional knobs; the
    invariant filters (status='active'/'published', self, competitor,
    expiry, closed-venue) are NEVER parameters here -- they are not
    relaxable at any rung, enforced by `hard.py` unconditionally."""

    name: str
    radius_m: float | None = None  # None = no radius constraint (area-based instead)
    require_open_now: bool = False
    area_level: str = "area"  # "area" | "district" | "city"
    apply_freshness_cutoff: bool = True
    editorial_fallback: bool = False


DEFAULT_LADDER: tuple[RungSpec, ...] = (
    RungSpec(name="strict", radius_m=2000, require_open_now=True, area_level="area", apply_freshness_cutoff=True),
    RungSpec(name="widen_radius_5km", radius_m=5000, require_open_now=True, area_level="area", apply_freshness_cutoff=True),
    RungSpec(name="widen_radius_15km", radius_m=15000, require_open_now=True, area_level="area", apply_freshness_cutoff=True),
    RungSpec(name="drop_open_now", radius_m=15000, require_open_now=False, area_level="area", apply_freshness_cutoff=True),
    RungSpec(name="area_to_district", radius_m=None, require_open_now=False, area_level="district", apply_freshness_cutoff=True),
    RungSpec(name="district_to_city", radius_m=None, require_open_now=False, area_level="city", apply_freshness_cutoff=True),
    RungSpec(name="drop_freshness", radius_m=None, require_open_now=False, area_level="city", apply_freshness_cutoff=False),
    RungSpec(name="editorial_fallback", radius_m=None, require_open_now=False, area_level="city", apply_freshness_cutoff=False, editorial_fallback=True),
)


@dataclass
class RungResult:
    candidates: list[Candidate]
    rung_index: int
    rung_name: str
    slots_requested: int

    @property
    def starved(self) -> bool:
        return len(self.candidates) < self.slots_requested


@dataclass(frozen=True)
class FilterExplain:
    """Query text + params for a hard-filter SQL build, returned alongside
    results so callers (and tests -- Sec.8.G "show the query plan") can
    run EXPLAIN ANALYZE on exactly what was executed."""

    sql: str
    params: dict
