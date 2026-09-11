"""Aggregates every `/v1/{site}/...` route group.

Route groups are added here one wave at a time: `health` now (E0.3),
`events` in E0.5, then `articles` / `places` / `search` / `itineraries` /
`assistant` from E3 onward. Each group is one task's exclusive file per the
ownership map in PROGRESS.md.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import events, health, rails

router = APIRouter(prefix="/v1/{site}")
router.include_router(health.router)
router.include_router(events.router)
router.include_router(rails.router)
