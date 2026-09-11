"""Wires `hard.py` (SQL) + `ladder.py` (orchestration) into a concrete,
runnable fallback ladder for the one rail shape this package can fully
own end-to-end: **Row 2 Nearby** (ARCHITECTURE.md Sec.7 -- "Geo: within
radius (hard)"), which is exactly a `places` hard-filter query with a
radius parameter the ladder widens. Row 1 (Complementary) and Row 3
(Similar) need semantic/covisitation ranking this package does not own
(E3.3 blender, E3.5-3.7 rails) -- `build_nearby_fetch_fn` is written so
those rails can reuse the identical pattern: wrap their own retrieval
call in a `FetchFn`, hand it to `now_filters.ladder.run_ladder` with
their own `RungSpec` sequence, and get rung tracking + the defensive
competitor/status re-check for free. See README "Notes for E3.3 / E3.5-3.7".

**Area escalation caveat**: `places.area_term` is a single flat enum
(ARCHITECTURE.md Sec.5) -- there is no `district`/`city` parent column in
this database (the real area->district->city hierarchy lives in the
*platform* DB's `terms.parent_id`, a second database this single-DB-scoped
package does not reach, matching now-search's precedent). This
implementation therefore treats `RungSpec.area_level="area"` as "constrain
to the subject's own `area_term`" and both `"district"` and `"city"` as
"drop the area constraint entirely" -- a real widening (fewer results
excluded) even without a true intermediate district tier. Flagged as a
known simplification, not silently glossed over.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from now_filters.hard import build_places_hard_filter_sql, fetch_places_hard_filtered
from now_filters.ladder import LadderRun, run_ladder
from now_filters.models import DEFAULT_LADDER, Candidate, RungSpec
from now_filters.type_relations import TypeRelation


@dataclass(frozen=True)
class NearbySubject:
    place_id: int | None
    type: str | None
    lat: float | None
    lng: float | None
    area_term: str | None


def build_nearby_fetch_fn(
    conn: Connection,
    subject: NearbySubject,
    relations: dict[str, TypeRelation],
    *,
    places_table: str = "public.places",
):
    def _fetch(rung: RungSpec) -> list[Candidate]:
        area_terms = [subject.area_term] if (rung.area_level == "area" and subject.area_term) else None
        query = build_places_hard_filter_sql(
            subject_type=subject.type,
            relations=relations,
            exclude_self_id=subject.place_id,
            area_terms=area_terms,
            center_lat=subject.lat,
            center_lng=subject.lng,
            radius_m=rung.radius_m,
            editorial_fallback=rung.editorial_fallback,
            places_table=places_table,
        )
        return fetch_places_hard_filtered(conn, query)

    return _fetch


def run_nearby_ladder(
    conn: Connection,
    subject: NearbySubject,
    relations: dict[str, TypeRelation],
    *,
    slots_needed: int,
    ladder: tuple[RungSpec, ...] = DEFAULT_LADDER,
    places_table: str = "public.places",
) -> LadderRun:
    fetch_fn = build_nearby_fetch_fn(conn, subject, relations, places_table=places_table)
    return run_ladder(
        fetch_fn,
        subject_type=subject.type,
        relations=relations,
        slots_needed=slots_needed,
        ladder=ladder,
    )
