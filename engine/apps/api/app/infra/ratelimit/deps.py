"""FastAPI dependency wiring for `RateLimiter`.

Not yet attached to any route in this skeleton wave. E0.5's beacon endpoint
is the intended first consumer, keyed by `anon_id` (from the beacon payload)
rather than the generic client-IP fallback used here.
"""

from __future__ import annotations

from fastapi import HTTPException, Path, Request


async def enforce_rate_limit(
    request: Request,
    site: str = Path(..., description="City site slug."),
) -> None:
    limiter = request.app.state.rate_limiter
    identity = request.headers.get("x-api-key") or (
        request.client.host if request.client else "unknown"
    )
    allowed = await limiter.allow(f"{site}:{identity}")
    if not allowed:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
