"""`GET /v1/{site}/articles/{id}/rails` -- E3.8 (ARCHITECTURE.md §16).
Returns all three rails (Row 1 Complementary, Row 2 Nearby, Row 3
Similar) for one article, precomputed-and-cached per `(article_id,
segment)` in `engine.rail_cache` (E3.5-E3.7, `now_rails`), personalized
re-rank over the cached top ~40 not yet wired (E7.1/E7.2 gate it -- see
`now_rails.personalize`).

Depends on `Depends(get_city_db)` for the same tenancy/reachability
semantics every other route gets (unknown site -> 404, unreachable city
DB -> 503) even though the actual rail computation runs over this
package's own SYNC connection pools (`app/infra/db/sync_bridge.py`)
-- see that module's docstring for why `now_rails` cannot share the
async pool this dependency hands out. `db` itself is unused in the
handler body beyond the dependency's own side effect (validating the
site); this mirrors `events.py`'s own `_resolve_site_config` pattern of
a second, cheap site lookup for what the primary dependency doesn't
expose (there, CORS `hostname`; here, `db_ref`/`slug` for the sync
bridge).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from now_config import SiteNotFoundError
from now_rails.orchestrator import ArticleNotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rails.schemas import RailsResponse
from app.domain.rails.service import RailsArticleNotFoundError, get_rails
from app.infra.db.deps import get_city_db

logger = logging.getLogger("engine_api.rails")

router = APIRouter(tags=["rails"])


async def _resolve_site_config(request: Request, site: str):
    registry = request.app.state.site_registry
    try:
        return await registry.get_by_slug(site)
    except SiteNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown site '{site}'") from None
    except Exception as exc:  # noqa: BLE001 -- defensive: db.deps already probed reachability this request
        logger.error("site registry lookup failed for site=%s while resolving rails", site)
        raise HTTPException(status_code=503, detail="site registry is temporarily unavailable") from exc


@router.get("/articles/{article_id}/rails", response_model=RailsResponse)
async def get_article_rails(
    site: str,
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_city_db),
    k: int = Query(default=6, ge=1, le=20, description="Slots per rail."),
    synthetic_overlay: bool = Query(
        default=False,
        description=(
            "Debug/hand-check only: overlays a deterministic primary_type/format (F50) so "
            "competitor exclusion and freshness decay can be exercised on real articles that "
            "have not been classified yet. Never cached; never the default for a real reader."
        ),
    ),
    force_refresh: bool = Query(default=False, description="Bypass engine.rail_cache and recompute."),
) -> RailsResponse:
    """`db` (unused beyond `Depends(get_city_db)`'s own 404/503 validation
    of `site`) is required so an unknown or unreachable site's city DB
    fails the same way here as on every other `/v1/{site}/...` route --
    before this handler's own (separate, sync-side) connection is ever
    opened."""
    site_config = await _resolve_site_config(request, site)

    try:
        return await get_rails(
            site_config,
            article_id,
            k=k,
            synthetic_overlay=synthetic_overlay,
            force_refresh=force_refresh,
        )
    except (ArticleNotFoundError, RailsArticleNotFoundError):
        raise HTTPException(status_code=404, detail=f"no published article with id={article_id}") from None
