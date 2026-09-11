"""Row 2 -- Nearby (ARCHITECTURE.md Sec.7): activities and points of
interest close by. **Radius is a hard filter** -- this is the one rail
`now_filters` was explicitly built to own end-to-end
(`now_filters.pipeline.run_nearby_ladder`, that module's own docstring:
"the one rail shape this package can fully own end-to-end"). This module
is deliberately thin: build a `NearbySubject` from the article's place
context, hand it to `run_nearby_ladder` for the radius-widening ladder +
rung tracking + defensive competitor/status re-check, then blend +
diversify the result -- no SQL of its own beyond what `now_filters.hard`
already builds.

**No embedder call on this path** -- `open_now` is applied as a *soft*
post-fetch down-weight (`_open_now_factor` below), never a query-time
predicate, so Row 2 degrading to same-area-only (sparse geo: 0/177 real
places have coordinates today, verified) never depends on an hours table
that is equally sparse. "Never returns empty" is enforced by
`ROW2 fallback ladder`'s `editorial_fallback` rung (drop the geo/area
constraint down to city-wide, competitor exclusion still applied) reusing
`now_filters.models.DEFAULT_LADDER` unmodified -- the exact ladder E3.2
built and tested this rail's radius-widening rungs against.
"""

from __future__ import annotations

from datetime import datetime, timezone

from now_blender.geo import geo_distance_m, geo_proximity_component
from now_blender.mmr import diversify_ranked
from now_blender.platform import DEFAULT_SITE_RANKING_CONFIG, SiteRankingConfig
from now_filters.contextual import is_open_at
from now_filters.diversity import DiversityCaps
from now_filters.hard import DEFAULT_PLACES_TABLE
from now_filters.models import DEFAULT_LADDER, RungSpec
from now_filters.pipeline import NearbySubject, run_nearby_ladder
from now_filters.type_relations import TypeRelation
from now_search import query_embedder
from sqlalchemy.engine import Connection

from now_rails.display import fetch_place_names
from now_rails.fast_similarity import build_fast_similarity_fn as build_similarity_fn
from now_rails.ladders import ladder_target
from now_rails.models import ROW2, ComponentScoreOut, RailItem, RailResult
from now_rails.place_quality import fetch_place_quality
from now_rails.subject import ArticleSubject

DEFAULT_K = 6
DEFAULT_RERANK_POOL = 40  # ARCHITECTURE.md Sec.7: "re-ranked ... (top ~40)"

# ARCHITECTURE.md Sec.7 Row 2 "Extra: open-now soft". A down-weight, not an
# exclusion -- a closed-right-now venue can still be the best nearby
# recommendation (the reader may be planning ahead, not walking there this
# minute); this constant is a disclosed judgment call, same class as
# `now_filters.contextual.ALREADY_READ_DECAY_DAYS`'s own "not a
# study-validated shape" admission.
CLOSED_NOW_PENALTY = 0.85


def _open_now_factor(candidate, when: datetime) -> tuple[float, bool | None]:
    if not candidate.hours:
        return 1.0, None  # unknown hours -- neutral, matches contextual.is_open_at's own "unknown = open" default
    open_now = is_open_at(candidate, when)
    return (1.0 if open_now else CLOSED_NOW_PENALTY), open_now


def compute_row2(
    conn: Connection,
    subject: ArticleSubject,
    relations: dict[str, TypeRelation],
    *,
    site_config: SiteRankingConfig = DEFAULT_SITE_RANKING_CONFIG,
    k: int = DEFAULT_K,
    rerank_pool: int = DEFAULT_RERANK_POOL,
    ladder: tuple[RungSpec, ...] = DEFAULT_LADDER,
    places_table: str = DEFAULT_PLACES_TABLE,
    now: datetime | None = None,
) -> RailResult:
    when = now or datetime.now(timezone.utc)

    if subject.primary_type is None:
        # Same fail-closed stance as Row 1 (see row1_complementary.py's
        # `_pool_fetch_fn`): `now_filters.pipeline`'s own
        # `editorial_fallback` rung drops the competitor-exclusion
        # predicate entirely when `subject_type` is unknown (there is
        # nothing to exclude *from*), which would make Row 2's last rung
        # return literally every active place with no type check at all.
        # The brief is explicit that the exclusion "never relaxes ... for
        # any tier" and takes priority over "never empty" -- an unknown
        # subject type fails the WHOLE rail closed rather than guessing.
        return RailResult(
            rail=ROW2, items=[], rung_name="no_subject_type", rung_index=-1, rungs_evaluated=[],
            pool_size=0, subject_type=None, weights_source=site_config.weights_source,
            unvalidated_reason=(
                "subject article has no primary_type (F50 -- real archive-wide NULL); "
                "competitor exclusion cannot be computed from an unknown subject type, so this "
                "rail fails closed rather than risk showing an unexcluded competitor"
            ),
        )

    nearby_subject = NearbySubject(
        place_id=subject.place.entity_id if subject.place else None,
        type=subject.primary_type,
        lat=subject.place.lat if subject.place else None,
        lng=subject.place.lng if subject.place else None,
        area_term=subject.place.area_term if subject.place else None,
    )
    ladder_run = run_nearby_ladder(
        conn, nearby_subject, relations, slots_needed=ladder_target(k, rerank_pool), ladder=ladder, places_table=places_table
    )
    pool = ladder_run.result.candidates

    unvalidated_reason: str | None = None
    if not pool:
        unvalidated_reason = "no eligible places matched at any rung (F27: real places are not status='active' yet)"

    place_ids = [c.entity_id for c in pool]
    quality_by_id = fetch_place_quality(conn, place_ids)

    relevance: dict[tuple[str, int], float] = {}
    components_by_key: dict[tuple[str, int], list[ComponentScoreOut]] = {}
    for c in pool:
        geo_raw = geo_proximity_component(c.distance_m) if c.distance_m is not None else None
        # `now_filters.hard.fetch_places_hard_filtered` does not itself
        # populate `distance_m` on the returned Candidate (it selects
        # lat/lng, not the computed ST_Distance value) -- recompute from
        # the subject's own lat/lng so the geo component is available
        # whenever both sides have coordinates, matching Row 1/3's
        # "component computed here, not assumed present on the Candidate"
        # pattern.
        if geo_raw is None and nearby_subject.lat is not None and nearby_subject.lng is not None and c.lat is not None and c.lng is not None:
            geo_raw = geo_proximity_component(geo_distance_m(nearby_subject.lat, nearby_subject.lng, c.lat, c.lng))
        geo_factor = geo_raw if geo_raw is not None else 1.0

        open_factor, open_now = _open_now_factor(c, when)
        quality_row = quality_by_id.get(c.entity_id)
        quality_factor = 1.0 + (quality_row.score if quality_row else 0.0) * 1e-6  # tie-break only

        relevance[c.key] = geo_factor * open_factor * quality_factor
        components_by_key[c.key] = [
            ComponentScoreOut(
                key="geo_proximity", label="geo_proximity", value=geo_raw, weight=0.5,
                explanation="exp(-distance_m/3000); neutral (1.0) when either side has no lat/lng -- true for 0/177 real places today (F30/geocoding backlog).",
                available=geo_raw is not None,
            ),
            ComponentScoreOut(
                key="open_now", label="open_now", value=(1.0 if open_now else 0.0) if open_now is not None else None, weight=0.3,
                explanation=f"soft down-weight ({CLOSED_NOW_PENALTY}x) when closed right now, never a hard exclusion; unknown hours -> neutral.",
                available=open_now is not None,
            ),
            ComponentScoreOut(
                key="quality", label="quality", value=quality_row.score if quality_row else None, weight=0.2,
                explanation="engine.quality_scores (entity_type='place') -- tie-break only. Always None today (no places scorer has run).",
                available=quality_row is not None,
            ),
        ]

    similarity_fn, _sim_loader = build_similarity_fn(conn, pool, model=query_embedder.model_name())
    diversified = diversify_ranked(pool, relevance, k=k, similarity_fn=similarity_fn, caps=DiversityCaps())

    display_ids = [c.entity_id for c in diversified]
    names = fetch_place_names(conn, display_ids)

    items = [
        RailItem(
            entity_type="place",
            entity_id=c.entity_id,
            rail=ROW2,
            position=rank,
            score=relevance[c.key],
            components=components_by_key[c.key],
            title=names.get(c.entity_id, (None, None))[0],
            slug=names.get(c.entity_id, (None, None))[1],
        )
        for rank, c in enumerate(diversified, start=1)
    ]

    return RailResult(
        rail=ROW2,
        items=items,
        rung_name=ladder_run.result.rung_name,
        rung_index=ladder_run.result.rung_index,
        rungs_evaluated=ladder_run.rungs_evaluated,
        pool_size=len(pool),
        subject_type=subject.primary_type,
        weights_source=site_config.weights_source,
        unvalidated_reason=unvalidated_reason,
    )
