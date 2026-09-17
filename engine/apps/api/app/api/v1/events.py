"""`POST /v1/{site}/events` -- the interaction beacon endpoint (E0.5).

Accepts `{ "interactions": [...], "impressions": [...] }` from
`engine/packages/beacon` and writes both arrays into this city's
`engine.interactions` / `engine.impressions` (see
`app/domain/events/service.py`).

No API-key auth (decision C2 -- see `app/domain/events/cors.py`'s
docstring). Protection is: a CORS origin allowlist sourced from the site
registry's `hostname`, rate limiting keyed by the payload's `anon_id`, a
server-side batch-size ceiling, and validation that turns every malformed/
oversized/unknown-site input into a 4xx -- never a 500.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from now_config import SiteConfig, SiteNotFoundError

from app.domain.events.cors import allowed_origins_for_site, origin_is_allowed
from app.domain.events.schemas import EventsBatchIn
from app.domain.events.service import EventOutOfRangeError, EventsWriteError, write_events
from app.infra.db.deps import get_city_db

logger = logging.getLogger("engine_api.events")

router = APIRouter(tags=["events"])

# Comfortably above a real batch (client caps at ~210 events/array, beacon
# README "Transport") while still bounding worst-case request size -- a
# defense-in-depth ceiling checked before JSON parsing even runs, so an
# oversized body never reaches `json.loads`/Pydantic at all.
MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MiB


async def _resolve_site_config(request: Request, site: str) -> SiteConfig:
    """A second, cheap lookup against the same TTL-cached registry
    `Depends(get_city_db)` already consulted for this request (it doesn't
    hand back the `SiteConfig` it resolved, only a DB session) -- needed
    here for `hostname`, to build the CORS allowlist. By the time this
    runs, `get_city_db` has already 404'd an unknown/inactive site or
    503'd an unreachable registry for this same request, so failures here
    are the rare case where the registry died in between; still mapped
    defensively to 404/503, never left to bubble up as a 500.
    """
    registry = request.app.state.site_registry
    try:
        return await registry.get_by_slug(site)
    except SiteNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown site '{site}'") from None
    except Exception as exc:  # noqa: BLE001 - defensive: see docstring above
        logger.error("site registry lookup failed for site=%s while resolving CORS origin", site)
        raise HTTPException(
            status_code=503, detail="site registry is temporarily unavailable"
        ) from exc


def _cors_headers(origin: str) -> dict[str, str]:
    # `Vary: Origin` -- this response's `Access-Control-Allow-Origin` value
    # depends on the request's `Origin`, so any intermediate cache must key
    # on it too.
    return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}


def _rate_limit_identity(batch: EventsBatchIn, request: Request) -> str:
    """`anon_id` from the payload (decision C2: "rate limit keyed by
    anon_id from the payload, falling back to client IP when absent").
    Every event in a real batch carries the same `anon_id` (one beacon
    instance, one browser tab's queue) so the first one found is
    representative; only a batch with neither array populated (which
    `EventsBatchIn` allows, per the beacon's own "either may be empty"
    contract) falls back to the client IP.
    """
    for interaction in batch.interactions:
        return interaction.anon_id
    for impression in batch.impressions:
        return impression.anon_id
    return request.client.host if request.client else "unknown"


@router.options("/events")
async def preflight_events(site: str, request: Request) -> Response:
    """CORS preflight for the `fetch(..., {keepalive})` fallback transport.

    The beacon's primary transport, `navigator.sendBeacon`, is always sent
    in `no-cors` mode by the browser and never triggers a preflight -- this
    handler only matters for the fetch fallback (used when `sendBeacon` is
    unavailable) and for manual/XHR testing. No DB touched and no rate
    limiting here: a preflight carries no body and no event data, so there
    is nothing to write and nothing to key a rate limit on.
    """
    origin = request.headers.get("origin")
    site_config = await _resolve_site_config(request, site)
    settings = request.app.state.settings

    if origin is None:
        return Response(status_code=204)
    extra_origins = settings.extra_allowed_origins.get(site, ())
    if not origin_is_allowed(origin, site_config, env=settings.env, extra=extra_origins):
        # Same reasoning as the POST path. A preflight refusal is the FIRST
        # thing a browser hits, so this is often the earliest evidence
        # available that an origin is misconfigured.
        logger.warning(
            "events preflight origin rejected: site=%s origin=%s allowed=%s",
            site,
            origin,
            ",".join(allowed_origins_for_site(site_config, extra_origins)),
        )
        return Response(status_code=403)

    requested_headers = request.headers.get("access-control-request-headers", "content-type")
    return Response(
        status_code=204,
        headers={
            **_cors_headers(origin),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": requested_headers,
            "Access-Control-Max-Age": "600",
        },
    )


@router.post("/events", status_code=204)
async def post_events(
    site: str,
    request: Request,
    db: AsyncSession = Depends(get_city_db),
) -> Response:
    """Accepts one beacon batch and writes it into this city's tables.

    Order of checks is deliberate:

    1. `Depends(get_city_db)` -- unknown/inactive site -> 404, registry or
       city DB unreachable -> 503. Runs before the handler body at all
       (FastAPI dependency resolution), so a bad site never even reaches
       body parsing.
    2. Body-size ceiling, then JSON parse, then schema validation
       (`EventsBatchIn`, which itself caps array length at
       `MAX_EVENTS_PER_ARRAY`) -- malformed or oversized -> 4xx.
    3. CORS origin allowlist (decision C2) -- a disallowed browser
       `Origin` -> 403.
    4. Rate limit keyed by the batch's `anon_id` -> 429.
    5. Write. A `ts` outside the currently provisioned partition window is
       a client-data problem, translated to 400 rather than left to
       surface as a raw database error.

    Every one of the above is a controlled `HTTPException`; nothing here
    lets an unexpected exception escape as a bare 500 for these known
    failure classes.
    """
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="request body exceeds maximum size")

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"malformed JSON body: {exc.msg}") from None

    try:
        batch = EventsBatchIn.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False),
        ) from None

    site_config = await _resolve_site_config(request, site)
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    extra_origins = settings.extra_allowed_origins.get(site, ())
    if origin is not None and not origin_is_allowed(
        origin, site_config, env=settings.env, extra=extra_origins
    ):
        # Logged with BOTH sides of the comparison, because the absence of this
        # line is what made the production outage expensive: the beacon was
        # firing, the endpoint was reachable, every batch 403'd, and nothing
        # anywhere said which origin had been refused or what was expected. It
        # took an SSH session and a hand-built repro to learn that the site's
        # own front end was being judged like a hostile one. None of these
        # values are secret — they are a public hostname and a config list.
        logger.warning(
            "events origin rejected: site=%s origin=%s allowed=%s",
            site,
            origin,
            ",".join(allowed_origins_for_site(site_config, extra_origins)),
        )
        raise HTTPException(
            status_code=403, detail=f"origin '{origin}' is not allowed for site '{site}'"
        )

    limiter = request.app.state.rate_limiter
    identity = _rate_limit_identity(batch, request)
    if not await limiter.allow(f"events:{site}:{identity}"):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    try:
        result = await write_events(db, batch)
    except (EventOutOfRangeError, EventsWriteError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    logger.info(
        "events batch written",
        extra={
            "site": site,
            "interactions_written": result.interactions_written,
            "impressions_written": result.impressions_written,
        },
    )

    return Response(status_code=204, headers=_cors_headers(origin) if origin is not None else {})
