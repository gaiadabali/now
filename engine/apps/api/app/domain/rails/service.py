"""`GET /v1/{site}/articles/{id}/rails` -- resolves the site's `db_ref`,
runs `now_rails.orchestrator.RailsOrchestrator` off the event loop
(`sync_bridge.run_sync`), and maps the result to this module's wire
schema.

Read-only against the platform DB (site resolution) and the city DB
(everything else) -- no writes happen in this request path except
`engine.rail_cache` itself, which `now_rails.cache.write_rail_caches`
already limits to a single multi-row upsert per cache-miss compute (see
that package's README "Performance" section).
"""

from __future__ import annotations

from now_config import SiteConfig
from now_rails.orchestrator import ArticleNotFoundError, RailsOrchestrator

from app.domain.rails.schemas import CacheInfoOut, ComponentScoreOut, RailItemOut, RailOut, RailsResponse
from app.domain.rails.sync_bridge import get_sync_city_engine, get_sync_platform_engine, run_sync

DEFAULT_K = 6
DEFAULT_RERANK_POOL = 40  # ARCHITECTURE.md §7: "re-ranked ... (top ~40)"


class RailsArticleNotFoundError(Exception):
    """No published article with this id on this site -- maps to 404."""


def _to_response(bundle) -> RailsResponse:  # bundle: now_rails.models.RailsBundle
    rails_out: dict[str, RailOut] = {}
    for name, result in bundle.rails.items():
        rails_out[name] = RailOut(
            rail=result.rail,
            items=[
                RailItemOut(
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    rail=item.rail,
                    position=item.position,
                    score=item.score,
                    components=[
                        ComponentScoreOut(
                            key=c.key, label=c.label, value=c.value, weight=c.weight,
                            explanation=c.explanation, available=c.available,
                        )
                        for c in item.components
                    ],
                    title=item.title,
                    slug=item.slug,
                    is_paid=item.is_paid,
                )
                for item in result.items
            ],
            rung_name=result.rung_name,
            rung_index=result.rung_index,
            rungs_evaluated=result.rungs_evaluated,
            pool_size=result.pool_size,
            subject_type=result.subject_type,
            weights_source=result.weights_source,
            unvalidated_reason=result.unvalidated_reason,
        )
    return RailsResponse(
        article_id=bundle.article_id,
        segment=bundle.segment,
        rails=rails_out,
        cache=CacheInfoOut(hit=bundle.cache_hit, computed_at=bundle.computed_at),
        synthetic_overlay=bundle.synthetic_overlay,
    )


def _compute(
    db_ref: str,
    site_slug: str,
    article_id: int,
    *,
    k: int,
    rerank_pool: int,
    synthetic_overlay: bool,
    force_refresh: bool,
) -> RailsResponse:
    """Runs entirely off the event loop (see `sync_bridge.run_sync`).
    Opens its own short-lived sync connections from the cached `Engine`
    pools -- one per call, released on exit, exactly like `now_search`/
    `now_filters`/`now_blender`'s own CLI/test connection lifecycle."""
    city_eng = get_sync_city_engine(db_ref)
    platform_eng = get_sync_platform_engine()
    with city_eng.connect() as city_conn, platform_eng.connect() as platform_conn:
        orch = RailsOrchestrator.build(city_conn, platform_conn=platform_conn, site_slug=site_slug)
        try:
            bundle = orch.compute_rails(
                article_id,
                k=k,
                rerank_pool=rerank_pool,
                synthetic_overlay=synthetic_overlay,
                force_refresh=force_refresh,
            )
        except ArticleNotFoundError as exc:
            raise RailsArticleNotFoundError(str(exc)) from exc
        return _to_response(bundle)


async def get_rails(
    site_config: SiteConfig,
    article_id: int,
    *,
    k: int = DEFAULT_K,
    rerank_pool: int = DEFAULT_RERANK_POOL,
    synthetic_overlay: bool = False,
    force_refresh: bool = False,
) -> RailsResponse:
    return await run_sync(
        lambda: _compute(
            site_config.db_ref,
            site_config.slug,
            article_id,
            k=k,
            rerank_pool=rerank_pool,
            synthetic_overlay=synthetic_overlay,
            force_refresh=force_refresh,
        )
    )
