"""`BlenderReranker` -- the E3.3 integration point. Orchestrates, in
order (ARCHITECTURE.md Sec.7's offline/online split diagram, "ONLINE"
column, minus the filter pipeline and rail generation this package does
not own):

    now_search.SearchEngine.search()        <- RRF-fused candidate pool, UNMODIFIED
        -> fetch quality + article meta (batched, Sec.8.G)
        -> per-candidate BlendComponents -> compute_blend()   (this package, Sec.7)
        -> real embedding cosine similarity_fn (this package)
        -> now_filters.diversity.diversify()  (MMR, UNMODIFIED, real similarity injected)
        -> Sec.10 stage-4 feature vector, logged per candidate at final position

This class is the "re-ranker over the fused candidate set" half of the
F39 decision: it does not call lexical/semantic retrieval itself, does
not touch RRF's fusion math, and does not reimplement MMR's cap
enforcement -- it is glue, on purpose, so every piece it wires stays
independently owned, tested, and (for search/filters) completely
unmodified by this ticket.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy.engine import Connection

from now_filters.models import Candidate
from now_filters.type_relations import TypeRelation, load_type_relations
from now_search import query_embedder
from now_search.engine import SearchEngine
from now_search.models import FusedHit

from now_blender.articles import fetch_article_meta
from now_blender.blend import BlendResult, compute_blend
from now_blender.components import BlendComponents, ComponentScore
from now_blender.covisitation import fetch_covis_scores
from now_blender.decay import describe_format_trust, freshness_component
from now_blender.feature_log import build_record, log_feature_vector
from now_blender.features import build_stage4_features
from now_blender.mmr import diversify_ranked
from now_blender.platform import DEFAULT_SITE_RANKING_CONFIG, SiteRankingConfig, load_site_ranking_config
from now_blender.quality import fetch_quality
from now_blender.similarity import build_similarity_fn
from now_blender.synthetic import deterministic_format

DEFAULT_RERANK_POOL = 40  # ARCHITECTURE.md Sec.7: "re-ranked ... (top ~40)"
DEFAULT_K = 10
DEFAULT_MMR_LAMBDA = 0.7  # ARCHITECTURE.md Sec.8.D


@dataclass(frozen=True)
class BlendedHit:
    entity_id: int
    final_rank: int
    blend_score: float
    components: list[ComponentScore]
    fused_hit: FusedHit
    format_: str | None
    format_is_synthetic: bool


@dataclass(frozen=True)
class RerankTiming:
    search_ms: float
    fetch_ms: float
    blend_ms: float
    mmr_ms: float
    total_ms: float


@dataclass(frozen=True)
class BlendedSearchResult:
    query: str
    hits: list[BlendedHit]
    rerank_pool_size: int
    weights_source: str
    decay_source: str
    mmr_missing_embeddings: int
    mmr_fallback_calls: int
    synthetic_format_overlay: bool
    timing: RerankTiming


def _to_candidate(article_id: int, meta, quality_row, *, synthetic_format_overlay: bool) -> Candidate:
    fmt = meta.format if meta is not None else None
    if fmt is None and synthetic_format_overlay:
        fmt = deterministic_format(article_id)
    return Candidate(
        entity_type="article",
        entity_id=article_id,
        type=meta.primary_type if meta is not None else None,
        series_key=meta.series_key if meta is not None else None,
        format=fmt,
        quality_score=quality_row.score if quality_row is not None else None,
        published_at=meta.published_at if meta is not None else None,
    )


class BlenderReranker:
    def __init__(
        self,
        search_engine: SearchEngine,
        conn: Connection,
        *,
        site_ranking_config: SiteRankingConfig = DEFAULT_SITE_RANKING_CONFIG,
        relations: dict[str, TypeRelation] | None = None,
    ) -> None:
        self._engine = search_engine
        self._conn = conn
        self._site_config = site_ranking_config
        self._relations = relations or {}

    @classmethod
    def build(
        cls,
        city_conn: Connection,
        *,
        platform_conn: Connection | None = None,
        site_slug: str | None = None,
    ) -> "BlenderReranker":
        """`platform_conn`/`site_slug` are optional together: give both to
        read live `sites.ranking_weights`, or omit both to fall back to
        `DEFAULT_SITE_RANKING_CONFIG` (documented, never silent -- see
        `BlendedSearchResult.weights_source`/`decay_source` on every
        result, which name exactly which branch was taken)."""
        engine = SearchEngine(city_conn)
        engine.warm_up()
        try:
            relations = load_type_relations(city_conn)
        except Exception:  # noqa: BLE001 -- engine.type_relations may not exist in every test DB
            relations = {}
        if platform_conn is not None and site_slug is not None:
            config = load_site_ranking_config(platform_conn, site_slug)
        else:
            config = DEFAULT_SITE_RANKING_CONFIG
        return cls(engine, city_conn, site_ranking_config=config, relations=relations)

    def rerank(
        self,
        query: str,
        *,
        k: int = DEFAULT_K,
        rerank_pool: int = DEFAULT_RERANK_POOL,
        mmr_lambda: float = DEFAULT_MMR_LAMBDA,
        synthetic_format_overlay: bool = False,
        log_features: bool = True,
        surface: str = "search",
        now=None,
    ) -> BlendedSearchResult:
        t_start = time.perf_counter()

        t0 = time.perf_counter()
        search_result = self._engine.search(query, k=rerank_pool, compute_facets=False)
        fused_hits = search_result.hits
        search_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        article_ids = [int(h.entity_id) for h in fused_hits]
        meta_by_id = fetch_article_meta(self._conn, article_ids, self._site_config.format_term_ids)
        quality_by_id = fetch_quality(self._conn, article_ids)
        # Plain keyword search has no subject entity to co-visit against
        # (see covisitation.py's docstring) -- calling the real lookup
        # with subject_entity_id=None short-circuits to {} without a
        # query, which is the honest answer for this surface. Row 1
        # (E3.5) has a subject and should call `fetch_covis_scores` for
        # real once `engine.covisitation` has traffic to answer from.
        covis_by_id = fetch_covis_scores(self._conn, subject_entity_id=None, candidate_entity_ids=[])
        fetch_ms = (time.perf_counter() - t1) * 1000

        t2 = time.perf_counter()
        candidates: list[Candidate] = []
        fused_by_key: dict[tuple[str, int], FusedHit] = {}
        blend_by_key: dict[tuple[str, int], BlendResult] = {}
        format_is_synthetic: dict[tuple[str, int], bool] = {}

        for hit in fused_hits:
            article_id = int(hit.entity_id)
            meta = meta_by_id.get(article_id)
            quality_row = quality_by_id.get(article_id)
            candidate = _to_candidate(article_id, meta, quality_row, synthetic_format_overlay=synthetic_format_overlay)
            candidates.append(candidate)
            fused_by_key[candidate.key] = hit
            format_is_synthetic[candidate.key] = synthetic_format_overlay and (meta is None or meta.format is None)

            semantic = max(0.0, hit.semantic_raw_score) if hit.semantic_raw_score is not None else None
            format_confidence = meta.format_confidence if meta is not None else None
            format_source = meta.format_source if meta is not None else None
            fresh = freshness_component(
                candidate.format, candidate.published_at, self._site_config.decay,
                format_confidence=format_confidence, format_source=format_source, now=now,
            )
            fresh_reason = describe_format_trust(candidate.format, format_confidence, format_source, self._site_config.decay)
            components = BlendComponents(
                semantic=semantic,
                covis=covis_by_id.get(str(article_id)),
                freshness=fresh,
                quality=quality_row.score if quality_row is not None else None,
                geo=None,
                promo=None,
                freshness_explanation=fresh_reason,
            )
            blend_by_key[candidate.key] = compute_blend(components, self._site_config.weights)

        relevance = {key: result.normalized_score for key, result in blend_by_key.items()}
        similarity_fn, sim_loader = build_similarity_fn(self._conn, candidates, model=query_embedder.model_name())
        diversified = diversify_ranked(candidates, relevance, k=k, similarity_fn=similarity_fn, lambda_=mmr_lambda)
        blend_ms = (time.perf_counter() - t2) * 1000

        t3 = time.perf_counter()
        out: list[BlendedHit] = []
        for rank, candidate in enumerate(diversified, start=1):
            blend_result = blend_by_key[candidate.key]
            hit = fused_by_key[candidate.key]
            out.append(
                BlendedHit(
                    entity_id=candidate.entity_id,
                    final_rank=rank,
                    blend_score=blend_result.normalized_score,
                    components=blend_result.components,
                    fused_hit=hit,
                    format_=candidate.format,
                    format_is_synthetic=format_is_synthetic[candidate.key],
                )
            )
            if log_features:
                quality_row = quality_by_id.get(candidate.entity_id)
                features = build_stage4_features(
                    fused_hit=hit,
                    candidate=candidate,
                    subject=None,
                    relations=self._relations,
                    freshness=next(c.value for c in blend_result.components if c.key == "freshness"),
                    quality=quality_row.score if quality_row is not None else None,
                    popularity_prior=quality_row.popularity_prior if quality_row is not None else None,
                    covis_score=None,
                    already_read=None,
                    position=rank,
                )
                record = build_record(
                    site_slug=self._site_config.site_slug,
                    surface=surface,
                    query=query,
                    subject_entity_id=None,
                    entity_type="article",
                    entity_id=candidate.entity_id,
                    blend_score=blend_result.normalized_score,
                    weights_source=self._site_config.weights_source,
                    features=features,
                    now=now,
                )
                log_feature_vector(record)
        mmr_ms = (time.perf_counter() - t3) * 1000
        total_ms = (time.perf_counter() - t_start) * 1000

        return BlendedSearchResult(
            query=query,
            hits=out,
            rerank_pool_size=len(fused_hits),
            weights_source=self._site_config.weights_source,
            decay_source=self._site_config.decay_source,
            mmr_missing_embeddings=len(sim_loader.missing_keys),
            mmr_fallback_calls=sim_loader.fallback_calls,
            synthetic_format_overlay=synthetic_format_overlay,
            timing=RerankTiming(search_ms=search_ms, fetch_ms=fetch_ms, blend_ms=blend_ms, mmr_ms=mmr_ms, total_ms=total_ms),
        )

    def fetch_summaries(self, article_ids: list[int]):
        """Passthrough to `SearchEngine.fetch_summaries` -- title/dek
        lookups for a hand-check display, not part of the ranking
        pipeline itself."""
        return self._engine.fetch_summaries(article_ids)

    def close(self) -> None:
        self._engine.close()
