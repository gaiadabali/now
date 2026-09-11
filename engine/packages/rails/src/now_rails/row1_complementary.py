"""Row 1 -- Complementary (ARCHITECTURE.md Sec.7): "reading a hotel? show
where to eat." Pool is `complements[subject_type]` -- an explicit
co-recommendation whitelist (`engine.type_relations.complements`), not
"everything that isn't a competitor" -- so this module adds its own
`type = ANY(complements)` predicate on top of `now_filters.hard
.build_places_hard_filter_sql`'s competitor-exclusion/status/quality
predicates, rather than relying on exclusion alone to shape the pool.

Cold-start relevance is the literal Sec.7 formula, computed here (not fed
through `now_blender.compute_blend`, whose six named terms have no slot
for a *multiplicative* facet-compat product):

    compat = price_band_proximity * vibe_overlap * geo_proximity * user_taste

`user_taste` is always `1.0` (E7.2 not built -- the identity element for a
product, matching how a *missing* factor here is treated as neutral
(`1.0`), not `0.0`: multiplying by `None`/0 would silently zero out every
candidate the instant one facet is unpopulated, which is true for
100% of real places today -- see `vibes.py`/`now_blender.geo`'s own
"missing is not the same as worst-case" rule). Real `public.places` has
**zero** rows with `price_band`/vibe tags set, so on real content every
compat score is uniformly `1.0` today and the tie-break is quality then id
-- disclosed in `RailResult.unvalidated_reason`, not hidden.

MMR diversity reuses `now_blender.mmr.diversify_ranked` with real cosine
similarity over `engine.embeddings` (`entity_type='place'` rows exist for
all 177 real places, verified) -- genuinely real, unlike the facet-compat
inputs above.
"""

from __future__ import annotations

from datetime import datetime, timezone

from now_blender.geo import geo_distance_m, geo_proximity_component, price_compat
from now_blender.mmr import diversify_ranked
from now_blender.platform import DEFAULT_SITE_RANKING_CONFIG, SiteRankingConfig
from now_filters.diversity import DiversityCaps
from now_filters.hard import DEFAULT_PLACES_TABLE, PlacesHardFilterQuery, build_places_hard_filter_sql, fetch_places_hard_filtered
from now_filters.ladder import run_ladder
from now_filters.models import Candidate, RungSpec
from now_filters.type_relations import TypeRelation
from now_search import query_embedder
from sqlalchemy.engine import Connection

from now_rails.display import fetch_place_names
from now_rails.fast_similarity import build_fast_similarity_fn as build_similarity_fn
from now_rails.ladders import ROW1_LADDER, ladder_target
from now_rails.models import ROW1, ComponentScoreOut, RailItem, RailResult
from now_rails.place_quality import fetch_place_quality
from now_rails.subject import ArticleSubject
from now_rails.vibes import fetch_place_vibes, vibe_overlap

DEFAULT_K = 6
DEFAULT_RERANK_POOL = 40  # ARCHITECTURE.md Sec.7: "re-ranked ... (top ~40)"


def _pool_fetch_fn(
    conn: Connection, subject: ArticleSubject, relations: dict[str, TypeRelation], *, places_table: str
):
    def _fetch(rung: RungSpec) -> list[Candidate]:
        if subject.primary_type is None:
            # No subject type at all (F50) -> competitor exclusion cannot
            # be computed from the subject side (now_filters.type_relations
            # .excluded_types_for's own documented behaviour for an
            # unknown subject_type), so even the editorial-fallback rung
            # -- which still requires exclusion to be meaningful -- must
            # not run. Returning [] at every rung is the fail-closed
            # choice, not a starvation bug: showing ANY place would risk
            # showing the subject's own (unknown) type back to itself.
            return []
        relation = relations.get(subject.primary_type)
        complements = relation.complements if relation else ()
        if not complements and not rung.editorial_fallback:
            return []  # nothing to recommend -- an editorial-fallback rung is the only way forward

        area_terms = None
        if rung.area_level == "area" and subject.place is not None and subject.place.area_term:
            area_terms = [subject.place.area_term]

        base: PlacesHardFilterQuery = build_places_hard_filter_sql(
            subject_type=subject.primary_type,
            relations=relations,
            exclude_self_id=subject.place.entity_id if subject.place else None,
            area_terms=area_terms,
            editorial_fallback=rung.editorial_fallback,
            places_table=places_table,
        )
        if rung.editorial_fallback:
            # Sec.8.F rung 6 semantics, same as `now_filters.hard`'s own
            # editorial-fallback branch: competitor exclusion still
            # applies, but the complements whitelist is dropped -- some
            # non-competitor recommendation beats none.
            query = base
        else:
            query = PlacesHardFilterQuery(
                sql=base.sql + " AND type::text = ANY(:complement_types)",
                params={**base.params, "complement_types": list(complements)},
            )
        return fetch_places_hard_filtered(conn, query)

    return _fetch


def compute_row1(
    conn: Connection,
    subject: ArticleSubject,
    relations: dict[str, TypeRelation],
    *,
    site_config: SiteRankingConfig = DEFAULT_SITE_RANKING_CONFIG,
    k: int = DEFAULT_K,
    rerank_pool: int = DEFAULT_RERANK_POOL,
    ladder: tuple[RungSpec, ...] = ROW1_LADDER,
    places_table: str = DEFAULT_PLACES_TABLE,
    now: datetime | None = None,
) -> RailResult:
    ladder_run = run_ladder(
        _pool_fetch_fn(conn, subject, relations, places_table=places_table),
        subject_type=subject.primary_type,
        relations=relations,
        slots_needed=ladder_target(k, rerank_pool),
        ladder=ladder,
    )
    pool = ladder_run.result.candidates

    unvalidated_reason: str | None = None
    if subject.primary_type is None:
        unvalidated_reason = (
            "subject article has no primary_type (F50 -- real archive-wide NULL); "
            "the complements pool cannot be resolved without one"
        )
    elif not pool:
        unvalidated_reason = "no eligible places matched (F27: real places are not status='active' yet)"

    place_ids = [c.entity_id for c in pool]
    quality_by_id = fetch_place_quality(conn, place_ids)
    vibes_by_id = fetch_place_vibes(conn, place_ids + ([subject.place.entity_id] if subject.place else []))
    subject_vibes = vibes_by_id.get(subject.place.entity_id) if subject.place else None

    subj_lat = subject.place.lat if subject.place else None
    subj_lng = subject.place.lng if subject.place else None
    subj_price = subject.place.price_band if subject.place else None

    compat_by_key: dict[tuple[str, int], float] = {}
    components_by_key: dict[tuple[str, int], list[ComponentScoreOut]] = {}
    for c in pool:
        pb = price_compat(subj_price, c.price_band)
        pb_factor = pb if pb is not None else 1.0
        dist = geo_distance_m(subj_lat, subj_lng, c.lat, c.lng)
        geo_raw = geo_proximity_component(dist)
        geo_factor = geo_raw if geo_raw is not None else 1.0
        vo = vibe_overlap(subject_vibes, vibes_by_id.get(c.entity_id))
        vibe_factor = vo if vo is not None else 1.0
        user_taste = 1.0  # E7.2 not built -- identity element, see module docstring
        compat = pb_factor * vibe_factor * geo_factor * user_taste
        quality_row = quality_by_id.get(c.entity_id)
        # Tie-break only -- quality is NOT multiplied into compat (that
        # would silently change the Sec.7 formula this module implements
        # literally); it breaks ties when compat is uniform, which is
        # every real candidate today (see module docstring).
        compat_by_key[c.key] = compat + (quality_row.score if quality_row else 0.0) * 1e-6

        components_by_key[c.key] = [
            ComponentScoreOut(
                key="price_compat", label="price_compat", value=pb, weight=0.25,
                explanation="1.0 identical price_band, decaying with ordinal distance; neutral (1.0) when either band is unset.",
                available=pb is not None,
            ),
            ComponentScoreOut(
                key="vibe_overlap", label="vibe_overlap", value=vo, weight=0.25,
                explanation="Jaccard overlap of places_vibe tags; neutral (1.0) when either side has no vibe tags.",
                available=vo is not None,
            ),
            ComponentScoreOut(
                key="geo_proximity", label="geo_proximity", value=geo_raw, weight=0.25,
                explanation="exp(-distance_m/3000); neutral (1.0) when subject or candidate has no lat/lng.",
                available=geo_raw is not None,
            ),
            ComponentScoreOut(
                key="quality", label="quality", value=quality_row.score if quality_row else None, weight=0.25,
                explanation="engine.quality_scores (entity_type='place') -- tie-break only, not multiplied into compat. Always None today (no places scorer has run).",
                available=quality_row is not None,
            ),
        ]

    # `sim_loader` (missing_keys/fallback_calls) is not surfaced on
    # `RailResult` today -- same observability gap as `reranker.py`'s own
    # `mmr_missing_embeddings`/`mmr_fallback_calls`, a seam for E3.4
    # (Inspector wiring), not dropped silently: see this package's report.
    similarity_fn, _sim_loader = build_similarity_fn(conn, pool, model=query_embedder.model_name())
    diversified = diversify_ranked(
        pool, compat_by_key, k=k, similarity_fn=similarity_fn, caps=DiversityCaps()
    )

    display_ids = [c.entity_id for c in diversified]
    names = fetch_place_names(conn, display_ids)

    items = [
        RailItem(
            entity_type="place",
            entity_id=c.entity_id,
            rail=ROW1,
            position=rank,
            score=compat_by_key[c.key],
            components=components_by_key[c.key],
            title=names.get(c.entity_id, (None, None))[0],
            slug=names.get(c.entity_id, (None, None))[1],
        )
        for rank, c in enumerate(diversified, start=1)
    ]

    return RailResult(
        rail=ROW1,
        items=items,
        rung_name=ladder_run.result.rung_name,
        rung_index=ladder_run.result.rung_index,
        rungs_evaluated=ladder_run.rungs_evaluated,
        pool_size=len(pool),
        subject_type=subject.primary_type,
        weights_source=site_config.weights_source,
        unvalidated_reason=unvalidated_reason,
    )
