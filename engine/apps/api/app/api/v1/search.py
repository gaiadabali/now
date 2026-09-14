"""`GET /v1/{site}/search` -- ARCHITECTURE.md §16.

Hybrid BM25 + pgvector retrieval fused with RRF (E3.1, `now_search`),
over a candidate pool the §8 hard filters resolved first. See
`app/domain/search/service.py` for why filtering precedes retrieval and
why the competitor rule does not apply to a subject-less query.

`db: AsyncSession = Depends(get_city_db)` is present for its dependency
side effect only -- it is what makes an unknown site 404 and an
unreachable city DB 503 *before* this handler opens its own (separate,
sync-side) connection. `rails.py` carries the identical pattern and its
docstring explains the async/sync split in full.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from now_config import SiteNotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.search.schemas import SearchResponse
from app.domain.search.service import DEFAULT_K, MAX_K, search_articles
from app.infra.db.deps import get_city_db

logger = logging.getLogger("engine_api.search")

router = APIRouter(tags=["search"])


async def _resolve_site_config(request: Request, site: str):
    registry = request.app.state.site_registry
    try:
        return await registry.get_by_slug(site)
    except SiteNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown site '{site}'") from None
    except Exception as exc:  # noqa: BLE001 -- defensive: db.deps already probed reachability this request
        logger.error("site registry lookup failed for site=%s while resolving search", site)
        raise HTTPException(status_code=503, detail="site registry is temporarily unavailable") from exc


@router.get("/search", response_model=SearchResponse)
async def search(
    site: str,
    request: Request,
    q: str = Query(min_length=1, max_length=200, description="The reader's query string."),
    db: AsyncSession = Depends(get_city_db),
    k: int = Query(default=DEFAULT_K, ge=1, le=MAX_K, description="Results to return."),
    type: list[str] | None = Query(  # noqa: A002 -- `type` is the §16 query-param name, a public contract
        default=None,
        description="L1 type facet (§4). Repeatable; multiple values are OR'd.",
    ),
    format: list[str] | None = Query(  # noqa: A002 -- likewise §16
        default=None,
        description="Format facet (§4). Repeatable; multiple values are OR'd.",
    ),
    facets: list[str] | None = Query(
        default=None,
        description=(
            "Term-facet selectors as `facet:term-slug` (e.g. `location:senopati`). "
            "Repeatable. Selectors matching no term are reported in `unresolved_facets` "
            "rather than silently ignored."
        ),
    ),
) -> SearchResponse:
    site_config = await _resolve_site_config(request, site)
    return await search_articles(
        site_config,
        q,
        k=k,
        types=type,
        formats=format,
        facets=facets,
    )
