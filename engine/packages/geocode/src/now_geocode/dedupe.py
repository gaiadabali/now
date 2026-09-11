"""Merges `venues.jsonl` (tribe_venue, structured address) and `geo.jsonl`
(MapPress/`google_map`, already-coordinated POIs) into one list of
`PlaceCandidate`.

**Why merge by name, not by `wp_id`**: `geo.jsonl`'s `wp_id` is the
WordPress post that *embedded* the map (a page, an event, sometimes a
post outside the published-articles set) — not a venue identity. It does
not overlap `venues.jsonl`'s `wp_id` space at all (verified against the
real extracted files: 0 of 177 venue wp_ids appear in geo.jsonl's 54
distinct wp_ids). Treat each `geo.jsonl` row as an independent POI
candidate in its own right (per ARCHITECTURE.md §15's "free seed"
framing), then fold it into a `venues.jsonl` candidate when the
normalized *name* matches — on the real data this catches 6 real
overlaps (e.g. "Potato Head Beach Club", "Padma Resort Ubud") with no
false positives found on manual inspection.

At this corpus's scale (73 geo rows + 177 venues) a normalized-name
merge is deliberately simple rather than a fuzzy-matching library: every
merge is logged in `MergeReport.merges` so a human can audit the exact
list, and any group that merges rows with **conflicting** city/province
(a possible false-positive merge, e.g. two different "Warung Bali"s) is
flagged in `MergeReport.conflicts` rather than silently accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from now_geocode.models import PlaceCandidate, SourceKind, SourceRef
from now_geocode.textnorm import candidate_key, normalize_name


@dataclass
class MergeReport:
    merges: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    dropped_draft_venues: int = 0
    total_venue_rows: int = 0
    total_geo_rows: int = 0


def _first(*values: str | None) -> str | None:
    for v in values:
        if v:
            v = v.strip()
            if v:
                return v
    return None


def build_candidates(
    venue_rows: list[dict], geo_rows: list[dict], report: MergeReport | None = None
) -> list[PlaceCandidate]:
    if report is None:
        report = MergeReport()
    report.total_venue_rows = len(venue_rows)
    report.total_geo_rows = len(geo_rows)

    # Deterministic ordering regardless of file line order, so key
    # assignment / merge decisions are a pure function of content, not of
    # iteration order — required for idempotent re-runs.
    venue_rows = sorted(venue_rows, key=lambda r: r.get("wp_id") or 0)
    geo_rows = sorted(geo_rows, key=lambda r: (r.get("wp_id") or 0, r.get("map_id") or 0, r.get("poi_index") or 0))

    buckets: dict[str, list[dict]] = {}
    order: list[str] = []

    def bucket_for(name: str) -> list[dict]:
        norm = normalize_name(name)
        if norm not in buckets:
            buckets[norm] = []
            order.append(norm)
        return buckets[norm]

    for row in venue_rows:
        name = row.get("name") or ""
        if not normalize_name(name):
            continue
        entry = {"kind": "venue", "row": row}
        bucket_for(name).append(entry)

    for row in geo_rows:
        title = row.get("title") or ""
        if not normalize_name(title):
            continue
        entry = {"kind": "geo", "row": row}
        bucket_for(title).append(entry)

    candidates: list[PlaceCandidate] = []

    for norm in order:
        entries = buckets[norm]
        venue_entries = [e for e in entries if e["kind"] == "venue"]
        geo_entries = [e for e in entries if e["kind"] == "geo"]

        if len(entries) > 1:
            report.merges.append(
                {
                    "normalized_name": norm,
                    "venue_wp_ids": [e["row"]["wp_id"] for e in venue_entries],
                    "geo_wp_ids": [e["row"]["wp_id"] for e in geo_entries],
                }
            )
            cities = {
                normalize_name(e["row"].get("city")) for e in venue_entries if e["row"].get("city")
            }
            if len(cities) > 1:
                report.conflicts.append({"normalized_name": norm, "distinct_cities": sorted(cities)})

        display_name = _first(*(e["row"].get("name") or e["row"].get("title") for e in entries)) or norm

        address = _first(*(e["row"].get("address") for e in entries))
        city = _first(*(e["row"].get("city") for e in venue_entries))
        province = _first(*(e["row"].get("province") or e["row"].get("state") for e in venue_entries))
        country = _first(*(e["row"].get("country") for e in venue_entries))

        existing_lat = existing_lng = existing_place_id = None
        for e in geo_entries:
            row = e["row"]
            if row.get("lat") is not None and row.get("lng") is not None:
                existing_lat, existing_lng = row["lat"], row["lng"]
                existing_place_id = row.get("place_id")
                break

        status_hint = None
        source_refs: list[SourceRef] = []
        dropped_draft = False
        for e in venue_entries:
            row = e["row"]
            if row.get("status") != "publish":
                dropped_draft = True
                status_hint = row.get("status")
            source_refs.append(SourceRef(kind=SourceKind.TRIBE_VENUE, wp_id=row["wp_id"]))
        if dropped_draft:
            report.dropped_draft_venues += 1
        for e in geo_entries:
            row = e["row"]
            kind = SourceKind.GOOGLE_MAP if row["source"] == "google_map" else SourceKind.MAPPRESS
            source_refs.append(SourceRef(kind=kind, wp_id=row.get("wp_id"), map_id=row.get("map_id")))

        key = candidate_key(display_name, address)
        candidates.append(
            PlaceCandidate(
                key=key,
                name=display_name,
                address=address,
                city=city,
                province=province,
                country=country,
                existing_lat=existing_lat,
                existing_lng=existing_lng,
                existing_google_place_id=existing_place_id,
                source_refs=source_refs,
                status_hint=status_hint,
            )
        )

    return candidates
