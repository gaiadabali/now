"""Per-request structured logging: request id, site, route, latency, status."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("engine_api.request")


def _extract_site(path: str) -> str | None:
    """`/v1/{site}/...` -> `{site}`. `None` for non-tenant routes like `/healthz`."""
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "v1":
        return parts[1]
    return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        site = _extract_site(request.url.path)
        request.state.request_id = request_id
        request.state.site = site
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "site": site,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": 500,
                    "latency_ms": latency_ms,
                },
            )
            raise

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "site": site,
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response
