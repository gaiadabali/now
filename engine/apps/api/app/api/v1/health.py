"""`GET /v1/{site}/health` -- resolves and pings the correct city database.

- Unknown site      -> 404 (raised by `get_city_db`)
- Site DB unreachable -> 503 (raised by `get_city_db`)
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.deps import get_city_db

router = APIRouter(tags=["health"])


class CityHealthResponse(BaseModel):
    site: str
    status: str
    database: str
    latency_ms: float


@router.get("/health", response_model=CityHealthResponse)
async def city_health(site: str, db: AsyncSession = Depends(get_city_db)) -> CityHealthResponse:
    start = time.perf_counter()
    await db.execute(text("SELECT 1"))
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return CityHealthResponse(
        site=site,
        status="ok",
        database="reachable",
        latency_ms=latency_ms,
    )
