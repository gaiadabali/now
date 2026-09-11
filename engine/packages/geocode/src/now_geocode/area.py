"""Area-term fallback (ARCHITECTURE.md §8 Row 2 / §15): every place gets a
node from the seeded location tree even when precise geo is unresolved.
Text matching (address/venue-name/city mentioning a known area) is tried
before the geometric nearest-centroid fallback, because a resolved
coordinate is often the *centroid of a whole city* (see quality.py) and a
literal "Kemang" in the address is more specific than "6.26km from the
Kemang centroid" derived from a geocode that landed on the Jakarta
centroid.

Ladder (mirrors §8's fallback-ladder spirit, applied to one field):
  1. text match on address                  -> "text_match", conf 0.9
  2. text match on venue name                -> "text_match", conf 0.75
  3. text match on city/province             -> "text_match", conf 0.6
  4. geometric nearest centroid (<=60km)      -> "geometric_nearest", conf decays with distance
  5. `country` field says non-Indonesia       -> "international_fallback" -> "international", conf 0.5
  6. no signal at all                        -> "country_fallback" -> "indonesia", conf 0.15

Rung 6's default is "indonesia", not "international": every row in this
corpus's inputs (`venues.jsonl`, `geo.jsonl`) is either explicitly
`country: "Indonesia"` or has no `country` field at all — this is a
NOW! Jakarta/Bali archive, so total absence of signal is far more likely
"metadata wasn't captured" than "this is a foreign venue". `international`
is reserved for an explicit non-Indonesia `country` value, which does not
occur in the current inputs but may once E2.3 hands this pipeline venue
names pulled from World Traveller / Travel category articles.
"""

from __future__ import annotations

from now_geocode.models import AreaAssignment, PlaceCandidate
from now_geocode.terms import LocationTree
from now_geocode.textnorm import normalize_name


def assign_area(
    candidate: PlaceCandidate,
    tree: LocationTree,
    resolved_lat: float | None,
    resolved_lng: float | None,
) -> AreaAssignment:
    if candidate.address:
        slug = tree.match_text(candidate.address)
        if slug:
            return AreaAssignment(slug, tree.label_of(slug), "text_match", 0.9)

    slug = tree.match_text(candidate.name)
    if slug:
        return AreaAssignment(slug, tree.label_of(slug), "text_match", 0.75)

    slug = tree.match_text(candidate.city, candidate.province)
    if slug:
        return AreaAssignment(slug, tree.label_of(slug), "text_match", 0.6)

    if resolved_lat is not None and resolved_lng is not None:
        nearest = tree.nearest(resolved_lat, resolved_lng, max_km=60.0)
        if nearest:
            nearest_slug, distance_km = nearest
            # Linear decay: 0km -> 0.85, 60km -> 0.35. Never above the
            # ceiling of a real text match, since a nearby centroid is
            # still a guess about which neighbourhood, not a citation.
            confidence = max(0.35, 0.85 - (distance_km / 60.0) * 0.5)
            return AreaAssignment(nearest_slug, tree.label_of(nearest_slug), "geometric_nearest", confidence, distance_km)

    if candidate.country and normalize_name(candidate.country) != "indonesia":
        return AreaAssignment("international", tree.label_of("international"), "international_fallback", 0.5)

    return AreaAssignment("indonesia", tree.label_of("indonesia"), "country_fallback", 0.15)
