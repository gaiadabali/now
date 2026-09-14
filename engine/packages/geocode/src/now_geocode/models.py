"""Typed shapes shared across the pipeline.

`PlaceCandidate` is the normalized input unit — one row survives from
either `venues.jsonl` (tribe_venue, structured address) or `geo.jsonl`
(MapPress/ACF `google_map`, already has coordinates), *after* the
name-based merge in `dedupe.py` folds duplicate sightings of the same
real-world place into one candidate with multiple `source_refs`.

`ProviderResult` is what a `GeocodeProvider` returns for one lookup —
never persisted directly; the ladder wraps it into a `LadderOutcome`
that records *which rung* produced it, which is what `GeocodedPlace`
(the `geocoded_places.jsonl` row) is built from.

Nothing in this module talks to a database or an HTTP client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceKind(str, Enum):
    """Where a `PlaceCandidate` (or one of its merged sightings) came from."""

    TRIBE_VENUE = "tribe_venue"
    MAPPRESS = "mappress"
    GOOGLE_MAP = "google_map"


class Rung(str, Enum):
    """The strict resolution ladder, in order. `Rung.value` is stored on
    every output row as `source` — never skipped, never guessed past.

    `MANUAL_OVERRIDE` is rung 0: a human looked the venue up and cited
    where the coordinate came from. It outranks the free seed because the
    reason `jakarta/site/place-overrides.jsonl` exists is that some seed
    and geocode answers are demonstrably wrong — see `overrides.py`.

    NB for consumers: `source` gained `manual_override` on 2026-09-14.
    Anything switching on this value needs that arm."""

    MANUAL_OVERRIDE = "manual_override"
    EXISTING_COORDINATES = "existing_coordinates"
    ADDRESS_GEOCODE = "address_geocode"
    NAME_PLACE_SEARCH = "name_place_search"
    UNRESOLVED = "unresolved"


class Status(str, Enum):
    RESOLVED = "resolved"
    RESOLVED_SYNTHETIC = "resolved_synthetic"  # offline/dry-run provider only — never a real deliverable row
    REJECTED = "rejected"  # a geocode came back but failed a quality gate (out of bounds)
    UNRESOLVED = "unresolved"  # nothing usable found anywhere on the ladder — review queue, not a guess


@dataclass(frozen=True)
class SourceRef:
    """Traceability back to the WP row(s) a merged candidate came from.
    `wp_id` is `None` for a MapPress map with no linked post (rare, the
    map's own center with an empty `mappress_posts` join)."""

    kind: SourceKind
    wp_id: int | None
    map_id: int | None = None


@dataclass
class PlaceCandidate:
    """One place, after dedup, before resolution."""

    key: str  # stable hash of normalized name (+address when present) — see dedupe.candidate_key
    name: str
    address: str | None
    city: str | None
    province: str | None
    country: str | None
    existing_lat: float | None  # already known, free (rung 1) — geo.jsonl only
    existing_lng: float | None
    existing_google_place_id: str | None
    source_refs: list[SourceRef] = field(default_factory=list)
    status_hint: str | None = None  # e.g. "draft" for a tribe_venue not published — carried through as a flag, not a silent drop


@dataclass
class ProviderResult:
    """What a `GeocodeProvider` call returns. `is_synthetic` is the load
    -bearing field: `True` only ever comes from `OfflineProvider`, and the
    pipeline refuses to let a synthetic result masquerade as `resolved`."""

    lat: float
    lng: float
    formatted_address: str | None
    google_place_id: str | None
    location_type: str | None  # e.g. ROOFTOP / RANGE_INTERPOLATED / GEOMETRIC_CENTER / APPROXIMATE / place_search
    confidence: float
    provider: str
    is_synthetic: bool = False
    raw: dict | None = None


@dataclass
class AreaAssignment:
    slug: str
    label: str
    method: str  # "text_match" | "geometric_nearest" | "country_fallback" | "international_fallback"
    confidence: float
    distance_km: float | None = None


@dataclass
class GeocodedPlace:
    """One `geocoded_places.jsonl` row — the E2.3/E1.8 contract."""

    place_key: str
    name: str
    slug: str
    address: str | None
    city: str | None
    province: str | None
    country: str | None
    lat: float | None
    lng: float | None
    status: Status
    source: Rung
    confidence: float
    google_place_id: str | None
    area_term: str | None
    area_term_source: str | None
    area_term_confidence: float | None
    flags: list[str]
    source_refs: list[SourceRef]
    review_reason: str | None
    location_type: str | None = None

    def to_json(self) -> dict:
        return {
            "place_key": self.place_key,
            "name": self.name,
            "slug": self.slug,
            "address": self.address,
            "city": self.city,
            "province": self.province,
            "country": self.country,
            "lat": self.lat,
            "lng": self.lng,
            "status": self.status.value,
            "source": self.source.value,
            "confidence": round(self.confidence, 3),
            "google_place_id": self.google_place_id,
            "area_term": self.area_term,
            "area_term_source": self.area_term_source,
            "area_term_confidence": (
                round(self.area_term_confidence, 3) if self.area_term_confidence is not None else None
            ),
            "location_type": self.location_type,
            "flags": self.flags,
            "source_refs": [
                {"kind": r.kind.value, "wp_id": r.wp_id, "map_id": r.map_id} for r in self.source_refs
            ],
            "review_reason": self.review_reason,
        }
