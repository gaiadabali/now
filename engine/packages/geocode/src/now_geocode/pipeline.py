"""Top-level orchestration: `venues.jsonl` + `geo.jsonl` -> deduped
candidates -> ladder resolution (state-cached) -> area-term assignment ->
duplicate-centroid pass -> `geocoded_places.jsonl` rows + coverage stats.

`run()` is deliberately not a CLI concern — `cli.py` is a thin wrapper so
this stays testable as a plain function.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from now_geocode.dedupe import MergeReport, build_candidates
from now_geocode.ladder import resolve_candidate
from now_geocode.area import assign_area
from now_geocode.models import GeocodedPlace, PlaceCandidate, Rung, Status
from now_geocode.providers.base import GeocodeProvider
from now_geocode.quality import find_duplicate_centroids
from now_geocode.state import StateRecord, StateStore, now_iso
from now_geocode.terms import LocationTree, load_location_tree
from now_geocode.textnorm import slugify


@dataclass
class RunStats:
    total_candidates: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    by_area_source: dict[str, int] = field(default_factory=dict)
    confidence_buckets: dict[str, int] = field(default_factory=dict)  # "0.9-1.0" etc, resolved only
    flagged: dict[str, int] = field(default_factory=dict)
    resolved_from_cache: int = 0
    resolved_from_provider_calls: int = 0
    merge_report: MergeReport | None = None


def iter_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _confidence_bucket(confidence: float) -> str:
    if confidence <= 0:
        return "0.0"
    lo = int(confidence * 10) / 10
    hi = round(lo + 0.1, 1)
    return f"{lo:.1f}-{hi:.1f}"


def _unique_slug(name: str, used: set[str]) -> str:
    base = slugify(name)
    slug = base
    n = 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def run(
    venue_rows: list[dict],
    geo_rows: list[dict],
    *,
    provider: GeocodeProvider | None,
    state: StateStore | None = None,
    location_tree: LocationTree | None = None,
    allow_synthetic: bool = False,
) -> tuple[list[GeocodedPlace], RunStats]:
    tree = location_tree or load_location_tree()
    merge_report = MergeReport()
    candidates = build_candidates(venue_rows, geo_rows, merge_report)

    stats = RunStats(total_candidates=len(candidates), merge_report=merge_report)
    places: list[GeocodedPlace] = []
    used_slugs: set[str] = set()

    for candidate in candidates:
        cached = state.get(candidate.key) if state else None
        if cached is not None:
            stats.resolved_from_cache += 1
            outcome_rung = Rung(cached.rung)
            outcome_status = Status(cached.status)
            lat, lng = cached.lat, cached.lng
            google_place_id = cached.google_place_id
            confidence = cached.confidence
            location_type = cached.location_type
            flags: list[str] = []
            review_reason = cached.note
            # A synthetic point cached by an earlier --dry-run must never be
            # replayed into a real run. Both existing guardrails act on a
            # *fresh* provider call (ladder) or the output filename (CLI);
            # neither sees a cache hit, so a shared --state file across a
            # dry-run and a real build would otherwise smuggle a fabricated
            # coordinate into the real deliverable. Found by QA.2.
            if outcome_status is Status.RESOLVED_SYNTHETIC and not allow_synthetic:
                outcome_status = Status.UNRESOLVED
                lat = lng = None
                google_place_id = None
                confidence = 0.0
                location_type = None
                flags.append("discarded_synthetic_cache_hit")
                review_reason = (
                    "synthetic coordinate from a --dry-run cache was discarded "
                    "in a non-dry-run build"
                )
        else:
            outcome = resolve_candidate(candidate, provider, allow_synthetic=allow_synthetic)
            if provider is not None and outcome.rung != Rung.EXISTING_COORDINATES:
                stats.resolved_from_provider_calls += 1
            if state is not None:
                state.record(
                    StateRecord(
                        place_key=candidate.key,
                        final=outcome.retryable_error is None,
                        rung=outcome.rung.value,
                        status=outcome.status.value,
                        lat=outcome.lat,
                        lng=outcome.lng,
                        google_place_id=outcome.google_place_id,
                        confidence=outcome.confidence,
                        location_type=outcome.location_type,
                        note=outcome.review_reason,
                        attempted_at=now_iso(),
                    )
                )
            outcome_rung = outcome.rung
            outcome_status = outcome.status
            lat, lng = outcome.lat, outcome.lng
            google_place_id = outcome.google_place_id
            confidence = outcome.confidence
            location_type = outcome.location_type
            flags = list(outcome.flags)
            review_reason = outcome.review_reason

        area = assign_area(candidate, tree, lat, lng)

        # Candidate-level flag, independent of which rung resolved it (or
        # whether it resolved at all) — a draft tribe_venue's coordinates
        # or area term are still usable, but a human should know it was
        # never published on the source site.
        if candidate.status_hint and f"venue_status:{candidate.status_hint}" not in flags:
            flags.append(f"venue_status:{candidate.status_hint}")

        slug = _unique_slug(candidate.name, used_slugs)
        place = GeocodedPlace(
            place_key=candidate.key,
            name=candidate.name,
            slug=slug,
            address=candidate.address,
            city=candidate.city,
            province=candidate.province,
            country=candidate.country,
            lat=lat,
            lng=lng,
            status=outcome_status,
            source=outcome_rung,
            confidence=confidence,
            google_place_id=google_place_id,
            area_term=area.slug,
            area_term_source=area.method,
            area_term_confidence=area.confidence,
            location_type=location_type,
            flags=flags,
            source_refs=candidate.source_refs,
            review_reason=review_reason,
        )
        places.append(place)

    # Duplicate-centroid pass, across everything with a coordinate that
    # passed the bbox gate (resolved or resolved_synthetic).
    resolvable = [
        (p.place_key, p.name, p.lat, p.lng, p.source.value)
        for p in places
        if p.lat is not None and p.lng is not None and p.status in (Status.RESOLVED, Status.RESOLVED_SYNTHETIC)
    ]
    dup_groups = find_duplicate_centroids(resolvable)
    flagged_keys: dict[str, list[str]] = {}
    for group in dup_groups:
        for key in group.place_keys:
            others = [n for n in group.names]
            flagged_keys[key] = others

    for place in places:
        if place.place_key in flagged_keys:
            place.flags.append("duplicate_centroid")

    # Stats
    for p in places:
        stats.by_status[p.status.value] = stats.by_status.get(p.status.value, 0) + 1
        stats.by_source[p.source.value] = stats.by_source.get(p.source.value, 0) + 1
        stats.by_area_source[p.area_term_source or "none"] = stats.by_area_source.get(p.area_term_source or "none", 0) + 1
        if p.status in (Status.RESOLVED, Status.RESOLVED_SYNTHETIC):
            bucket = _confidence_bucket(p.confidence)
            stats.confidence_buckets[bucket] = stats.confidence_buckets.get(bucket, 0) + 1
        for flag in p.flags:
            stats.flagged[flag] = stats.flagged.get(flag, 0) + 1

    return places, stats
