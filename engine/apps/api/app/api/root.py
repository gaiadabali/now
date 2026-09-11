"""Non-tenant routes: no site resolution, no DB dependency."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["ops"])


class HealthzResponse(BaseModel):
    status: str


@router.get("/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    """Unauthenticated liveness probe for the load balancer.

    Deliberately does not touch any database -- a city or platform outage
    must not make the load balancer think engine-api itself is down.
    """
    return HealthzResponse(status="ok")
