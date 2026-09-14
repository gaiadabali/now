"""Aggregates every `/v1/{site}/...` route group.

Route groups are added here one wave at a time: `health` (E0.3), `events`
(E0.5), `rails` (E3.8) and `search` (E3.1's engine, exposed over HTTP),
with `articles` / `places` / `itineraries` / `assistant` still to come.
Each group is one task's exclusive file per the ownership map in
PROGRESS.md.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import events, health, rails, search

router = APIRouter(prefix="/v1/{site}")
router.include_router(health.router)
router.include_router(events.router)
router.include_router(rails.router)
router.include_router(search.router)
