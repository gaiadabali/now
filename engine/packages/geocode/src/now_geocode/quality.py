"""Quality gates (ARCHITECTURE.md E2.5 deliverable #4):

- out-of-Indonesia bounding box -> rejected and flagged (Jakarta has
  same-named streets worldwide; a geocoder with a weak/absent country
  bias can return a real result for the wrong hemisphere)
- duplicate coordinates across *distinct* places -> flagged (geocoders
  collapse a vague/incomplete address onto a city centroid — several
  unrelated venues all landing on exactly the same point is the
  signature, not a coincidence)

Neither gate silently drops a row: rejection sets `Status.REJECTED` and
strips the coordinate from anything a nearby-radius query would read,
but the row still ships in `geocoded_places.jsonl` with the flag and the
raw rejected lat/lng preserved in `raw_lat`/`raw_lng` for audit.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

# Indonesia's extent is roughly 6.08 N - 11.01 S, 94.97 E - 141.02 E
# (Sabang to Merauke). Padded by ~0.5 degree (~55km) so a real coastal or
# border result isn't clipped by an overly tight box.
INDONESIA_BBOX = {"lat_min": -11.5, "lat_max": 6.5, "lng_min": 94.5, "lng_max": 141.5}


def in_indonesia_bbox(lat: float, lng: float) -> bool:
    return (
        INDONESIA_BBOX["lat_min"] <= lat <= INDONESIA_BBOX["lat_max"]
        and INDONESIA_BBOX["lng_min"] <= lng <= INDONESIA_BBOX["lng_max"]
    )


@dataclass
class DuplicateGroup:
    lat: float
    lng: float
    place_keys: list[str]
    names: list[str]


def find_duplicate_centroids(
    resolved: list[tuple[str, str, float, float, str]], precision: int = 5
) -> list[DuplicateGroup]:
    """`resolved` is (place_key, name, lat, lng, source) for every row with
    coordinates that passed the bbox gate. Flags groups of >=2 *distinct*
    place_keys sharing a coordinate rounded to `precision` decimals
    (~1.1m at 5dp) — tight enough that it's not two genuinely nearby but
    different venues, loose enough to catch a geocoder's literal repeat.

    `source == "existing_coordinates"` rows are excluded from triggering
    a flag on their own: those are free-seed points already merged by
    name in dedupe.py, so a real repeat there (two different post IDs
    pointing at one venue) is expected and not a geocoder artifact. A
    provider-sourced duplicate landing exactly on an existing-coordinates
    point (or on another provider result) still flags.
    """

    groups: dict[tuple[float, float], list[tuple[str, str, str]]] = defaultdict(list)
    for place_key, name, lat, lng, source in resolved:
        groups[(round(lat, precision), round(lng, precision))].append((place_key, name, source))

    out: list[DuplicateGroup] = []
    for (lat, lng), members in groups.items():
        distinct_keys = {m[0] for m in members}
        if len(distinct_keys) < 2:
            continue
        non_seed = [m for m in members if m[2] != "existing_coordinates"]
        if not non_seed:
            continue
        out.append(
            DuplicateGroup(
                lat=lat,
                lng=lng,
                place_keys=sorted(distinct_keys),
                names=sorted({m[1] for m in members}),
            )
        )
    return out
