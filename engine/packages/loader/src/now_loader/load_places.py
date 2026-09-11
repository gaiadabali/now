"""`places` <- `venues.jsonl` (E1.1 contract: 177 `tribe_venue` rows — name,
slug, address, city, state, province, zip, country, phone, url,
thumbnail_id, date). No lat/lng, no category of any kind in the source —
ARCHITECTURE.md §6's geo-coverage finding holds for venues too (E2.5 is the
critical path; this loader cannot geocode).

**Schema conflict this ticket asks to be stated explicitly, not
worked around** (mirrors the 490-undated-events call the ticket
pre-authorizes): `places.type` and `places.subtype` are `NOT NULL` real
Postgres enums (confirmed against the live `now_jakarta` schema — see
`\\d places`). The ticket's instruction is "leave any facet field NULL;
E2.1/E2.3 fill it in" — for `articles.primary_type`/`format` that is
literally possible (nullable columns, because Articles supports Payload
drafts and required-field validation is deferred). `places` does NOT
support drafts (E1.6's `Places.ts` comment explains why: a Payload
`_status` enum collision), so Postgres enforces `type`/`subtype` as
mandatory on every row, draft or not. There is no NULL to fall back to,
and no legitimate signal in `venues.jsonl` to classify from (no category,
no type hint of any kind) — assigning a real business type here would be
exactly the "bake an unreviewed guess into the DB" the ticket says not to
do for articles.

Resolution taken (see final report for the full writeup and the
alternative considered): every venue-derived place is inserted with the
explicit **sentinel** `type = 'editorial'`, `subtype = 'city-guide'` --
chosen because it is the one pairing in the seeded taxonomy that carries
no commercial-exclusion meaning (`type_relations.editorial.exclude_same =
false` per ARCHITECTURE.md §4 — it can never wrongly assert a place is a
competitor to a real hotel/restaurant/bar) -- AND `status = 'pending_review'`
(not the column's own default `'active'`), so nothing downstream that
filters on `status = 'active'` will surface a mislabelled venue. Both are
loudly flagged in every row this loader writes (see `PLACEHOLDER_TYPE` /
`PLACEHOLDER_SUBTYPE` below) so `grep`ing this module tells you exactly
which rows need it. **E2.3 (place extraction + dedup) must overwrite these
before any venue-derived place goes live**; this loader does not consider
that its own job (E2.3 also owns dedup, which the ticket explicitly says
E1.8 must not attempt — see the duplicate-slug handling below).

`area_term` (nullable) is the one field this loader *does* fill from
venue data, because it's normalization, not classification: if
`slugify(venue.state or venue.province)` exactly matches a label already
in the live `enum_places_area_term` type (e.g. "Bali" -> "bali"), that
exact value is used. No fuzzy matching, no inference — an exact-match miss
just leaves it NULL.

Idempotency / dedup: `slug` is `UNIQUE`, but 7 of 177 venues in the source
share a slug with another venue (`red-carpet` x4, `timur-kitchen` x4,
`dava-steak-seafood` x2 — apparent genuine WP data duplication, not an
extraction bug). Per this ticket's explicit scope, **dedup is E2.3's job,
not this loader's** ("Dedup name variants... not auto-merged" is literally
E2.3's acceptance criterion) — so every venue row is preserved as its own
place rather than merged. Collisions are resolved deterministically by
appending `-{wp_id}` to every slug after the first (sorted by `wp_id`, so
reruns are stable), which keeps the natural-key upsert working without
silently dropping rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_loader.dbutil import enum_values
from now_loader.sources import iter_jsonl
from now_loader.textutil import slugify

PLACEHOLDER_TYPE = "editorial"
PLACEHOLDER_SUBTYPE = "city-guide"
PLACEHOLDER_STATUS = "pending_review"

_UPSERT = text(
    """
    INSERT INTO "public"."places"
        (name, slug, address, area_term, type, subtype, status, updated_at, created_at)
    VALUES
        (:name, :slug, :address, :area_term, :type, :subtype, :status, now(), now())
    ON CONFLICT (slug) DO UPDATE
       SET name = EXCLUDED.name,
           address = EXCLUDED.address,
           area_term = EXCLUDED.area_term,
           updated_at = now()
    RETURNING id
    """
)


@dataclass
class PlacesLoadResult:
    read: int = 0
    inserted_or_updated: int = 0
    slug_deduplicated: int = 0
    area_term_matched: int = 0
    area_term_unmatched: int = 0
    wp_id_to_place_id: dict[int, int] = field(default_factory=dict)


def _build_address(venue: dict) -> str | None:
    parts = [venue.get(k) for k in ("address", "city", "state", "province", "country")]
    parts = [p for p in parts if p]
    # de-duplicate consecutive identical parts (state == province is common in the source)
    deduped: list[str] = []
    for p in parts:
        if not deduped or deduped[-1] != p:
            deduped.append(p)
    return ", ".join(deduped) if deduped else None


def load_places(conn: Connection, venues_path: Path) -> PlacesLoadResult:
    result = PlacesLoadResult()
    valid_area_terms = enum_values(conn, "enum_places_area_term")

    venues = sorted(iter_jsonl(venues_path), key=lambda v: v["wp_id"])
    used_slugs: set[str] = set()

    for venue in venues:
        result.read += 1
        wp_id = venue["wp_id"]
        base_slug = venue.get("slug") or slugify(venue.get("name") or f"venue-{wp_id}")
        slug = base_slug
        if slug in used_slugs:
            slug = f"{base_slug}-{wp_id}"
            result.slug_deduplicated += 1
        used_slugs.add(slug)

        area_term = None
        for candidate_field in ("state", "province"):
            candidate = venue.get(candidate_field)
            if candidate:
                candidate_slug = slugify(candidate)
                if candidate_slug in valid_area_terms:
                    area_term = candidate_slug
                    break
        if area_term:
            result.area_term_matched += 1
        else:
            result.area_term_unmatched += 1

        place_id = conn.execute(
            _UPSERT,
            {
                "name": venue.get("name") or slug,
                "slug": slug,
                "address": _build_address(venue),
                "area_term": area_term,
                "type": PLACEHOLDER_TYPE,
                "subtype": PLACEHOLDER_SUBTYPE,
                "status": PLACEHOLDER_STATUS,
            },
        ).scalar_one()

        result.wp_id_to_place_id[wp_id] = place_id
        result.inserted_or_updated += 1

    return result
